import pytest
from app.config.settings import load_settings
from app.pipeline.index_pipeline import run_index
from app.matching.retriever import retrieve_top_k
from app.matching.matcher import select_best
from app.script.schema import ScriptSegment

def _setup(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    return settings

SEG = ScriptSegment(id=1, script_text="视频镜头", visual_requirements=["镜头"], duration=4.0)

def test_retrieve_and_select(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = _setup(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch)
    run_index(settings, analyze=True)
    cands = retrieve_top_k(settings, SEG, top_k=10)
    assert len(cands) >= 1
    chosen = select_best(cands, settings, log=None)
    assert chosen is not None
    assert chosen.score > 0
