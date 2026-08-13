import json
import sqlite3
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    rel_path TEXT NOT NULL,
    duration REAL, width INTEGER, height INTEGER, fps REAL,
    codec TEXT, audio INTEGER, size INTEGER,
    hash TEXT, mtime REAL, indexed_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS shots (
    shot_id TEXT PRIMARY KEY,
    media_id INTEGER NOT NULL REFERENCES media(id),
    start REAL, end REAL, duration REAL,
    analysis_version TEXT, analysis_method TEXT
);
CREATE TABLE IF NOT EXISTS visual_analysis (
    shot_id TEXT PRIMARY KEY REFERENCES shots(shot_id),
    description TEXT, objects TEXT, actions TEXT, environment TEXT,
    shot_type TEXT, camera_motion TEXT, people_count INTEGER,
    visual_quality REAL, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shot_id TEXT NOT NULL REFERENCES shots(shot_id),
    seg_index INTEGER, start REAL, end REAL, text TEXT, speaker TEXT,
    UNIQUE(shot_id, seg_index)
);
CREATE TABLE IF NOT EXISTS embeddings (
    shot_id TEXT PRIMARY KEY REFERENCES shots(shot_id),
    model TEXT, dim INTEGER, vector_json TEXT, text TEXT
);
"""

class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def table_names(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return [r["name"] for r in rows]

    def upsert_media(self, filename, rel_path, duration, width, height, fps,
                     codec, audio, size, hash, mtime=0.0, path=None) -> int:
        path = path or str((Path(rel_path)))
        cur = self.conn.execute(
            """INSERT INTO media (filename,path,rel_path,duration,width,height,fps,codec,audio,size,hash,mtime)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET
                 filename=excluded.filename, duration=excluded.duration, width=excluded.width,
                 height=excluded.height, fps=excluded.fps, codec=excluded.codec, audio=excluded.audio,
                 size=excluded.size, hash=excluded.hash, mtime=excluded.mtime
               RETURNING id""",
            (filename, path, rel_path, duration, width, height, fps, codec,
             int(audio), size, hash, mtime))
        row = cur.fetchone()
        self.conn.commit()
        return row["id"]

    def get_media_by_path(self, rel_path: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM media WHERE rel_path=?", (rel_path,)).fetchone()
        return dict(row) if row else None

    def get_all_media(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM media")]

    def upsert_shot(self, shot_id, media_id, start, end, duration,
                    analysis_version, analysis_method) -> None:
        self.conn.execute(
            """INSERT INTO shots (shot_id,media_id,start,end,duration,analysis_version,analysis_method)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(shot_id) DO UPDATE SET start=excluded.start, end=excluded.end,
                 duration=excluded.duration, analysis_method=excluded.analysis_method""",
            (shot_id, media_id, start, end, duration, analysis_version, analysis_method))
        self.conn.commit()

    def get_shots_by_media(self, media_id: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM shots WHERE media_id=? ORDER BY start", (media_id,))]

    def get_all_shots(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT s.*, m.rel_path as source FROM shots s JOIN media m ON m.id=s.media_id ORDER BY s.start")]

    def delete_shots_for_media(self, media_id: int) -> None:
        for sid in self.conn.execute("SELECT shot_id FROM shots WHERE media_id=?", (media_id,)):
            self.conn.execute("DELETE FROM visual_analysis WHERE shot_id=?", (sid["shot_id"],))
            self.conn.execute("DELETE FROM transcripts WHERE shot_id=?", (sid["shot_id"],))
            self.conn.execute("DELETE FROM embeddings WHERE shot_id=?", (sid["shot_id"],))
        self.conn.execute("DELETE FROM shots WHERE media_id=?", (media_id,))
        self.conn.commit()

    def delete_media(self, rel_path: str) -> None:
        m = self.get_media_by_path(rel_path)
        if m:
            self.delete_shots_for_media(m["id"])
            self.conn.execute("DELETE FROM media WHERE id=?", (m["id"],))
            self.conn.commit()

    def upsert_visual(self, shot_id, description, objects, actions, environment,
                      shot_type, camera_motion, people_count, visual_quality, raw_json):
        self.conn.execute(
            """INSERT INTO visual_analysis (shot_id,description,objects,actions,environment,shot_type,camera_motion,people_count,visual_quality,raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(shot_id) DO UPDATE SET description=excluded.description,
                 objects=excluded.objects, actions=excluded.actions, environment=excluded.environment,
                 shot_type=excluded.shot_type, camera_motion=excluded.camera_motion,
                 people_count=excluded.people_count, visual_quality=excluded.visual_quality,
                 raw_json=excluded.raw_json""",
            (shot_id, description, json.dumps(objects, ensure_ascii=False),
             json.dumps(actions, ensure_ascii=False), environment, shot_type,
             camera_motion, people_count, visual_quality, raw_json))
        self.conn.commit()

    def get_visual(self, shot_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM visual_analysis WHERE shot_id=?", (shot_id,)).fetchone()
        return dict(row) if row else None

    def upsert_transcript(self, shot_id, seg_index, start, end, text, speaker=""):
        self.conn.execute(
            """INSERT INTO transcripts (shot_id,seg_index,start,end,text,speaker) VALUES (?,?,?,?,?,?)
               ON CONFLICT(shot_id, seg_index) DO UPDATE SET
                 start=excluded.start, end=excluded.end, text=excluded.text, speaker=excluded.speaker""",
            (shot_id, seg_index, start, end, text, speaker))
        self.conn.commit()

    def get_transcripts(self, shot_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM transcripts WHERE shot_id=? ORDER BY start", (shot_id,))]

    def upsert_embedding(self, shot_id, model, dim, vector, text):
        self.conn.execute(
            """INSERT INTO embeddings (shot_id,model,dim,vector_json,text) VALUES (?,?,?,?,?)
               ON CONFLICT(shot_id) DO UPDATE SET model=excluded.model, dim=excluded.dim,
                 vector_json=excluded.vector_json, text=excluded.text""",
            (shot_id, model, dim, json.dumps(vector), text))
        self.conn.commit()

    def get_all_embeddings(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM embeddings")]

    def close(self):
        self.conn.close()