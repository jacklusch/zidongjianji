import pytest
from app.index.database import Database

@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "index.db")

def test_schema_created(db):
    tables = db.table_names()
    assert {"media", "shots", "visual_analysis", "transcripts", "embeddings"} <= set(tables)

def test_upsert_media_and_read(db):
    m = db.upsert_media("factory_001.mp4", "materials/factory_001.mp4", 6.0, 640, 360, 30.0, "h264", True, 1234, "abc123")
    got = db.get_media_by_path("materials/factory_001.mp4")
    assert got is not None and got["hash"] == "abc123"

def test_shots_roundtrip(db):
    db.upsert_media("m.mp4", "materials/m.mp4", 6.0, 640, 360, 30.0, "h264", True, 1, "h1")
    mid = db.get_media_by_path("materials/m.mp4")["id"]
    db.upsert_shot("m_001", mid, 0.0, 3.0, 3.0, "v1", "fallback")
    shots = db.get_shots_by_media(mid)
    assert shots[0]["shot_id"] == "m_001"

def test_visual_and_transcript_roundtrip(db):
    db.upsert_media("m.mp4", "materials/m.mp4", 6.0, 640, 360, 30.0, "h264", True, 1, "h1")
    mid = db.get_media_by_path("materials/m.mp4")["id"]
    db.upsert_shot("m_001", mid, 0.0, 3.0, 3.0, "v1", "fallback")
    db.upsert_visual("m_001", "工人在流水线上", ["person"], ["operation"], "factory", "medium", "static", 1, 0.9, "{}")
    va = db.get_visual("m_001")
    assert va["description"] == "工人在流水线上"
    db.upsert_transcript("m_001", 0, 0.0, 1.0, "你好")
    tr = db.get_transcripts("m_001")
    assert tr[0]["text"] == "你好"