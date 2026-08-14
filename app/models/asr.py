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
            from app.models.device import DeviceManager
            dev = DeviceManager(self.device)
            model = AutoModel(model=self.model,
                              device="cuda" if dev.resolve() == "cuda" else "cpu")
            res = model.generate(input=str(audio_path))
            segs = []
            for r in res:
                text = (r.get("text") or "").strip()
                if not text:
                    continue
                ts = r.get("timestamp") or []
                if ts:
                    segs.extend(_group_sentences(text, ts))
                else:
                    segs.append({"start": 0.0, "end": 0.0, "text": text})
            return segs
        except Exception as e:
            raise RuntimeError(f"FunASR 转写失败: {e}") from e


def _group_sentences(text: str, ts: list, gap_threshold_ms: int = 350) -> list[dict]:
    """把逐字时间戳按相邻间隔断句，合并为句子级片段。"""
    chars = text.split()
    if not chars:
        return []
    groups = []
    cur_chars = [chars[0]]
    cur_ts = [ts[0]]
    for i in range(1, len(chars)):
        if i >= len(ts):
            break
        gap = ts[i][0] - ts[i - 1][1]
        if gap > gap_threshold_ms:
            groups.append((cur_chars, cur_ts))
            cur_chars = [chars[i]]
            cur_ts = [ts[i]]
        else:
            cur_chars.append(chars[i])
            cur_ts.append(ts[i])
    groups.append((cur_chars, cur_ts))
    segs = []
    for g_chars, g_ts in groups:
        segs.append({
            "start": float(g_ts[0][0]) / 1000.0,
            "end": float(g_ts[-1][1]) / 1000.0,
            "text": "".join(g_chars),
        })
    return segs
