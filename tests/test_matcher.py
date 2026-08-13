import pytest
from app.config.settings import load_settings
from app.pipeline.index_pipeline import run_index
from app.matching.retriever import retrieve_top_k
from app.matching.matcher import select_best
from app.script.schema import ScriptSegment
from app.matching.reranker import rerank_candidates
from app.matching.retriever import CandidateShot

def _setup(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    monkeypatch.setattr(settings, "vlm", type("MC", (), {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""})())
    monkeypatch.setattr(settings, "embedding", type("MC", (), {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""})())
    monkeypatch.setattr(settings, "asr", type("MC", (), {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""})())
    return settings

SEG = ScriptSegment(id=1, script_text="视频镜头", visual_requirements=["镜头"], duration=4.0)

def test_rerank_no_vlm_returns_same(tmp_path, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "vlm_reranker", type("MC", (), {"provider": "none", "model": "", "device": "auto"})())
    cands = [CandidateShot(shot_id="a", source="x", start=0.0, end=1.0, duration=1.0, similarity=0.5)]
    assert rerank_candidates(cands, settings) is cands

def test_retrieve_and_select(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = _setup(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch)
    run_index(settings, analyze=True)
    cands = retrieve_top_k(settings, SEG, top_k=10)
    assert len(cands) >= 1
    chosen = select_best(cands, settings, log=None)
    assert chosen is not None
    assert chosen.score > 0
