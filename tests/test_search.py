import pytest
from app.index.search import SearchBackend
from app.config.settings import load_settings
from app.pipeline.index_pipeline import run_index

def test_search_finds_by_filename(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    import shutil
    mat = tmp_path / "materials"
    mat.mkdir()
    shutil.copy(sample_video, mat / "factory01.mp4")
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", mat)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    run_index(settings, analyze=True)
    backend = SearchBackend(settings)
    hits = backend.search("factory01")
    assert hits and len(hits) >= 1

def test_search_empty_query_returns_no_hits(tmp_path, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    backend = SearchBackend(settings)
    assert backend.search("") == []

def test_search_empty_corpus_safe(tmp_path, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    backend = SearchBackend(settings)
    assert backend.search("factory01") == []