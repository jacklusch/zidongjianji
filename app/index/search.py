import json
import math
from app.index.database import Database
from app.index.embeddings import build_corpus, shot_search_text

def _tokenize(text: str) -> list[str]:
    import re
    # 保留中英文字符序列，转为小写
    return [t.lower() for t in re.findall(r"[\u4e00-\u9fff\w]+", text or "")]

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
        # 命中文档可能出现负分（rank_bm25 对出现在半数以上文档的词做 idf 下限），故用 != 0 过滤
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