import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.asr import ASR

def test_asr_none_returns_empty():
    a = ASR(provider="none", model="", device="cpu")
    assert a.transcribe("whatever.wav") == []

def test_asr_available_local():
    a = ASR(provider="local", model="models/asr", device="cpu")
    assert a.available() is True

def test_asr_groups_sentences(monkeypatch):
    import sys
    class FakeModel:
        def generate(self, input):
            return [{"text": "我 们 今 天 来 拿 洋 葱 结 果 明 天 去",
                     "timestamp": [[500, 600], [600, 700], [700, 800], [800, 900],
                                   [900, 1000], [1000, 1100], [1100, 1200],
                                   [1200, 1300], [1300, 1500], [1500, 1800],  # 800->1300 间隔 100ms，1300->1800 连续
                                   [1800, 1900], [1900, 2000], [2000, 2100]]}]
    class FakeFunasr:
        class AutoModel:
            def __init__(self, model, device=None):
                pass
            def generate(self, input):
                return FakeModel().generate(input)
    monkeypatch.setitem(sys.modules, "funasr", FakeFunasr())
    a = ASR(provider="local", model="m", device="cpu")
    segs = a.transcribe("x.wav")
    # 无 >350ms 间隔，应合并为 1 句
    assert len(segs) == 1
    assert segs[0]["text"] == "我们今天来拿洋葱结果明天去"
    assert abs(segs[0]["start"] - 0.5) < 1e-6
    assert abs(segs[0]["end"] - 2.1) < 1e-6

def test_asr_splits_on_long_gap(monkeypatch):
    import sys
    class FakeModel:
        def generate(self, input):
            return [{"text": "一 二 三 四 五",
                     "timestamp": [[100, 200], [200, 300], [900, 1000],  # 300->900 gap 600ms 断句
                                   [1000, 1100], [1100, 1200]]}]
    class FakeFunasr:
        class AutoModel:
            def __init__(self, model, device=None):
                pass
            def generate(self, input):
                return FakeModel().generate(input)
    monkeypatch.setitem(sys.modules, "funasr", FakeFunasr())
    a = ASR(provider="local", model="m", device="cpu")
    segs = a.transcribe("x.wav")
    assert len(segs) == 2
    assert segs[0]["text"] == "一二"
    assert segs[1]["text"] == "三四五"
    assert abs(segs[0]["start"] - 0.1) < 1e-6 and abs(segs[0]["end"] - 0.3) < 1e-6
    assert abs(segs[1]["start"] - 0.9) < 1e-6 and abs(segs[1]["end"] - 1.2) < 1e-6

def test_asr_no_timestamp_returns_single(monkeypatch):
    import sys
    class FakeFunasr:
        class AutoModel:
            def __init__(self, model, device=None):
                pass
            def generate(self, input):
                return [{"text": "完整句子"}]
    monkeypatch.setitem(sys.modules, "funasr", FakeFunasr())
    a = ASR(provider="local", model="m", device="cpu")
    segs = a.transcribe("x.wav")
    assert segs == [{"start": 0.0, "end": 0.0, "text": "完整句子"}]
