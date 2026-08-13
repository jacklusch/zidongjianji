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
            # paraformer 返回 list[dict]：{"key","text","timestamp": [[s,e], ...]}
            segs = []
            for r in res:
                text = r.get("text", "")
                ts = r.get("timestamp") or []
                if not ts:
                    segs.append({"start": 0.0, "end": 0.0, "text": text})
                    continue
                for (s, e), word in zip(ts, _split_words(text, len(ts))):
                    segs.append({"start": float(s) / 1000.0, "end": float(e) / 1000.0, "text": word})
            return segs
        except Exception as e:
            raise RuntimeError(f"FunASR 转写失败: {e}") from e

def _split_words(text: str, n: int) -> list[str]:
    """把整句按 timestamp 段数粗略切分（paraformer 无逐词 text 时兜底）。"""
    if n <= 1:
        return [text]
    chars = list(text)
    seg = max(1, len(chars) // n)
    return ["".join(chars[i * seg:(i + 1) * seg]) for i in range(n)]
