import pytest
from app.config.settings import load_settings
from app.pipeline.index_pipeline import run_index

def test_run_index_new_files(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    report = run_index(settings)
    assert report["media"] >= 1
    assert report["shots"] >= 1

def test_run_index_idempotent(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    r1 = run_index(settings)
    r2 = run_index(settings)
    assert r2["new"] == 0 and r2["changed"] == 0