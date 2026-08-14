import os
import shutil
import subprocess

def _has_nvidia_smi() -> bool:
    return shutil.which("nvidia-smi") is not None

def _query_gpu() -> dict:
    """返回 {name, total_mb, free_mb}；失败返回空 dict。"""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return {}
        parts = out.stdout.strip().split(",")
        if len(parts) >= 3:
            return {"name": parts[0].strip(), "total_mb": int(parts[1].strip()), "free_mb": int(parts[2].strip())}
    except Exception:
        pass
    return {}

def _torch_cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False

def _llama_gpu_offload() -> bool:
    try:
        from llama_cpp import llama_cpp
        return bool(getattr(llama_cpp, "llama_supports_gpu_offload", lambda: False)())
    except Exception:
        return False

class DeviceManager:
    def __init__(self, device: str = "auto"):
        self.device = device

    def resolve_cuda_support(self) -> dict:
        """检测 CUDA 可用性：torch + llama.cpp GPU + nvidia-smi 三者。"""
        return {
            "cuda": _torch_cuda_available() and _llama_gpu_offload() and _has_nvidia_smi(),
            "gpu": _query_gpu(),
            "driver": None,
        }

    def resolve(self) -> str:
        if self.device in ("cuda", "rocm"):
            return self.device
        if self.device == "auto":
            if self.resolve_cuda_support()["cuda"]:
                return "cuda"
        return "cpu"

    def select_device(self, estimate_bytes: int, total_layers: int = 40, memory_fraction: float = 0.7):
        """按显存预算决定 (device, n_gpu_layers)。显存不足或非 CUDA 回退 CPU。

        estimate_bytes 为模型主体估算大小；返回 ("cpu", 0) 或 ("cuda", layers)。
        """
        if self.device == "off":
            return "cpu", 0
        if self.device not in ("auto", "cuda"):
            return "cpu", 0
        info = self.resolve_cuda_support()
        if not info["cuda"]:
            return "cpu", 0
        free_mb = info["gpu"].get("free_mb", 0)
        budget_bytes = free_mb * 1024 * 1024 * memory_fraction
        if budget_bytes < estimate_bytes / 2:
            return "cpu", 0
        per_layer = estimate_bytes / max(total_layers, 1)
        layers = int(budget_bytes // per_layer)
        layers = max(1, min(total_layers, layers))
        return "cuda", layers
