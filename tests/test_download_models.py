import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_models import MODELS, source_id, resolve_target, download_all

def test_model_list_complete():
    assert set(MODELS.keys()) == {"vlm", "asr", "embedding"}
    assert MODELS["embedding"]["hf"] == "BAAI/bge-small-zh-v1.5"
    assert MODELS["embedding"]["ms"] == "AI-ModelScope/bge-small-zh-v1.5"

def test_source_id_mapping():
    assert source_id("embedding", "hf") == "BAAI/bge-small-zh-v1.5"
    assert source_id("embedding", "ms") == "AI-ModelScope/bge-small-zh-v1.5"

def test_resolve_target(tmp_path):
    target = resolve_target(tmp_path, "embedding", "AI-ModelScope/bge-small-zh-v1.5")
    assert target == tmp_path / "models" / "embedding"

def test_download_all_selects_source(tmp_path, monkeypatch):
    calls = []
    def fake_snapshot_hf(repo_id, local_dir):
        calls.append(("hf", repo_id, local_dir))
        (local_dir / "x.txt").write_text("ok")
    monkeypatch.setattr("scripts.download_models.snapshot_hf", fake_snapshot_hf)
    rep = download_all(tmp_path, sources="hf", models=["embedding"], install=False)
    assert rep["embedding"] is True
    assert calls[0][:2] == ("hf", "BAAI/bge-small-zh-v1.5")
