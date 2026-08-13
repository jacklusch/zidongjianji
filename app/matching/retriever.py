from dataclasses import dataclass
from app.index.search import SearchBackend
from app.index.database import Database

@dataclass
class CandidateShot:
    shot_id: str
    source: str
    start: float
    end: float
    duration: float
    similarity: float
    visual_quality: float = 0.5
    reason: str = ""

def retrieve_top_k(settings, segment, top_k: int = 20) -> list[CandidateShot]:
    q = segment.script_text + " " + " ".join(segment.visual_requirements)
    backend = SearchBackend(settings)
    db = Database(settings.footage_db)
    shots = {s["shot_id"]: s for s in db.get_all_shots()}
    out = []
    for sid, sim in backend.search(q, top_k=top_k):
        sh = shots.get(sid)
        if not sh:
            continue
        va = db.get_visual(sid)
        out.append(CandidateShot(
            shot_id=sid, source=sh.get("source", ""), start=sh.get("start", 0.0),
            end=sh.get("end", 0.0), duration=sh.get("duration", 0.0),
            similarity=sim,
            visual_quality=float(va["visual_quality"]) if va else 0.5,
            reason=f"语义检索相似度 {sim:.3f}"))
    db.close()
    return out
