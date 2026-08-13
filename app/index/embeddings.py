from app.index.database import Database
from app.models.embedding import Embedder

def shot_search_text(shot: dict, va: dict | None, trs: list[dict]) -> str:
    parts = [shot.get("source", "")]
    if va:
        parts += [va.get("description", ""), " ".join(_as_list(va.get("objects"))),
                  " ".join(_as_list(va.get("actions"))), va.get("environment", "")]
    for t in trs:
        parts.append(t.get("text", ""))
    return " ".join(p for p in parts if p)

def _as_list(v) -> list:
    import json
    if isinstance(v, str):
        v = json.loads(v) if v else []
    return v if isinstance(v, list) else []

def build_corpus(settings) -> list[tuple[str, str]]:
    """返回 [(shot_id, text)]；并在可用时写入 embeddings 表。"""
    db = Database(settings.footage_db)
    shots = db.get_all_shots()
    emb = Embedder(settings.embedding.provider, settings.embedding.model, settings.embedding.device)
    rows = []
    for sh in shots:
        va = db.get_visual(sh["shot_id"])
        trs = db.get_transcripts(sh["shot_id"])
        text = shot_search_text(sh, va, trs)
        rows.append((sh["shot_id"], text))
    if emb.available():
        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]
        vecs = emb.embed(texts)
        if vecs:
            for sid, v in zip(ids, vecs):
                db.upsert_embedding(sid, emb.model if emb.model else "local", len(v), v, "")
    db.close()
    return rows