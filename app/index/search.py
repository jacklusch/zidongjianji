import json
import math
from app.index.database import Database
from app.index.embeddings import build_corpus, shot_search_text

def _tokenize(text: str) -> list[str]:
    import re
    # 中文用 jieba 分词，英文/数字保持完整词，统一小写
    toks = []
    for seg in re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+", text or ""):
        if seg and seg[0] >= "\u4e00":
            try:
                import jieba
                toks.extend(t for t in jieba.lcut(seg) if t.strip())
            except ImportError:
                toks.append(seg)
        else:
            toks.append(seg.lower())
    return toks

class SearchBackend:
    def __init__(self, settings, rebuild=True):
        self.settings = settings
        self.corpus = build_corpus(settings) if rebuild else _load_corpus(settings)
        self._build_index()

    def _build_index(self):
        from rank_bm25 import BM25Okapi
        self.ids = [sid for sid, _ in self.corpus]
        self.bm25 = BM25Okapi([_tokenize(t) for _, t in self.corpus]) if self.corpus else None

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        toks = _tokenize(query)
        if not toks or self.bm25 is None:
            return []
        scores = self.bm25.get_scores(toks)
        ranked = sorted(zip(self.ids, scores), key=lambda x: -x[1])
        # 优先返回正分命中；无正分时（如单文档语料 idf 退化）保留排序靠前的候选
        positive = [(sid, float(s)) for sid, s in ranked[:top_k] if s > 0]
        if positive:
            return positive
        return [(sid, float(s)) for sid, s in ranked[:top_k] if s != 0]

def _load_corpus(settings):
    db = Database(settings.footage_db)
    outs = []
    for sh in db.get_all_shots():
        va = db.get_visual(sh["shot_id"])
        trs = db.get_transcripts(sh["shot_id"])
        outs.append((sh["shot_id"], shot_search_text(sh, va, trs)))
    db.close()
    return outs