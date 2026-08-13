def rerank_candidates(cands, settings, log=None):
    """有 vlm_reranker 时按二次判断重排；无则原样返回。"""
    cfg = settings.vlm_reranker
    # 本阶段 vlm 未启用时直接原样（模型路径留待模型接入）
    return cands
