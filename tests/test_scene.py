from app.analyzer.scene import detect_shots, is_image


def test_detect_shots_returns_shots(sample_video):
    shots = detect_shots(sample_video)
    assert len(shots) >= 1
    first = shots[0]
    assert first.start >= 0 and first.end > first.start
    assert first.duration > 0


def test_is_image():
    assert is_image("a.JPG")
    assert not is_image("a.mp4")