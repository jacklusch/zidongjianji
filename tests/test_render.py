from pathlib import Path
from app.editors.renderer import render_plan
from app.utils.process import run


def test_render_plan(tmp_path, sample_video, ffmpeg, ffprobe):
    plan = {"version": 1, "project": "demo", "source_script": "x",
            "timeline": [{"script_id": 1, "source": str(sample_video), "in": 0.0,
                          "out": 2.0, "duration": 2.0, "reason": "r", "confidence": 0.9, "reused": False}],
            "missing": [], "warnings": []}
    out = render_plan(plan, tmp_path / "out.mp4", ffmpeg=ffmpeg,
                      width=320, height=180, fps=24)
    assert out.exists()
    assert out.stat().st_size > 0
