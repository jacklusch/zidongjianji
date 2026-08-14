from app.models.vlm import VLM
from app.models.device import resolve_device

def rerank_candidates(cands, settings, log=None):
    """有 vlm_reranker 时按二次判断重排；无则原样返回。"""
    cfg = settings.vlm_reranker
    if cfg.provider in ("local", "openai"):
        vlm = VLM(cfg.provider, cfg.model, resolve_device(settings, cfg), cfg.base_url, cfg.api_key,
                  memory_fraction=getattr(settings, "gpu_memory_fraction", 0.7))
        # 目前不做实际重排打分，仅确保模型可加载并保留候选（模型接入任务细化排序）
        if log:
            log.info("vlm_reranker 已启用（provider=%s），候选保留原序", cfg.provider)
    return cands
