# 规格：GPU 自动检测与设备分配

日期：2026-08-13
状态：已批准

## 背景

当前 VLM（llama.cpp）、ASR（FunASR）、Embedding、LLM-local 全部以 CPU 运行（torch 为 CPU 版、llama-cpp 无 CUDA）。目标：自动检测 CUDA → 计算显存 → 显存允许时 GPU 优先，CPU 回退；FFmpeg 检测到 NVENC 时渲染自动切硬件编码。

## 关键事实（已实测）

- GPU：NVIDIA RTX 3060，12GB（空闲 10.5GB）。
- torch 为 CPU 版（`2.13.0+cpu`，`cuda_available: False`）——需重装 CUDA 版。
- llama-cpp-python 0.3.34 编译版无 CUDA（`llama_supports_gpu_offload: False`）——需装 CUDA 预编译版。
- 当前 `bin\ffmpeg` 已支持 NVENC（`h264_nvenc` 可用）。
- `DeviceManager(auto).resolve()` 现因 CPU 版 torch 恒返回 "cpu"。
- `app/models/llm.py` local 路径 `torch.device("auto")` 非法（"auto" 不是合法 torch 设备名）。
- `app/models/asr.py` 的 `AutoModel(model=...)` 未传 device，由 FunASR 默认决定。

## 组件设计

### 1. 依赖安装（`scripts/install.ps1` + `requirements-models.txt`）

- `install.ps1` 检测 GPU（`nvidia-smi` 存在且报驱动版本）：
  - 有 GPU → 装 CUDA 版依赖：`pip install torch==2.13.0+cu121 --index-url https://download.pytorch.org/whl/cu121`、`llama-cpp-python` CUDA 预编译 wheel、`funasr`、`sentence-transformers` 等
  - 无 GPU → 装 CPU 版（现状）
- `requirements-models.txt` 保持 CPU 版基线（GPU 版依赖仅 install.ps1 动态装，避免破坏无 GPU 环境）。
- 新增 `scripts/gpu_check.ps1`（可选）：打印 GPU/驱动/CUDA 可用性诊断。

### 2. `app/models/device.py` — 显存感知设备管理器

- `DeviceManager.resolve()` 扩展（保持向后兼容）：
  - `auto`：检测（a）torch CUDA 可用（b）llama.cpp GPU offload 支持（c）nvidia-smi 存在——三者具备才返回 "cuda"，否则 "cpu"。
  - 新增 `resolve_cuda_support()` → `{"cuda": bool, "driver": str|None, "gpu_name": str|None, "total_mb": int, "free_mb": int}`：用 `nvidia-smi --query-gpu=name,memory.total,memory.free` 解析（无 nvidia-smi 返回 None 字段）。
- 新增 `select_device(estimate_bytes, memory_fraction=0.7)` → `("cuda", n_gpu_layers)` 或 `("cpu", 0)`：
  - 非 CUDA → `("cpu", 0)`。
  - 计算可用显存预算 = `free_mb × memory_fraction`；估算能放多少 llama.cpp 层：`n_gpu_layers = min(总层数, 预算字节 // (estimate_bytes / 总层数))`（estimate_bytes 由调用方按模型量化大小估算）；预算不足装下模型主体 → `("cpu", 0)`。
  - 简化：`estimate_bytes` 不足预算一半 → cpu；否则按比例算层数，最少 1 层（有 GPU 就用部分层加速）。

### 3. 各适配器接入

- `vlm.py get_gguf_llm(model_path, device)`：`n_gpu_layers` 由 `select_device(主模型文件大小)` 计算（主模型路径已有）；返回不变。
- `asr.py`：`AutoModel(model=..., device="cuda" if dev.resolve()=="cuda" else "cpu")`（FunASR 的 AutoModel 支持 device 参数）。
- `embedding.py`：`m.encode(texts, device=dev.resolve(), ...)` 已用 resolve，升级后 resolve 返回 cuda 即用 GPU。
- `llm.py` local 路径：`dev = torch.device(dev.resolve())`（auto 时先 resolve；显式 "cuda"/"cpu" 保持）。

### 4. FFmpeg 渲染（`app/editors/renderer.py`）

- 新增 `_pick_video_codec(ffmpeg)`：探测 `ffmpeg -encoders` 输出含 `h264_nvenc` → 返回 `"h264_nvenc"`，否则 `"libx264"`。
- `_render_clip` 的 `-c:v` 用探测结果；`h264_nvenc` 时移除 `-pix_fmt yuv420p` 前的 `-c:v libx264` 冲突（NVENC 用 `-c:v h264_nvenc -pix_fmt yuv420p`）。
- NVENC 编码失败（如驱动/显存问题）→ 捕获异常回退 `libx264` 重试一次。
- concat 逻辑不变（各片段同编码器）。

### 5. 配置（`config.yaml`）

```yaml
gpu:
  enabled: auto        # auto|on|off
  memory_fraction: 0.7 # 可用显存的利用比例
```

- `settings.py` 新增 `gpu_enabled`、`gpu_memory_fraction` 字段（默认 auto/0.7）。
- `enabled: off` → 强制 CPU；`on` → 即使无 CUDA 也尝试（异常回退 CPU）；`auto` → 检测。

## 错误处理

- GPU 检测失败/驱动缺失 → CPU，日志标注。
- llama.cpp CUDA 加载失败 / CUDA OOM → 捕获异常，回退 CPU 重试（get_gguf_llm 内 try/except 换 `n_gpu_layers=0` 重载）。
- NVENC 编码失败 → 回退 libx264 重试。

## 测试

- `tests/test_device.py`（新建）：resolve 各分支（无 torch/无 nvidia-smi/显存不足→cpu；有 CUDA+显存足→cuda）；select_device 的 n_gpu_layers 计算（monkeypatch 显存）。
- `tests/test_render.py` 追加：`_pick_video_codec` 探测 NVENC→h264_nvenc、无→libx264。
- 适配器测试保持绿（mock 设备解析）。

## 验收标准

1. `nvidia-smi` 存在且 torch/llama-cpp CUDA 版安装后，`DeviceManager("auto").resolve()` 返回 "cuda"。
2. `describe`/`analyze` 运行日志显示模型在 GPU 推理（或显存不足时回退 CPU 并标注）。
3. 渲染在 NVENC 可用时生成 `h264_nvenc` 编码的 final.mp4；无 NVENC 回退 libx264。
4. 全量 `pytest tests/` 保持全绿。
5. 无 GPU 环境（CPU 版依赖）下所有功能正常回退 CPU，不受影响。
