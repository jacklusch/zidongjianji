# GPU 自动检测与设备分配 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 自动检测 CUDA → 计算显存 → 显存允许时 GPU 优先运行模型（VLM/ASR/Embedding/LLM-local），CPU 回退；FFmpeg 检测 NVENC 自动切硬件编码。

**架构：** `app/models/device.py` 的 `DeviceManager` 扩展显存感知（`resolve_cuda_support`/`select_device`），各适配器用 `select_device` 决定 GPU 层数/设备；`app/editors/renderer.py` 探测 `h264_nvenc` 自动切换编码器；`scripts/install.ps1` 检测 GPU 装 CUDA 版依赖。

**技术栈：** Python、torch（CUDA 版）、llama-cpp-python（CUDA 版）、nvidia-smi、FFmpeg NVENC。

**规格：** `docs/superpowers/specs/2026-08-13-gpu-autodetect-design.md`

---

### 任务 1：settings 增加 gpu 配置段

**文件：**
- 修改：`app/config/settings.py`
- 修改：`config.yaml`、`config.yaml.example`
- 测试：`tests/test_settings.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_settings.py` 追加：

```python
def test_settings_has_gpu_config():
    s = load_settings()
    assert hasattr(s, "gpu_enabled")
    assert hasattr(s, "gpu_memory_fraction")
    assert s.gpu_memory_fraction > 0.0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
预期：FAIL（`Settings` 无 `gpu_enabled` 属性）

- [ ] **步骤 3：修改 `app/config/settings.py`**

`_DEFAULTS` 增加：

```python
    "gpu": {"enabled": "auto", "memory_fraction": 0.7},
```

`Settings` 字段（在 `fps` 后）：

```python
    gpu_enabled: str = "auto"
    gpu_memory_fraction: float = 0.7
```

`load_settings`：

```python
        gpu_enabled=merge["gpu"]["enabled"],
        gpu_memory_fraction=float(merge["gpu"]["memory_fraction"]),
```

- [ ] **步骤 4：修改 `config.yaml` 与 `config.yaml.example`**

`render:` 段后加：

```yaml
gpu:
  enabled: auto        # auto|on|off
  memory_fraction: 0.7 # 可用显存利用比例
```

（config.yaml 不入库，example 同步。）

- [ ] **步骤 5：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add app/config/settings.py config.yaml config.yaml.example tests/test_settings.py
git commit -m "feat: settings 增加 gpu 配置段（enabled/memory_fraction）"
```

---

### 任务 2：`device.py` 显存感知设备管理器

**文件：**
- 修改：`app/models/device.py`
- 测试：`tests/test_device.py`（新建）

- [ ] **步骤 1：编写失败的测试**

创建 `tests/test_device.py`：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.device import DeviceManager


def test_resolve_cpu_when_no_torch_cuda(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: False)
    d = DeviceManager("auto")
    assert d.resolve() == "cpu"


def test_resolve_cuda_when_supported(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: True)
    monkeypatch.setattr("app.models.device._query_gpu", lambda: {"name": "RTX 3060", "total_mb": 12288, "free_mb": 10503})
    monkeypatch.setattr("app.models.device._torch_cuda_available", lambda: True)
    monkeypatch.setattr("app.models.device._llama_gpu_offload", lambda: True)
    d = DeviceManager("auto")
    assert d.resolve() == "cuda"


def test_select_device_returns_cpu_when_no_cuda(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: False)
    dev, layers = DeviceManager("auto").select_device(estimate_bytes=2**30)
    assert dev == "cpu" and layers == 0


def test_select_device_cuda_layers(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: True)
    monkeypatch.setattr("app.models.device._query_gpu", lambda: {"name": "RTX 3060", "total_mb": 12288, "free_mb": 10503})
    monkeypatch.setattr("app.models.device._torch_cuda_available", lambda: True)
    monkeypatch.setattr("app.models.device._llama_gpu_offload", lambda: True)
    dev, layers = DeviceManager("auto").select_device(estimate_bytes=3 * 2**30, total_layers=40)
    assert dev == "cuda"
    assert layers >= 1


def test_resolve_explicit_device():
    assert DeviceManager("cpu").resolve() == "cpu"
    assert DeviceManager("cuda").resolve() == "cuda"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_device.py -v`
预期：FAIL（`select_device`/`_has_nvidia_smi` 未定义）

- [ ] **步骤 3：修改 `app/models/device.py`**

```python
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
```

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_device.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add app/models/device.py tests/test_device.py
git commit -m "feat: DeviceManager 显存感知设备决策（select_device）"
```

---

### 任务 3：各适配器接入 GPU 设备解析

**文件：**
- 修改：`app/models/vlm.py`（`get_gguf_llm` 的 n_gpu_layers）
- 修改：`app/models/asr.py`（AutoModel device）
- 修改：`app/models/embedding.py`（encode device）
- 修改：`app/models/llm.py`（torch.device 修复）
- 测试：`tests/test_models.py`、`tests/test_device.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_device.py` 追加：

```python
def test_select_device_respects_gpu_enabled_off(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: True)
    monkeypatch.setattr("app.models.device._torch_cuda_available", lambda: True)
    monkeypatch.setattr("app.models.device._llama_gpu_offload", lambda: True)
    d = DeviceManager("off")  # config gpu_enabled: off 映射为 device="off"
    dev, layers = d.select_device(estimate_bytes=2**30)
    assert dev == "cpu" and layers == 0
```

在 `tests/test_models.py` 追加（验证 llm local 路径 auto 不崩）：

```python
def test_llm_local_auto_device_no_crash(monkeypatch):
    # 无 torch CUDA 时 torch.device("cpu") 正常
    from app.models.llm import LLM
    monkeypatch.setattr("app.models.device.DeviceManager.resolve", lambda self: "cpu")
    llm = LLM("local", "m", "auto")
    assert llm.device == "auto"  # 构造不崩
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_device.py tests/test_models.py -v`
预期：当前 `select_device` 无 `"off"` 处理（FAIL）

- [ ] **步骤 3：修改各适配器**

**`app/models/device.py`**：`select_device` 的 `"off"` 分支已在上一步实现（task 2 代码含 `if self.device == "off"`）。

**`app/models/vlm.py`** `get_gguf_llm`：

```python
    dev = DeviceManager(device)
    # 显存感知：按主模型大小估算 GPU 层数
    if dev.resolve() == "cuda":
        n_gpu = dev.select_device(estimate_bytes=main_path.stat().st_size, total_layers=40)[1]
    else:
        n_gpu = 0
```

（`main_path` 在 `_resolve_gguf_paths` 后可得。）

**`app/models/asr.py`**：

```python
    from app.models.device import DeviceManager
    dev = DeviceManager(self.device)
    model = AutoModel(model=self.model,
                      device="cuda" if dev.resolve() == "cuda" else "cpu")
```

**`app/models/embedding.py`**：已用 `dev.resolve()`，无需改（resolve 升级后自动 GPU）。

**`app/models/llm.py`** local 路径：

```python
    from app.models.device import DeviceManager
    dev = DeviceManager(self.device)
    torch_device = torch.device(dev.resolve())
    m = m.to(torch_device)
    inp = tok(prompt, return_tensors="pt").to(torch_device)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_device.py tests/test_models.py -v`
预期：PASS

- [ ] **步骤 5：全量回归**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全绿（15 ffmpeg skip 属环境）

- [ ] **步骤 6：Commit**

```bash
git add app/models/device.py app/models/vlm.py app/models/asr.py app/models/llm.py tests/test_device.py tests/test_models.py
git commit -m "feat: 适配器接入显存感知 GPU 设备解析"
```

---

### 任务 4：FFmpeg NVENC 自动切换

**文件：**
- 修改：`app/editors/renderer.py`
- 测试：`tests/test_render.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_render.py` 追加：

```python
def test_pick_video_codec_nvenc_when_available(monkeypatch):
    from app.editors.renderer import _pick_video_codec
    monkeypatch.setattr("app.editors.renderer._probe_nvenc", lambda ffmpeg: True)
    assert _pick_video_codec("ffmpeg") == "h264_nvenc"

def test_pick_video_codec_libx264_when_no_nvenc(monkeypatch):
    from app.editors.renderer import _pick_video_codec
    monkeypatch.setattr("app.editors.renderer._probe_nvenc", lambda ffmpeg: False)
    assert _pick_video_codec("ffmpeg") == "libx264"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_render.py -v`
预期：FAIL（`_pick_video_codec` 未定义）

- [ ] **步骤 3：修改 `app/editors/renderer.py`**

```python
import subprocess

def _probe_nvenc(ffmpeg: str) -> bool:
    """探测 ffmpeg 是否支持 h264_nvenc。"""
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20)
        return "h264_nvenc" in out.stdout
    except Exception:
        return False

def _pick_video_codec(ffmpeg: str) -> str:
    return "h264_nvenc" if _probe_nvenc(ffmpeg) else "libx264"
```

`_render_clip` 的 `-c:v` 改用探测结果；`_render_clip` 签名加 `codec` 参数（或从 ffmpeg 探测）。`_normalize_timeline` 传入 codec。NVENC 编码失败回退：

```python
def _render_clip(src, start, dur, out, ffmpeg, width, height, fps, codec="libx264"):
    ...
    try:
        run(cmd, timeout=600)
    except Exception:
        if codec == "h264_nvenc":
            codec = "libx264"
            # 重建 cmd 用 libx264 重试一次
            run(cmd_with_libx264, timeout=600)
        else:
            raise
```

（实现时把 cmd 构造抽为局部函数以便 codec 切换重建。）

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_render.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add app/editors/renderer.py tests/test_render.py
git commit -m "feat: FFmpeg NVENC 自动探测与回退"
```

---

### 任务 5：install.ps1 GPU 依赖安装 + 验收

**文件：**
- 修改：`scripts/install.ps1`
- 修改：`docs/manual-test-guide.md`
- 测试：无（脚本验证）

- [ ] **步骤 1：修改 `scripts/install.ps1`**

在 `pip install -r requirements.txt` 后加 GPU 检测与 CUDA 依赖安装：

```powershell
# GPU 检测：有 nvidia-smi 则装 CUDA 版模型依赖
$gpu = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($gpu) {
    Write-Host "检测到 NVIDIA GPU，安装 CUDA 版模型依赖..."
    & $py -m pip install "torch==2.13.0+cu121" --index-url https://download.pytorch.org/whl/cu121
    & $py -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
} else {
    Write-Host "未检测到 NVIDIA GPU，安装 CPU 版模型依赖..."
    & $py -m pip install -r requirements-models.txt
}
& $py -m pip install -r requirements-models.txt  # 其余模型依赖（funasr/sentence-transformers 等）
```

（注意：requirements-models.txt 已含 torch/llama-cpp 的 CPU 版本声明，GPU 分支先装 CUDA 版会满足版本约束。若冲突则用 `--force-reinstall`。）

- [ ] **步骤 2：人工验证**

运行：`scripts\install.ps1`（或仅验证 GPU 检测分支逻辑不破坏现有环境——若已有 CUDA 版依赖则跳过实际安装）

- [ ] **步骤 3：全量测试**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全绿

- [ ] **步骤 4：更新 `docs/manual-test-guide.md`**

新增"GPU 加速"小节：`nvidia-smi` 检测、install.ps1 自动装 CUDA 版、`config.yaml` 的 gpu 段说明、`describe`/`render` 如何确认在用 GPU。

- [ ] **步骤 5：Commit**

```bash
git add scripts/install.ps1 docs/manual-test-guide.md
git commit -m "feat: install.ps1 GPU 检测与 CUDA 依赖安装"
```

---

## 自检

- **规格覆盖度**：依赖安装（任务 5）、DeviceManager 显存感知（任务 2）、各适配器接入（任务 3）、NVENC 切换（任务 4）、配置段（任务 1）、验收（任务 5）——全部覆盖。
- **占位符扫描**：无 TODO/待定；每步骤含实际代码。
- **类型一致性**：`select_device(estimate_bytes, total_layers, memory_fraction)` 任务 2 定义，任务 3 vlm.py 调用签名一致；`gpu_enabled`/`gpu_memory_fraction` 任务 1 定义，任务 3 通过 config 映射 device；`_pick_video_codec`/`_probe_nvenc` 任务 4 定义并同任务使用。
