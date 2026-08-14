from app.models.base import ModelProvider
import logging

log = logging.getLogger("embedding")

class Embedder(ModelProvider):
    name = "embedding"
    def __init__(self, provider="none", model="", device="auto"):
        super().__init__(provider, model, device)

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if not self.available():
            return None
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            from app.models.device import DeviceManager
            dev = DeviceManager(self.device)
            resolved = dev.resolve()
            log.info("Embedding 设备决策 device=%s", resolved)
            m = SentenceTransformer(self.model)
            v = m.encode(texts, device=resolved, convert_to_numpy=True)
            return [list(x) for x in v]
        except Exception as e:
            raise RuntimeError(f"Embedding 失败: {e}") from e
