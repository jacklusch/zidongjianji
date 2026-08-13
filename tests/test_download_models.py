import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
from scripts.download_models import MODELS, source_id, resolve_target, download_all, write_config

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

def test_write_config_updates_success_only(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump({
        "models": {
            "vlm": {"provider": "none", "model": "", "device": "auto"},
            "asr": {"provider": "none", "model": "", "device": "auto"},
            "embedding": {"provider": "none", "model": "", "device": "auto"},
        },
        "video": {"width": 1280, "height": 720},
    }, allow_unicode=True), encoding="utf-8")
    report = {"vlm": True, "asr": False, "embedding": True}
    write_config(tmp_path, report)
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    m = raw["models"]
    assert m["vlm"]["provider"] == "local"
    assert m["vlm"]["model"] == str(tmp_path / "models" / "vlm")
    assert m["embedding"]["provider"] == "local"
    assert m["embedding"]["model"] == str(tmp_path / "models" / "embedding")
    assert m["asr"]["provider"] == "none"
    assert m["asr"]["model"] == ""
    assert raw["video"] == {"width": 1280, "height": 720}
