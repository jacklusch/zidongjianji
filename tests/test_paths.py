import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.utils.paths import project_root, ensure_dirs
from app.utils.hashing import sha256_file
from app.utils.logging import setup_logging

def test_project_root_is_repo():
    assert (project_root() / "requirements.txt").exists()

def test_ensure_dirs_creates(tmp_path):
    d1 = tmp_path / "a" / "b"
    ensure_dirs([d1])
    assert d1.is_dir()

def test_sha256_stable(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    assert sha256_file(f) == sha256_file(f)
    assert len(sha256_file(f)) == 64

def test_setup_logging_creates_file(tmp_path):
    log = setup_logging(tmp_path, "test")
    log.info("hi")
    assert any(tmp_path.iterdir())