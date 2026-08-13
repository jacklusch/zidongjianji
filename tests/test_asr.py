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
