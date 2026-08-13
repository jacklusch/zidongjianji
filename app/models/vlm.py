import json
import re
from app.models.base import ModelProvider

def vlm_repair_json(raw: str) -> str:
    s = raw[raw.find("{"):] if "{" in raw else raw
    if not s:
        raise ValueError("输出中不包含 JSON")
    s = re.sub(r'[\x00-\x1f]', ' ', s)
    open_cnt = s.count("{") + s.count("[")
    close_cnt = s.count("}") + s.count("]")
    s += "}" * max(0, open_cnt - close_cnt)
    return s

def parse_vlm_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(vlm_repair_json(raw))

class VLM(ModelProvider):
    name = "vlm"
    def __init__(self, provider="none", model="", device="auto"):
        super().__init__(provider, model, device)
    def describe(self, frames, prompt: str) -> dict:
        if not self.available():
            raise RuntimeError("VLM 未启用（provider=none）")
        from transformers import AutoModelForVision2Seq, AutoProcessor  # noqa
        raise NotImplementedError("需安装 transformers + qwen 模型后在本地实现；主流程使用 fallback")
