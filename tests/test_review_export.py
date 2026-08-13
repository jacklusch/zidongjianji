import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.index.database import Database
from app.index.review_export import export_visual_review

def test_export_visual_review_creates_markdown(tmp_path, monkeypatch):
    db = Database(tmp_path / "index.db")
    db.upsert_media("factory01.mp4", "factory01.mp4", 10.0, 1920, 1080, 30.0,
                    "h264", 1, 1000, "abc123", 1.0)
    mid = db.get_media_by_path("factory01.mp4")["id"]
    db.upsert_shot("factory01_001", mid, 0.0, 4.0, 4.0, "v1", "scenedetect")
    db.upsert_visual("factory01_001", "视频镜头，画面亮度 0.5", ["person"], ["walking"],
                     "工厂", "medium", "static", 2, 0.7, "{}")
    db.close()

    class FakeSettings:
        footage_dir = tmp_path
        footage_db = tmp_path / "index.db"
        thumbnails_dir = tmp_path / "thumbnails"

    out = export_visual_review(FakeSettings())
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "|" in content
    assert "factory01_001" in content
    assert "视频镜头" in content
    assert "walking" in content
    assert "factory01.mp4" in content

def test_export_visual_review_empty_db(tmp_path):
    db = Database(tmp_path / "index.db")
    db.close()
    class FakeSettings:
        footage_dir = tmp_path
        footage_db = tmp_path / "index.db"
        thumbnails_dir = tmp_path / "thumbnails"
    out = export_visual_review(FakeSettings())
    assert out.exists()
    assert "|" in out.read_text(encoding="utf-8")
