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

def test_asr_aligns_timestamp_words(monkeypatch):
    import sys
    class FakeModel:
        def generate(self, input):
            return [{"text": "你 好 世 界",
                     "timestamp": [[500, 600], [600, 700], [700, 800], [800, 900]]}]
    class FakeFunasr:
        class AutoModel:
            def __init__(self, model):
                pass
            def generate(self, input):
                return FakeModel().generate(input)
    monkeypatch.setitem(sys.modules, "funasr", FakeFunasr())
    a = ASR(provider="local", model="m", device="cpu")
    segs = a.transcribe("x.wav")
    assert len(segs) == 4
    assert segs[0] == {"start": 0.5, "end": 0.6, "text": "你"}
    assert segs[3] == {"start": 0.8, "end": 0.9, "text": "界"}

def test_asr_no_timestamp_returns_single(monkeypatch):
    import sys
    class FakeFunasr:
        class AutoModel:
            def __init__(self, model):
                pass
            def generate(self, input):
                return [{"text": "完整句子"}]
    monkeypatch.setitem(sys.modules, "funasr", FakeFunasr())
    a = ASR(provider="local", model="m", device="cpu")
    segs = a.transcribe("x.wav")
    assert segs == [{"start": 0.0, "end": 0.0, "text": "完整句子"}]
