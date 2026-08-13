import numpy as np
from app.analyzer.frames import sample_times, extract_frame, save_thumbnails
from app.analyzer.visual import fallback_visual_analysis, vlm_visual_analysis


def test_sample_times():
    times = sample_times(0.0, 6.0, frames_min=3, frames_max=8)
    assert 3 <= len(times) <= 8
    assert times[0] >= 0 and times[-1] <= 6.0


def test_extract_frame(sample_video, ffmpeg, tmp_path):
    frame = extract_frame(str(sample_video), 1.0, ffmpeg, tmp_path / "f.jpg", width=320)
    assert (tmp_path / "f.jpg").exists() or frame is not None


def test_fallback_analysis(tmp_path):
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    np.save(str(tmp_path / "a.npy"), img)
    va = fallback_visual_analysis([img])
    assert va.visual_quality >= 0.0
    assert va.shot_type == "medium"


def test_vlm_visual_analysis_parses_struct():
    class FakeVLM:
        def describe(self, frames, prompt):
            assert "JSON" in prompt
            return {"description": "工厂车间", "objects": ["机器"], "actions": ["运转"],
                    "environment": "车间", "shot_type": "medium", "camera_motion": "static",
                    "people_count": 2}
    va = vlm_visual_analysis([np.zeros((10, 10, 3), dtype=np.uint8)], FakeVLM())
    assert va.description == "工厂车间"
    assert va.objects == ["机器"]
    assert va.environment == "车间"
    assert va.people_count == 2


def test_vlm_visual_analysis_falls_back_on_error():
    class BadVLM:
        def describe(self, frames, prompt):
            raise RuntimeError("模型崩溃")
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    va = vlm_visual_analysis([img], BadVLM())
    assert "亮度" in va.description
