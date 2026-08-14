import json
import logging
import re
from pathlib import Path
from app.models.base import ModelProvider

log = logging.getLogger("vlm")

_llm_cache = {}

def vlm_repair_json(raw: str) -> str:
    s = raw[raw.find("{"):] if "{" in raw else raw
    if not s:
        raise ValueError("输出中不包含 JSON")
    s = re.sub(r'[\x00-\x1f]', ' ', s)
    open_cnt = s.count("{") + s.count("[")
    close_cnt = s.count("}") + s.count("]")
    s += "}" * max(0, open_cnt - close_cnt)
    return s


def _extract_json_object(raw: str) -> str:
    """提取第一个最外层完整的 JSON 对象（容忍前后附加文本）。"""
    start = raw.find("{")
    if start == -1:
        return raw
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return raw[start:]


def parse_vlm_json(raw: str) -> dict:
    if isinstance(raw, str):
        attempts = [raw, vlm_repair_json(raw), _extract_json_object(raw)]
        for candidate in attempts:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise ValueError(f"VLM 输出无法解析为 JSON: {raw[:200]}")
    return raw

def _find_mmproj(directory: Path, main_name: str = ""):
    files = sorted(directory.glob("mmproj-*.gguf"))
    if not files:
        return None
    if main_name:
        stem = main_name.rsplit(".", 1)[0]  # 如 Qwen3VL-4B-Instruct-Q4_K_M
        base = stem.split("-Q4_")[0] if "-Q4_" in stem else stem  # Qwen3VL-4B-Instruct
        for f in files:
            if base and base in f.name:
                return f
    return files[0]

def _resolve_gguf_paths(model_path: str):
    """把 model_path（.gguf 文件或目录）解析为 (主模型文件, mmproj 或 None)。"""
    p = Path(model_path)
    if not p.exists():
        raise RuntimeError(f"模型不存在: {model_path}")
    if p.is_file():
        return p, _find_mmproj(p.parent, p.name)
    files = sorted(p.glob("*.gguf"))
    if not files:
        raise RuntimeError(f"目录中未找到 .gguf 文件: {model_path}")
    mmproj = [f for f in files if f.name.startswith("mmproj")]
    mains = [f for f in files if not f.name.startswith("mmproj")]
    if not mains:
        raise RuntimeError(f"目录中未找到主模型 .gguf（仅含 mmproj）: {model_path}")
    def rank(f):
        name = f.name.lower()
        return (0 if "q4" in name else 1, -f.stat().st_size)
    main = sorted(mains, key=rank)[0]
    return main, _find_mmproj(p, main.name) if mmproj else (main, None)

def get_gguf_llm(model_path: str, device: str = "auto", memory_fraction: float = 0.7):
    """模块级单例：同一 GGUF 只加载一次（VLM 与 reranker 复用）。

    返回 (llm, mmproj_path 或 None)。model_path 可为目录，自动 glob 出主
    模型（优先含 q4 量化名、其次最大，mmproj-* 除外）与多模态 mmproj。
    """
    global _llm_cache
    key = f"{model_path}|{device}|{memory_fraction}"
    if key in _llm_cache:
        return _llm_cache[key]
    try:
        from llama_cpp import Llama
    except ImportError as e:
        raise RuntimeError("未安装 llama-cpp-python，请先 pip install -r requirements-models.txt") from e
    main_path, mmproj_path = _resolve_gguf_paths(model_path)
    from app.models.device import DeviceManager
    dev = DeviceManager(device)
    # 显存感知：按主模型大小估算 GPU 层数
    resolved = dev.resolve()
    if resolved == "cuda":
        n_gpu = dev.select_device(estimate_bytes=main_path.stat().st_size,
                                  total_layers=40, memory_fraction=memory_fraction)[1]
    else:
        n_gpu = 0
    log.info("GGUF 设备决策 model=%s device=%s n_gpu_layers=%d memory_fraction=%.2f",
             main_path.name, resolved, n_gpu, memory_fraction)
    kwargs = {"model_path": str(main_path), "n_gpu_layers": n_gpu, "verbose": False}
    if mmproj_path is not None:
        kwargs["mmproj"] = str(mmproj_path)
    try:
        llm = Llama(**kwargs)
    except Exception as e:
        if n_gpu > 0:
            log.warning("GPU 加载失败，回退 CPU: %s", e)
            kwargs["n_gpu_layers"] = 0
            llm = Llama(**kwargs)
            log.info("llama.cpp 已在 CPU 重载（n_gpu_layers=0）")
        else:
            raise
    _llm_cache[key] = (llm, mmproj_path)
    return llm, mmproj_path

class VLM(ModelProvider):
    name = "vlm"
    def __init__(self, provider="none", model="", device="auto", base_url="", api_key="", memory_fraction: float = 0.7):
        super().__init__(provider, model, device, base_url, api_key)
        self.memory_fraction = memory_fraction
    def describe(self, frames, prompt: str) -> dict:
        if not self.available():
            raise RuntimeError("VLM 未启用（provider=none）")
        if self.provider == "openai":
            return self._describe_openai(frames, prompt)
        llm, mmproj_path = get_gguf_llm(self.model, self.device, memory_fraction=self.memory_fraction)
        import tempfile, os
        # 确定性推理：零温度消除随机幻觉，top_p=1 全量采样，max_tokens 上限约束
        _det = {"temperature": 0.0, "top_p": 1.0, "max_tokens": 700}
        # frames 为图像 ndarray 列表：多模态 GGUF 推理需内置 mmproj，无则降级纯文本
        if frames and mmproj_path is not None:
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
                    **_det,
                )
            finally:
                os.unlink(tmp.name)
        else:
            out = llm(prompt, **_det)
        choice = out["choices"][0] if out.get("choices") else {}
        raw = choice.get("message", {}).get("content") if isinstance(choice.get("message"), dict) else choice.get("text", out.get("content", ""))
        return parse_vlm_json(raw)
    def _describe_openai(self, frames, prompt: str) -> dict:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("未安装 openai SDK（pip install openai）") from e
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
