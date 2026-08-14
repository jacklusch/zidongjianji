from pathlib import Path
from app.editors.renderer import render_plan
from app.utils.process import run


def test_pick_video_codec_nvenc_when_available(monkeypatch):
    from app.editors.renderer import _pick_video_codec
    monkeypatch.setattr("app.editors.renderer._probe_nvenc", lambda ffmpeg: True)
    assert _pick_video_codec("ffmpeg") == "h264_nvenc"


def test_pick_video_codec_libx264_when_no_nvenc(monkeypatch):
    from app.editors.renderer import _pick_video_codec
    monkeypatch.setattr("app.editors.renderer._probe_nvenc", lambda ffmpeg: False)
    assert _pick_video_codec("ffmpeg") == "libx264"


def test_render_plan(tmp_path, sample_video, ffmpeg, ffprobe):
    plan = {"version": 1, "project": "demo", "source_script": "x",
            "timeline": [{"script_id": 1, "source": str(sample_video), "in": 0.0,
                          "out": 2.0, "duration": 2.0, "reason": "r", "confidence": 0.9, "reused": False}],
            "missing": [], "warnings": []}
    out = render_plan(plan, tmp_path / "out.mp4", ffmpeg=ffmpeg,
                      width=320, height=180, fps=24)
    assert out.exists()
    assert out.stat().st_size > 0
