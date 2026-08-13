from pathlib import Path
from app.config.settings import load_settings
from app.pipeline.index_pipeline import run_index
from app.pipeline.matching_pipeline import run_plan
from app.pipeline.render_pipeline import run_render


def test_build_end_to_end(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "projects_dir", tmp_path / "data" / "projects")
    monkeypatch.setattr(settings, "output_dir", tmp_path / "data" / "output")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    script = tmp_path / "demo.md"
    script.write_text("开头展示 视频镜头。\n然后展示 画面亮度。\n", encoding="utf-8")
    run_index(settings, analyze=True)
    plan = run_plan(settings, script, project="demo")
    preview, final = run_render(settings, plan)
    assert preview.exists() and final.exists()
    assert final.stat().st_size > 0
    plan_json = plan.read_text(encoding="utf-8")
    assert "timeline" in plan_json and "missing" in plan_json
