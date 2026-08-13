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
                    "people_count": 2, "visual_quality": 0.8}
    va = vlm_visual_analysis([np.zeros((10, 10, 3), dtype=np.uint8)], FakeVLM())
    assert va.description == "工厂车间"
    assert va.objects == ["机器"]
    assert va.environment == "车间"
    assert va.people_count == 2
    assert abs(va.visual_quality - 0.8) < 1e-6


def test_vlm_visual_analysis_falls_back_on_error():
    class BadVLM:
        def describe(self, frames, prompt):
            raise RuntimeError("模型崩溃")
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    va = vlm_visual_analysis([img], BadVLM())
    assert "亮度" in va.description


def test_vlm_visual_analysis_aggregates_frames():
    from app.analyzer.visual import vlm_visual_analysis
    results = iter([
        {"description": "第一帧", "objects": ["人", "刀"], "actions": ["切割"],
         "environment": "厨房", "shot_type": "close", "camera_motion": "static",
         "people_count": 1, "visual_quality": 0.4},
        {"description": "第二帧", "objects": ["人"], "actions": [],
         "environment": "厨房", "shot_type": "close", "camera_motion": "static",
         "people_count": 2, "visual_quality": 0.6},
    ])
    class FakeVLM:
        def describe(self, frames, prompt):
            return next(results)
    frames = [object(), object()]  # 占位，FakeVLM 不真正读图
    va = vlm_visual_analysis(frames, FakeVLM())
    # 风险词从严：刀 保留
    assert "刀" in va.objects
    # people 取最大
    assert va.people_count == 2
    # quality 取均值
    assert abs(va.visual_quality - 0.5) < 1e-6
    # description 拼接两帧
    assert "第一帧" in va.description and "第二帧" in va.description


def test_vlm_visual_analysis_single_frame_failure_skips():
    from app.analyzer.visual import vlm_visual_analysis
    calls = {"n": 0}
    class FakeVLM:
        def describe(self, frames, prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return {"description": "ok", "objects": [], "actions": [],
                    "environment": "", "shot_type": "medium",
                    "camera_motion": "static", "people_count": 0,
                    "visual_quality": 0.5}
    va = vlm_visual_analysis([object(), object()], FakeVLM())
    assert "ok" in va.description
    assert calls["n"] == 2


def test_vlm_visual_analysis_bad_people_count_skips():
    from app.analyzer.visual import vlm_visual_analysis
    results = iter([
        {"description": "帧一", "objects": [], "actions": [],
         "environment": "", "shot_type": "medium", "camera_motion": "static",
         "people_count": "约3人", "visual_quality": 0.5},
        {"description": "帧二", "objects": [], "actions": [],
         "environment": "", "shot_type": "medium", "camera_motion": "static",
         "people_count": 2, "visual_quality": 0.5},
    ])
    class FakeVLM:
        def describe(self, frames, prompt):
            return next(results)
    va = vlm_visual_analysis([object(), object()], FakeVLM())
    assert va.people_count == 2
    assert "帧一" in va.description and "帧二" in va.description
