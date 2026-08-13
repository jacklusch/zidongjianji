from pathlib import Path
from app.models.base import ModelProvider

class ASR(ModelProvider):
    name = "asr"
    def __init__(self, provider="none", model="", device="auto", base_url="", api_key=""):
        super().__init__(provider, model, device, base_url, api_key)

    def transcribe(self, audio_path: str) -> list[dict]:
        if not self.available():
            return []
        try:
            from funasr import AutoModel
            model = AutoModel(model=self.model)
            res = model.generate(input=str(audio_path))
            # paraformer 返回 list[dict]：{"key","text","timestamp"}（timestamp 需 VAD+punc 模型）
            segs = []
            for r in res:
                text = (r.get("text") or "").strip()
                if not text:
                    continue
                ts = r.get("timestamp") or []
                if not ts:
                    segs.append({"start": 0.0, "end": 0.0, "text": text})
                    continue
                for (s, e) in ts:
                    segs.append({"start": float(s) / 1000.0, "end": float(e) / 1000.0,
                                 "text": text})
            return segs
        except Exception as e:
            raise RuntimeError(f"FunASR 转写失败: {e}") from e
