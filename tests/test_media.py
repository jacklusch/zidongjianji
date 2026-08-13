import pytest
from app.analyzer.media import probe_media, MissingMediaError

def test_probe_video(sample_video, ffprobe):
    info = probe_media(sample_video, ffprobe=ffprobe)
    assert info.filename == "factory01.mp4"
    assert info.width > 0 and info.height > 0
    assert info.duration > 0
    assert info.audio

def test_probe_missing_raises():
    with pytest.raises(MissingMediaError):
        probe_media("not_there.mp4")