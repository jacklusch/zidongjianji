import shutil
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

def test_run_index_failed_file_does_not_abort(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    import app.index.footage_index as fi
    other = sample_video.parent / "other.mp4"
    shutil.copy(sample_video, other)
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    real = fi.detect_shots
    def fake(path, *a, **k):
        if path.endswith("other.mp4"):
            raise RuntimeError("boom")
        return real(path, *a, **k)
    monkeypatch.setattr(fi, "detect_shots", fake)
    report = run_index(settings)
    assert report["failed"] == 1
    assert report["media"] == 1
    assert report["shots"] >= 1