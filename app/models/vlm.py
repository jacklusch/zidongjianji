import json
import re
from pathlib import Path
from app.models.base import ModelProvider

_llm_cache = {}
_llm_loaded_for = None

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

def get_gguf_llm(model_path: str, device: str = "auto"):
    """模块级单例：同一 GGUF 只加载一次（VLM 与 reranker 复用）。"""
    global _llm_cache, _llm_loaded_for
    key = f"{model_path}|{device}"
    if key == _llm_loaded_for and key in _llm_cache:
        return _llm_cache[key]
    from app.models.device import DeviceManager
    dev = DeviceManager(device)
    n_gpu = -1 if dev.resolve() == "cuda" else 0
    try:
        from llama_cpp import Llama
    except ImportError as e:
        raise RuntimeError("未安装 llama-cpp-python，请先 pip install -r requirements-models.txt") from e
    if not Path(model_path).exists():
        raise RuntimeError(f"模型文件不存在: {model_path}")
    llm = Llama(model_path=str(model_path), n_gpu_layers=n_gpu, verbose=False)
    _llm_cache[key] = llm
    _llm_loaded_for = key
    return llm

class VLM(ModelProvider):
    name = "vlm"
    def __init__(self, provider="none", model="", device="auto", base_url="", api_key=""):
        super().__init__(provider, model, device, base_url, api_key)
    def describe(self, frames, prompt: str) -> dict:
        if not self.available():
            raise RuntimeError("VLM 未启用（provider=none）")
        if self.provider == "openai":
            return self._describe_openai(frames, prompt)
        llm = get_gguf_llm(self.model, self.device)
        import tempfile, os
        # frames 为图像 ndarray 列表：暂存首帧为临时图并交给多模态 GGUF 推理
        # llama.cpp 多模态在 Python 绑定中用 chat 接口（需内置 mmproj），此处走文本协议
        if frames:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            import cv2
            cv2.imwrite(tmp.name, frames[0])
            tmp.close()
            try:
                out = llm.create_chat_completion(
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"file://{tmp.name}"}},
                        {"type": "text", "text": prompt},
                    ]}],
                )
            finally:
                os.unlink(tmp.name)
        else:
            out = llm(prompt)
        choice = out["choices"][0] if out.get("choices") else {}
        raw = choice.get("message", {}).get("content") if isinstance(choice.get("message"), dict) else choice.get("text", out.get("content", ""))
        return parse_vlm_json(raw)
    def _describe_openai(self, frames, prompt: str) -> dict:
        from openai import OpenAI
        import tempfile, os, cv2, base64
        key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("未配置 VLM api_key")
        client = OpenAI(base_url=self.base_url or None, api_key=key)
        if frames:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frames[0])
            tmp.close()
            try:
                with open(tmp.name, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
            finally:
                os.unlink(tmp.name)
            content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                       {"type": "text", "text": prompt}]
        else:
            content = prompt
        resp = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": content}])
        return parse_vlm_json(resp.choices[0].message.content)
