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

def test_split_words_no_tail_loss():
    from app.models.asr import _split_words
    out = _split_words("一二三四五六七八九", 5)
    assert len(out) == 5
    assert "".join(out) == "一二三四五六七八九"

def test_split_words_more_segments_than_chars():
    from app.models.asr import _split_words
    out = _split_words("一二三", 5)
    assert len(out) == 5
    assert "".join(x for x in out if x) == "一二三"
