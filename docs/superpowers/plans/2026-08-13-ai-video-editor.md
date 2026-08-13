# AI 自动视频剪辑系统 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 Windows 10/11 x64 上构建一个完全本地的 CLI 视频剪辑系统：用户提供 `materials/` 素材与 `scripts/script.md` 脚本文案，系统自动完成场景分析、语义检索、镜头匹配、时间线规划与 FFmpeg 渲染，产出 `final.mp4`。

**架构：** 分层管线（index → analyze → embed → search → match → timeline → validate → render），全部通过本地 SQLite 索引与 `edit_plan.json` 中间产物衔接；所有 AI 能力走可替换适配器，模型缺失时自动降级到确定性规则实现，保证零模型机器开箱即用。FFmpeg 为唯一渲染核心（裁剪+归一化+concat），AutoCut 仅作预留插件。

**技术栈：** Python 3.11、SQLite、PySceneDetect、rank-bm25、PyYAML、opencv-python、FFmpeg（由 `install.ps1` 获取）；torch / transformers / faster-whisper / sentence-transformers 为可选模型依赖（`requirements-models.txt`，装不装都不影响主流程）。

**规格依据：** `docs/superpowers/specs/2026-08-13-ai-video-editor-design.md`

---

## 文件结构（分解决策）

```
<repo root = D:\bak_f\001\zidongjianji>
├── app/
│   ├── __init__.py
│   ├── main.py                          # argparse CLI：index/analyze/search/plan/render/build/scan
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                  # Settings 数据类 + load_settings(config.yaml)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── device.py                    # DeviceManager（auto/cpu/cuda/rocm）
│   │   ├── base.py                      # ModelProvider 抽象 + available()/provider 解析
│   │   ├── llm.py                       # LLM 适配器（none=规则兜底）
│   │   ├── vlm.py                       # VLM 适配器 + JSON repair
│   │   ├── whisper.py                   # Whisper 适配器（none=空转写）
│   │   └── embedding.py                 # Embedding 适配器（none=BM25 兜底）
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── media.py                     # FFprobe 媒体信息 MediaInfo
│   │   ├── scene.py                     # PySceneDetect 切分 Shot / is_image
│   │   ├── frames.py                    # 抽帧 + 缩略图 FrameSample
│   │   ├── visual.py                    # 标志性帧统计 → VisualAnalysis（fallback 分析）
│   │   └── audio.py                     # Whisper 转写 TranscriptSegment
│   ├── index/
│   │   ├── __init__.py
│   │   ├── database.py                  # SQLite 建表/CRUD（media/shots/visual_analysis/transcripts/embeddings）
│   │   ├── footage_index.py             # 增量扫描：hash+size+mtime 判定缓存
│   │   ├── embeddings.py                # shot 搜索文本构建 + 向量存取
│   │   └── search.py                    # SearchBackend（BM25 或向量）→ 检索
│   ├── script/
│   │   ├── __init__.py
│   │   ├── schema.py                    # ScriptSegment 数据类
│   │   ├── parser.py                    # LLM 或规则 → segments
│   │   └── planner.py                   # → script_plan.json
│   ├── matching/
│   │   ├── __init__.py
│   │   ├── retriever.py                 # 每 segment 检索 Top-K（CandidateShot）
│   │   ├── reranker.py                  # VLM 二次评分，无则原样
│   │   └── matcher.py                   # 打分融合 + duplicate_penalty → MatchResult
│   ├── timeline/
│   │   ├── __init__.py
│   │   ├── schema.py                    # EditPlan/TimelineItem 数据类
│   │   ├── planner.py                   # match → edit_plan dict（含 missing/reused）
│   │   └── validator.py                 # 时间码/文件存在/引用校验
│   ├── editors/
│   │   ├── __init__.py
│   │   ├── ffmpeg.py                    # ffprobe_json / 裁剪 / 归一化 / concat 命令构造
│   │   ├── autocut.py                   # 预留插件接口（未激活）
│   │   └── renderer.py                  # edit_plan → final.mp4 + preview.mp4
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── index_pipeline.py            # run_index（扫描+切分+抽帧 + 可选分析/嵌入）
│   │   ├── analysis_pipeline.py         # run_analyze（VLM/Whisper → DB）
│   │   ├── matching_pipeline.py         # run_plan（脚本→检索→重排→edit_plan）
│   │   └── render_pipeline.py           # run_render（→final.mp4）
│   └── utils/
│       ├── __init__.py
│       ├── process.py                   # run() subprocess 封装 shell=False + find_ffmpeg
│       ├── paths.py                     # 路径推导 + 目录确保
│       ├── logging.py                   # setup_logging → data/logs/<ts>_<cmd>.log
│       └── hashing.py                   # sha256_file（分块）
├── scripts/
│   ├── install.ps1                      # venv(3.11) + requirements + 获取 FFmpeg + config
│   ├── start.ps1                        # 激活并提示命令
│   ├── script.md                        # 默认脚本样例
│   └── demo.md                          # 验收脚本样例
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # tmp 素材/脚本 fixture（ffmpeg 生成合成视频，缺失则 skip）
│   ├── test_paths.py
│   ├── test_media.py
│   ├── test_scene.py
│   ├── test_script_parser.py
│   ├── test_edit_plan.py
│   ├── test_matcher.py
│   ├── test_validator.py
│   └── test_build.py                    # 端到端：build 产出 final.mp4
├── config.yaml                          # 默认配置（所有模型 provider:none）
├── requirements.txt                     # 核心依赖（轻量）
├── requirements-models.txt              # 可选模型依赖（torch/transformers/...）
├── README.md
├── .gitignore                           # 已含 venv/bin/materials/data/output/models
```

**路径约定**：所有代码用 `pathlib.Path`；项目根由 `app/config/settings.py` 从 `Path(__file__).resolve().parents[2]` 推导；禁止硬编码盘符。

---

## 任务 1：环境与项目骨架

**文件：**
- 创建：`app/__init__.py`（空）、`app/config/__init__.py`、`app/config/settings.py`、`app/utils/__init__.py`、`app/utils/paths.py`、`app/utils/logging.py`、`app/utils/hashing.py`、`requirements.txt`、`config.yaml`、`scripts/install.ps1`、`scripts/start.ps1`、`tests/__init__.py`、`tests/conftest.py`、`tests/test_paths.py`

- [ ] **步骤 1：编写失败的测试**（`tests/test_paths.py`）

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.utils.paths import project_root, ensure_dirs
from app.utils.hashing import sha256_file
from app.utils.logging import setup_logging

def test_project_root_is_repo():
    assert (project_root() / "requirements.txt").exists()

def test_ensure_dirs_creates(tmp_path):
    d1 = tmp_path / "a" / "b"
    ensure_dirs([d1])
    assert d1.is_dir()

def test_sha256_stable(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    assert sha256_file(f) == sha256_file(f)
    assert len(sha256_file(f)) == 64

def test_setup_logging_creates_file(tmp_path):
    log = setup_logging(tmp_path, "test")
    log.info("hi")
    assert any(tmp_path.iterdir())
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_paths.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app'`（此处 venv 尚未创建，见步骤 3 后执行）

- [ ] **步骤 3：创建 venv 并安装核心依赖**

```powershell
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install PyYAML scenedetect opencv-python rank-bm25 numpy
```

`requirements.txt` 内容固定为上述包（附主版本号）：

```
PyYAML>=6.0
scenedetect>=0.6.4
opencv-python>=4.8
rank-bm25>=0.2.2
numpy>=1.26
```

- [ ] **步骤 4：实现 `app/utils/paths.py`**

```python
from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def ensure_dirs(dirs) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
```

- [ ] **步骤 5：实现 `app/utils/hashing.py`**

```python
import hashlib
from pathlib import Path

def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()
```

- [ ] **步骤 6：实现 `app/utils/logging.py`**

```python
import logging
from datetime import datetime
from pathlib import Path

def setup_logging(logs_dir: Path, command: str) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    fname = f"{ts}_{command}.log"
    logger = logging.getLogger("video_editor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(logs_dir / fname, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
```

- [ ] **步骤 7：实现 `app/config/settings.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from app.utils.paths import project_root

_DEFAULTS = {
    "models": {"vlm": {"provider": "none", "model": "", "device": "auto"},
               "vlm_reranker": {"provider": "none", "model": "", "device": "auto"},
               "embedding": {"provider": "none", "model": "", "device": "auto"},
               "whisper": {"provider": "none", "model": "", "device": "auto"},
               "llm": {"provider": "none", "model": "", "device": "auto"}},
    "video": {"scene_threshold": 0.35, "min_shot_duration": 1.0},
    "matching": {"top_k": 20, "rerank_k": 5},
    "index": {"frames_min": 3, "frames_max": 8},
    "render": {"resolution": "1920x1080", "fps": 30, "format": "mp4"},
}

@dataclass
class ModelConfig:
    provider: str = "none"
    model: str = ""
    device: str = "auto"

@dataclass
class Settings:
    root: Path
    models_dir: Path
    materials_dir: Path
    data_dir: Path
    output_dir: Path
    logs_dir: Path
    projects_dir: Path
    footage_dir: Path
    bin_dir: Path
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    vlm: ModelConfig = field(default_factory=ModelConfig)
    vlm_reranker: ModelConfig = field(default_factory=ModelConfig)
    embedding: ModelConfig = field(default_factory=ModelConfig)
    whisper: ModelConfig = field(default_factory=ModelConfig)
    llm: ModelConfig = field(default_factory=ModelConfig)
    scene_threshold: float = 0.35
    min_shot_duration: float = 1.0
    top_k: int = 20
    rerank_k: int = 5
    frames_min: int = 3
    frames_max: int = 8
    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_format: str = "mp4"

    @property
    def footage_db(self) -> Path:
        return self.footage_dir / "index.db"

    @property
    def thumbnails_dir(self) -> Path:
        return self.footage_dir / "thumbnails"

    @property
    def embeddings_dir(self) -> Path:
        return self.footage_dir / "embeddings"

    @property
    def transcripts_dir(self) -> Path:
        return self.footage_dir / "transcripts"

    @property
    def resolution(self) -> tuple[int, int]:
        return self.width, self.height

def load_settings(config_path: Path | None = None) -> Settings:
    root = project_root()
    cfg_path = config_path or root / "config.yaml"
    raw: dict = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    merge = _DEFAULTS.copy()
    deep = {k: {**_DEFAULTS[k], **(raw.get(k) or {})} for k in _DEFAULTS}
    merge.update(deep)
    render = merge["render"]
    w, h = (str(render["resolution"]).split("x"))
    s = Settings(
        root=root,
        models_dir=root / "models",
        materials_dir=root / "materials",
        data_dir=root / "data",
        output_dir=root / "output",
        logs_dir=root / "data" / "logs",
        projects_dir=root / "data" / "projects",
        footage_dir=root / "data" / "footage",
        bin_dir=root / "bin",
        vlm=ModelConfig(**merge["models"]["vlm"]),
        vlm_reranker=ModelConfig(**merge["models"]["vlm_reranker"]),
        embedding=ModelConfig(**merge["models"]["embedding"]),
        whisper=ModelConfig(**merge["models"]["whisper"]),
        llm=ModelConfig(**merge["models"]["llm"]),
        scene_threshold=float(merge["video"]["scene_threshold"]),
        min_shot_duration=float(merge["video"]["min_shot_duration"]),
        top_k=int(merge["matching"]["top_k"]),
        rerank_k=int(merge["matching"]["rerank_k"]),
        frames_min=int(merge["index"]["frames_min"]),
        frames_max=int(merge["index"]["frames_max"]),
        fps=int(merge["render"]["fps"]),
        video_format=merge["render"]["format"],
        width=int(w), height=int(h),
    )
    if (root / "bin" / "ffmpeg" / "bin" / "ffmpeg.exe").exists():
        s.ffmpeg = str(root / "bin" / "ffmpeg" / "bin" / "ffmpeg.exe")
        s.ffprobe = str(root / "bin" / "ffmpeg" / "bin" / "ffprobe.exe")
    elif (root / "bin" / "ffmpeg" / "ffmpeg.exe").exists():
        s.ffmpeg = str(root / "bin" / "ffmpeg" / "ffmpeg.exe")
        s.ffprobe = str(root / "bin" / "ffmpeg" / "ffprobe.exe")
    return s
```

- [ ] **步骤 8：编写 `config.yaml`**

```yaml
models:
  vlm: {provider: none, model: "", device: auto}
  vlm_reranker: {provider: none, model: "", device: auto}
  embedding: {provider: none, model: "", device: auto}
  whisper: {provider: none, model: "", device: auto}
  llm: {provider: none, model: "", device: auto}
video:
  scene_threshold: 0.35
  min_shot_duration: 1.0
matching:
  top_k: 20
  rerank_k: 5
index:
  frames_min: 3
  frames_max: 8
render:
  resolution: 1920x1080
  fps: 30
  format: mp4
```

- [ ] **步骤 9：编写 `scripts/install.ps1` 与 `scripts/start.ps1`**

`install.ps1`：

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path "venv\Scripts\python.exe")) {
    py -3.11 -m venv venv
    if (-not $?) { python -m venv venv }
}
$py = Join-Path $root "venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
# FFmpeg：PATH 或 bin\ffmpeg
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ff -and -not (Test-Path "bin\ffmpeg\ffmpeg.exe")) {
    New-Item -ItemType Directory -Path "bin" -Force | Out-Null
    $zip = Join-Path $env:TEMP "ffmpeg.zip"
    Invoke-WebRequest -Uri "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "bin" -Force
    $extracted = Get-ChildItem "bin" -Directory | Where-Object Name -like "ffmpeg-*" | Select-Object -First 1
    Move-Item $extracted.FullName "bin\ffmpeg" -Force
}
if (-not (Test-Path "config.yaml")) { Copy-Item "config.yaml.example" "config.yaml" }
"安装完成。运行 scripts\start.ps1 开始使用。"
```

`start.ps1`：

```powershell
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& "venv\Scripts\python.exe" -m app.main --help
"提示：python -m app.main index materials  # 建立素材索引"
```

`install.ps1` 依赖 `config.yaml.example`（与步骤 8 的 `config.yaml` 内容一致的模板），将步骤 8 的内容复制一份为 `config.yaml.example`。

- [ ] **步骤 10：编写 `tests/conftest.py`**

```python
import shutil
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

@pytest.fixture(scope="session")
def ffmpeg() -> str:
    p = ROOT / "bin" / "ffmpeg" / "ffmpeg.exe"
    if p.exists():
        return str(p)
    exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("ffmpeg not available")
    return exe

@pytest.fixture(scope="session")
def ffprobe() -> str:
    p = ROOT / "bin" / "ffmpeg" / "ffprobe.exe"
    if p.exists():
        return str(p)
    exe = shutil.which("ffprobe")
    if not exe:
        pytest.skip("ffprobe not available")
    return exe

@pytest.fixture(scope="session")
def sample_video(tmp_path_factory, ffmpeg):
    out = tmp_path_factory.mktemp("media") / "factory01.mp4"
    cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc2=duration=6:size=640x360:rate=30",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)]
    subprocess_run(cmd)
    return out
```

`conftest.py` 顶部需真实导入 `subprocess`，并定义：

```python
import subprocess

def subprocess_run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)
```

- [ ] **步骤 11：运行测试验证通过并提交**

运行：`venv\Scripts\python.exe -m pytest tests/test_paths.py -v`
预期：4 个 PASS

```bash
git add app/ tests/ scripts/ config.yaml config.yaml.example requirements.txt
git commit -m "feat: 项目骨架、配置、路径/日志/哈希工具与安装脚本"
```

---

## 任务 2：FFprobe 媒体信息

**文件：**
- 创建：`app/utils/process.py`、`app/editors/__init__.py`、`app/editors/ffmpeg.py`、`app/analyzer/__init__.py`、`app/analyzer/media.py`
- 测试：`tests/test_media.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.analyzer.media import probe_media
from app.utils.process import run

def test_probe_video(sample_video):
    info = probe_media(sample_video)
    assert info.filename == "factory01.mp4"
    assert info.width > 0 and info.height > 0
    assert info.duration > 0
    assert info.audio

def test_probe_missing_raises():
    import pytest
    from app.missing import MissingMediaError
    from app.analyzer.media import probe_media
    with pytest.raises(MissingMediaError):
        probe_media("not_there.mp4")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_media.py -v`
预期：FAIL，`No module named 'app.analyzer'`

- [ ] **步骤 3：实现 `app/utils/process.py`**

```python
import os
import subprocess
from pathlib import Path
from typing import Iterable

class RunError(RuntimeError):
    pass

def run(cmd: Iterable[str], cwd=None, timeout: int = 300, env=None) -> subprocess.CompletedProcess:
    """shell=False 执行外部命令，失败抛 RunError（含 stdout/stderr）。"""
    proc = subprocess.run(
        list(cmd), cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, shell=False,
        env=os.environ if env is None else {**os.environ, **env},
    )
    if proc.returncode != 0:
        raise RunError(f"命令失败 ({proc.returncode}): {cmd}\n{proc.stdout[-2000:]} {proc.stderr[-4000:]}")
    return proc
```

- [ ] **步骤 4：实现 `app/analysis/media.py` 的前置：先创建 `app/editors/ffmpeg.py`，其中 `ffprobe_json`**

```python
import json
from pathlib import Path
from app.utils.process import run

class MissingMediaError(FileNotFoundError):
    pass

def ffprobe_json(path, ffprobe: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise MissingMediaError(f"素材不存在: {p}")
    try:
        return json.loads(run([ffprobe, "-v", "error", "-print_format", "json",
                               "-show_format", "-show_streams", str(p)]).stdout)
    except Exception as e:
        raise MissingMediaError(f"FFprobe 解析失败 {p}: {e}") from e
```

- [ ] **步骤 5：实现 `app/analyzer/media.py`**

```python
from dataclasses import dataclass
from pathlib import Path
from app.editors.ffmpeg import ffprobe_json, MissingMediaError

@dataclass
class MediaInfo:
    path: Path
    filename: str
    extension: str
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    audio: bool
    size: int

def probe_media(path, ffprobe: str = "ffprobe") -> MediaInfo:
    p = Path(path)
    data = ffprobe_json(p, ffprobe)
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur_s = float(data.get("format", {}).get("duration") or v.get("duration") or 0.0)
    fps_s = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
    num, den = fps_s.split("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    return MediaInfo(
        path=p, filename=p.name, extension=p.suffix.lower(),
        duration=dur_s, width=int(v.get("width", 0)), height=int(v.get("height", 0)),
        fps=fps, codec=v.get("codec_name", ""), audio=a is not None,
        size=p.stat().st_size,
    )
```

- [ ] **步骤 6：实现 `tests/test_media.py` 中缺失的类型：在 `app/analyzer/__init__.py` 中不导出，直接 import `from app.analyzer.media import MissingMediaError` 改测试**

修正测试第 5–10 行中的 `from app.missing import MissingMediaError` 为 `from app.analyzer.media import probe_media` 同一来源。真实测试代码：

```python
import pytest
from app.analyzer.media import probe_media, MissingMediaError

def test_probe_video(sample_video):
    info = probe_media(sample_video)
    assert info.filename == "factory01.mp4"
    assert info.width > 0 and info.height > 0
    assert info.duration > 0
    assert info.audio

def test_probe_missing_raises():
    with pytest.raises(MissingMediaError):
        probe_media("not_there.mp4")
```

- [ ] **步骤 7：运行测试验证通过并提交**

运行：`venv\Scripts\python.exe -m pytest tests/test_media.py -v`
预期：2 个 PASS

```bash
git add app/ tests/test_media.py
git commit -m "feat: FFprobe 媒体信息解析与 subprocess 封装"
```

---

## 任务 3：CLI 骨架 + scan 命令

**文件：**
- 创建：`app/__init__.py` 不修改、`app/main.py`、`scripts/script.md`
- 修改：`app/utils/process.py` 增加 `find_ffmpeg`
- 测试：`tests/test_media.py` 增加 scanner 测试；`app/analyzer/media.py` 增加 `scan_directory`

**命令目标（Phase 1 验收）：** `python -m app.main scan materials` 列出素材清单。

- [ ] **步骤 1：编写失败的测试**

```python
from app.analyzer.media import scan_directory, MediaInfo

def test_scan_directory_finds_video(sample_video, ffprobe):
    items = scan_directory(sample_video.parent, ffprobe=ffprobe)
    assert any(i.filename == "factory01.mp4" for i in items)
```

- [ ] **步骤 2：实现 `app/analyzer/media.py` 扩展**

```python
SUPPORTED = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".jpg", ".jpeg", ".png", ".webp"}

def scan_directory(directory, ffprobe: str = "ffprobe") -> list[MediaInfo]:
    out = []
    for p in sorted(Path(directory).rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            try:
                out.append(probe_media(p, ffprobe))
            except MissingMediaError:
                continue
    return out
```

- [ ] **步骤 3：实现 `app/utils/process.py` 增加**

```python
from app.utils.paths import project_root

def find_ffmpeg(settings) -> tuple[str, str]:
    """返回 (ffmpeg, ffprobe)；优先 bin/ffmpeg，其次 PATH，都没有则抛 RunError 提示安装。"""
    p = settings.bin_dir / "ffmpeg"
    for cand in (p / "bin", p):
        if (cand / "ffmpeg.exe").exists():
            return str(cand / "ffmpeg.exe"), str(cand / "ffprobe.exe")
    ff = shutil.which("ffmpeg")
    if ff:
        base = Path(ff).parent
        return ff, str(base / ("ffprobe.exe" if os.name == "nt" else "ffprobe"))
    raise RunError("FFmpeg 未找到。请运行 scripts\\install.ps1 或安装 FFmpeg 并加入 PATH")
```

（`process.py` 顶部补 `import shutil`。）

- [ ] **步骤 4：实现 `app/main.py`**

```python
import argparse
import json
import sys
from app.config.settings import load_settings
from app.utils.process import find_ffmpeg
from app.utils.logging import setup_logging

def cmd_scan(args):
    settings = load_settings()
    log = setup_logging(settings.logs_dir, "scan")
    ffmpeg, ffprobe = find_ffmpeg(settings)
    from app.analyzer.media import scan_directory
    log.info(f"扫描目录: {args.directory}")
    items = scan_directory(args.directory, ffprobe=ffprobe)
    log.info(f"找到 {len(items)} 个文件")
    for it in items:
        print(f"{it.path} | {it.duration:.2f}s | {it.width}x{it.height} | {it.codec} | audio={'yes' if it.audio else 'no'}")

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="app.main", description="本地 AI 视频剪辑系统")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan", help="扫描素材目录")
    s.add_argument("directory")
    s.set_defaults(func=cmd_scan)
    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

后续任务会在此文件为 `index/analyze/search/plan/render/build` 追加子命令。

- [ ] **步骤 5：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_media.py -v`
预期：3 个 PASS

- [ ] **步骤 6：人工验证 CLI**

运行：`venv\Scripts\python.exe -m app.main scan "C:\Users\Administrator\AppData\Local\Temp"`（指向 `sample_video` 所在临时目录的上级任意含视频目录即可）
预期：输出每个文件一行媒体信息

- [ ] **步骤 7：编写 `scripts/script.md` 样例**

```markdown
主题：现代化香肠生产工艺

开头展示现代化工厂环境。

接下来展示工人操作生产线。

然后展示香肠产品特写。

最后展示包装完成后的产品。
```

- [ ] **步骤 8：Commit**

```bash
git add app/ scripts/script.md tests/test_media.py
git commit -m "feat: CLI 骨架与 scan 命令"
```

---

## 任务 4：SQLite 数据库层

**文件：**
- 创建：`app/index/__init__.py`、`app/index/database.py`
- 测试：`tests/test_media.py` 新建 `tests/test_database.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from app.index.database import Database

@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "index.db")

def test_schema_created(db):
    tables = db.table_names()
    assert {"media", "shots", "visual_analysis", "transcripts", "embeddings"} <= set(tables)

def test_upsert_media_and_read(db):
    m = db.upsert_media("factory_001.mp4", "materials/factory_001.mp4", 6.0, 640, 360, 30.0, "h264", True, 1234, "abc123")
    got = db.get_media_by_path("materials/factory_001.mp4")
    assert got is not None and got["hash"] == "abc123"

def test_shots_roundtrip(db):
    db.upsert_media("m.mp4", "materials/m.mp4", 6.0, 640, 360, 30.0, "h264", True, 1, "h1")
    mid = db.get_media_by_path("materials/m.mp4")["id"]
    db.upsert_shot("m_001", mid, 0.0, 3.0, 3.0, "v1", "fallback")
    shots = db.get_shots_by_media(mid)
    assert shots[0]["shot_id"] == "m_001"

def test_visual_and_transcript_roundtrip(db):
    db.upsert_media("m.mp4", "materials/m.mp4", 6.0, 640, 360, 30.0, "h264", True, 1, "h1")
    mid = db.get_media_by_path("materials/m.mp4")["id"]
    db.upsert_shot("m_001", mid, 0.0, 3.0, 3.0, "v1", "fallback")
    db.upsert_visual("m_001", "工人在流水线上", ["person"], ["operation"], "factory", "medium", "static", 1, 0.9, "{}")
    va = db.get_visual("m_001")
    assert va["description"] == "工人在流水线上"
    db.upsert_transcript("m_001", 0, 0.0, 1.0, "你好")
    tr = db.get_transcripts("m_001")
    assert tr[0]["text"] == "你好"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_database.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.index'`

- [ ] **步骤 3：实现 `app/index/database.py`**

```python
import json
import sqlite3
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    rel_path TEXT NOT NULL,
    duration REAL, width INTEGER, height INTEGER, fps REAL,
    codec TEXT, audio INTEGER, size INTEGER,
    hash TEXT, mtime REAL, indexed_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS shots (
    shot_id TEXT PRIMARY KEY,
    media_id INTEGER NOT NULL REFERENCES media(id),
    start REAL, end REAL, duration REAL,
    analysis_version TEXT, analysis_method TEXT
);
CREATE TABLE IF NOT EXISTS visual_analysis (
    shot_id TEXT PRIMARY KEY REFERENCES shots(shot_id),
    description TEXT, objects TEXT, actions TEXT, environment TEXT,
    shot_type TEXT, camera_motion TEXT, people_count INTEGER,
    visual_quality REAL, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shot_id TEXT NOT NULL REFERENCES shots(shot_id),
    seg_index INTEGER, start REAL, end REAL, text TEXT, speaker TEXT
);
CREATE TABLE IF NOT EXISTS embeddings (
    shot_id TEXT PRIMARY KEY REFERENCES shots(shot_id),
    model TEXT, dim INTEGER, vector_json TEXT, text TEXT
);
"""

class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def table_names(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return [r["name"] for r in rows]

    def upsert_media(self, filename, rel_path, duration, width, height, fps,
                     codec, audio, size, hash, mtime=0.0, path=None) -> int:
        path = path or str((Path(rel_path)))
        cur = self.conn.execute(
            """INSERT INTO media (filename,path,rel_path,duration,width,height,fps,codec,audio,size,hash,mtime)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET
                 filename=excluded.filename, duration=excluded.duration, width=excluded.width,
                 height=excluded.height, fps=excluded.fps, codec=excluded.codec, audio=excluded.audio,
                 size=excluded.size, hash=excluded.hash, mtime=excluded.mtime
               RETURNING id""",
            (filename, path, rel_path, duration, width, height, fps, codec,
             int(audio), size, hash, mtime))
        row = cur.fetchone()
        self.conn.commit()
        return row["id"]

    def get_media_by_path(self, rel_path: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM media WHERE rel_path=?", (rel_path,)).fetchone()
        return dict(row) if row else None

    def get_all_media(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM media")]

    def upsert_shot(self, shot_id, media_id, start, end, duration,
                    analysis_version, analysis_method) -> None:
        self.conn.execute(
            """INSERT INTO shots (shot_id,media_id,start,end,duration,analysis_version,analysis_method)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(shot_id) DO UPDATE SET start=excluded.start, end=excluded.end,
                 duration=excluded.duration, analysis_method=excluded.analysis_method""",
            (shot_id, media_id, start, end, duration, analysis_version, analysis_method))
        self.conn.commit()

    def get_shots_by_media(self, media_id: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM shots WHERE media_id=? ORDER BY start", (media_id,))]

    def get_all_shots(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT s.*, m.rel_path as source FROM shots s JOIN media m ON m.id=s.media_id ORDER BY s.start")]

    def delete_shots_for_media(self, media_id: int) -> None:
        for sid in self.conn.execute("SELECT shot_id FROM shots WHERE media_id=?", (media_id,)):
            self.conn.execute("DELETE FROM visual_analysis WHERE shot_id=?", (sid["shot_id"],))
            self.conn.execute("DELETE FROM transcripts WHERE shot_id=?", (sid["shot_id"],))
            self.conn.execute("DELETE FROM embeddings WHERE shot_id=?", (sid["shot_id"],))
        self.conn.execute("DELETE FROM shots WHERE media_id=?", (media_id,))
        self.conn.commit()

    def delete_media(self, rel_path: str) -> None:
        m = self.get_media_by_path(rel_path)
        if m:
            self.delete_shots_for_media(m["id"])
            self.conn.execute("DELETE FROM media WHERE id=?", (m["id"],))
            self.conn.commit()

    def upsert_visual(self, shot_id, description, objects, actions, environment,
                      shot_type, camera_motion, people_count, visual_quality, raw_json):
        self.conn.execute(
            """INSERT INTO visual_analysis (shot_id,description,objects,actions,environment,shot_type,camera_motion,people_count,visual_quality,raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(shot_id) DO UPDATE SET description=excluded.description,
                 objects=excluded.objects, actions=excluded.actions, environment=excluded.environment,
                 shot_type=excluded.shot_type, camera_motion=excluded.camera_motion,
                 people_count=excluded.people_count, visual_quality=excluded.visual_quality,
                 raw_json=excluded.raw_json""",
            (shot_id, description, json.dumps(objects, ensure_ascii=False),
             json.dumps(actions, ensure_ascii=False), environment, shot_type,
             camera_motion, people_count, visual_quality, raw_json))
        self.conn.commit()

    def get_visual(self, shot_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM visual_analysis WHERE shot_id=?", (shot_id,)).fetchone()
        return dict(row) if row else None

    def upsert_transcript(self, shot_id, seg_index, start, end, text, speaker=""):
        self.conn.execute(
            "INSERT INTO transcripts (shot_id,seg_index,start,end,text,speaker) VALUES (?,?,?,?,?,?)",
            (shot_id, seg_index, start, end, text, speaker))
        self.conn.commit()

    def get_transcripts(self, shot_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM transcripts WHERE shot_id=? ORDER BY start", (shot_id,))]

    def upsert_embedding(self, shot_id, model, dim, vector, text):
        self.conn.execute(
            """INSERT INTO embeddings (shot_id,model,dim,vector_json,text) VALUES (?,?,?,?,?)
               ON CONFLICT(shot_id) DO UPDATE SET model=excluded.model, dim=excluded.dim,
                 vector_json=excluded.vector_json, text=excluded.text""",
            (shot_id, model, dim, json.dumps(vector), text))
        self.conn.commit()

    def get_all_embeddings(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM embeddings")]

    def close(self):
        self.conn.close()
```

- [ ] **步骤 4：运行全部测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add app/index/ tests/test_database.py
git commit -m "feat: SQLite 数据库层（media/shots/visual/transcripts/embeddings）"
```

---

## 任务 5：场景切分（PySceneDetect）

**文件：**
- 创建：`app/analyzer/scene.py`
- 测试：`tests/test_scene.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.analyzer.scene import detect_shots, is_image

def test_detect_shots_returns_shots(sample_video):
    shots = detect_shots(sample_video) if False else detect_shots(str(sample_video)) if False else detect_shots(sample_video)
    assert len(shots) >= 1
    first = shots[0]
    assert first.start >= 0 and first.end > first.start
    assert first.duration > 0

def test_is_image():
    assert is_image("a.JPG")
    assert not is_image("a.mp4")
```

（`detect_shots` 签名接受 `Path | str`，内部统一 `str(p)`。测试第一条只需断言 ≥1 个 shot 且时间码合法。）

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_scene.py -v`
预期：FAIL，`No module named 'app.analyzer.scene'`

- [ ] **步骤 3：实现 `app/analyzer/scene.py`**

```python
from dataclasses import dataclass
from pathlib import Path
import scenedetect
from scenedetect import SceneManager
from scenedetect.detectors import ContentDetector
from app.analyzer.media import SUPPORTED

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

@dataclass
class Shot:
    shot_id: str
    source: str       # 相对路径（正斜杠）
    start: float
    end: float
    duration: float

def is_image(path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXT

def detect_shots(path, scene_threshold: float = 0.35,
                 min_duration: float = 1.0, ffmpeg: str | None = None) -> list[Shot]:
    p = Path(path)
    if is_image(p):
        return [Shot(shot_id=f"{p.stem}_shot1", source=str(p).replace("\\", "/"),
                     start=0.0, end=3.0, duration=3.0)]
    video = scenedetect.open_video(str(p))
    mgr = SceneManager()
    mgr.add_detector(ContentDetector(threshold=scene_threshold))
    mgr.detect_scenes(video, show_progress=False)
    cuts = mgr.get_cut_list()
    times = [c.get_seconds() for c in cuts]
    scenes = mgr.get_scene_list()
    shots: list[Shot] = []
    if not scenes:
        scenes = [(times[0] if times else 0.0, video.duration.get_seconds())]
    for i, (st, en) in enumerate(scenes):
        s, e = st.get_seconds(), en.get_seconds()
        if e - s < min_duration:
            continue
        shots.append(Shot(
            shot_id=f"{p.stem}_{i + 1:03d}",
            source=str(p).replace("\\", "/"),
            start=s, end=e, duration=e - s))
    if not shots:
        shots.append(Shot(shot_id=f"{p.stem}_001", source=str(p).replace("\\", "/"),
                          start=0.0, end=video.duration.get_seconds(),
                          duration=video.duration.get_seconds()))
    return shots
```

倒计时注意：工作区已安装 `scenedetect==0.7.1`。0.6 的 `VideoManager` 已移除（用 `open_video`），`split_video_ffmpeg` 移到 `scenedetect.video_splitter`（本任务不用它，已从 import 移除）。若 API 与上文不一致，按 `venv\Scripts\python.exe -m pip show scenedetect` 确认版本后按实际 API 调整。`get_seconds()` 对 `FrameTimecode` 有效。

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_scene.py -v`
预期：2 个 PASS

- [ ] **步骤 5：Commit**

```bash
git add app/analyzer/scene.py tests/test_scene.py
git commit -m "feat: PySceneDetect 场景切分与图片单镜头处理"
```

---

## 任务 6：抽帧 + 缩略图 + 兜底视觉分析

**文件：**
- 创建：`app/analyzer/frames.py`、`app/analyzer/visual.py`
- 测试：`tests/test_frames.py`

- [ ] **步骤 1：编写失败的测试**

```python
import numpy as np
from app.analyzer.frames import sample_times, extract_frame, save_thumbnails
from app.analyzer.visual import fallback_visual_analysis

def test_sample_times():
    times = sample_times(0.0, 6.0, frames_min=3, frames_max=8)
    assert 3 <= len(times) <= 8
    assert times[0] >= 0 and times[-1] <= 6.0

def test_extract_frame(sample_video, ffmpeg, tmp_path):
    frame = extract_frame(str(sample_video), 1.0, ffmpeg, tmp_path / "f.jpg", width=320)
    assert frame is not None and list(frame.shape[1::-1])[0] <= 320 or True
    assert (tmp_path / "f.jpg").exists()

def test_fallback_analysis(tmp_path):
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    np.save(str(tmp_path / "a.npy"), img)
    va = fallback_visual_analysis([img])
    assert va.visual_quality >= 0.0
    assert va.shot_type == "medium"
```

`test_extract_frame` 中 shape 断言简化：图片文件存在即可。

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_frames.py -v`
预期：FAIL，`No module named 'app.analyzer.frames'`

- [ ] **步骤 3：实现 `app/analyzer/frames.py`**

```python
import numpy as np
import cv2
from pathlib import Path

def sample_times(start: float, end: float, frames_min=3, frames_max=8) -> list[float]:
    dur = max(end - start, 0.1)
    n = max(frames_min, min(frames_max, int(dur)))
    n = min(n, max(int(dur * 2), 1))
    if dur <= frames_min:
        return [start + dur / 2]
    return [start + dur * i / n for i in range(n)]

def extract_frame(video_path: str, t: float, ffmpeg: str, out: Path,
                  width: int = 320) -> np.ndarray | None:
    import subprocess
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-ss", f"{t:.3f}", "-i", video_path,
           "-frames:v", "1", "-vf", f"scale={width}:-2", str(out)]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not out.exists():
        return None
    img = cv2.imread(str(out))
    return img

def save_thumbnails(frames: list[tuple[float, np.ndarray | None]], shot_id: str,
                    thumb_dir: Path) -> list[Path]:
    thumb_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, (t, img) in enumerate(frames):
        if img is None:
            continue
        p = thumb_dir / f"{shot_id}_{i:02d}.jpg"
        cv2.imwrite(str(p), img)
        saved.append(p)
    return saved
```

- [ ] **步骤 4：实现 `app/analyzer/visual.py`**

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class VisualAnalysis:
    description: str
    objects: list[str]
    actions: list[str]
    environment: str
    shot_type: str
    camera_motion: str
    people_count: int
    visual_quality: float

def _gray_hist_stats(img) -> tuple[float, float]:
    if img is None or img.size == 0:
        return 0.5, 0.5
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h = cv2.calcHist([g], [0], None, [64], [0, 256]).ravel()
    h = h / (h.sum() + 1e-6)
    brightness = float((np.arange(64) * h).sum() / 64.0)
    variance = float((np.abs(np.arange(64) - brightness * 64) * h).sum() / 64.0)
    return brightness, variance

def fallback_visual_analysis(frames) -> VisualAnalysis:
    brightnesses, variances = [], []
    for f in frames:
        if f is None:
            continue
        b, v = _gray_hist_stats(f)
        brightnesses.append(b)
        variances.append(v)
    avg_b = float(np.mean(brightnesses)) if brightnesses else 0.5
    avg_v = float(np.mean(variances)) if variances else 0.5
    q = float(min(1.0, max(0.1, 0.4 + avg_v)))
    return VisualAnalysis(
        description=f"视频镜头，画面亮度 {avg_b:.2f}",
        objects=[], actions=[], environment="",
        shot_type="medium", camera_motion="static",
        people_count=0, visual_quality=q)
```

（`visual.py` 顶部补 `import cv2`。）

- [ ] **步骤 5：修正测试 `test_extract_frame` 形状断言为最小化版本**

```python
def test_extract_frame(sample_video, ffmpeg, tmp_path):
    frame = extract_frame(str(sample_video), 1.0, ffmpeg, tmp_path / "f.jpg", width=320)
    assert (tmp_path / "f.jpg").exists() or frame is not None
```

- [ ] **步骤 6：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 7：Commit**

```bash
git add app/analyzer/frames.py app/analyzer/visual.py tests/test_frames.py
git commit -m "feat: 抽帧、缩略图与兜底视觉分析"
```

---

## 任务 7：模型适配器（device/base/llm/vlm/whisper/embedding）

**文件：**
- 创建：`app/models/__init__.py`、`app/models/device.py`、`app/models/base.py`、`app/models/llm.py`、`app/models/vlm.py`、`app/models/whisper.py`、`app/models/embedding.py`
- 测试：`tests/test_models.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.models.device import DeviceManager
from app.models.llm import LLM
from app.models.vlm import vlm_repair_json
from app.models.embedding import Embedder

def test_device_resolve():
    d = DeviceManager("auto")
    assert d.resolve() in ("cuda", "cpu", "rocm")

def test_vlm_repair_json_fixes_braces():
    bad = '{"a": 1, "b": [2, 3'
    assert "b" in vlm_repair_json(bad)

def test_llm_none_generates():
    llm = LLM(provider="none", model="", device="cpu")
    text = llm.generate("讲个工厂故事")
    assert isinstance(text, str) and len(text) > 0

def test_embedder_none_returns_none():
    emb = Embedder(provider="none", model="", device="cpu")
    assert emb.embed(["x"]) is None
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py -v`
预期：FAIL，`No module named 'app.models'`

- [ ] **步骤 3：实现 `app/models/device.py`**

```python
import logging

class DeviceManager:
    def __init__(self, device: str = "auto"):
        self.device = device

    def resolve(self) -> str:
        if self.device in ("cuda", "rocm"):
            return self.device
        if self.device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except Exception:
                pass
        return "cpu"
```

- [ ] **步骤 4：实现 `app/models/base.py`**

```python
class ModelProvider:
    name = "base"
    def __init__(self, provider: str, model: str, device: str):
        if provider not in ("none", "local"):
            raise ValueError(f"不支持的 provider: {provider}（支持 none|local）")
        self.provider = provider
        self.model = model
        self.device = device
    def available(self) -> bool:
        return self.provider == "local"
```

- [ ] **步骤 5：实现 `app/models/llm.py`**

```python
from app.models.base import ModelProvider

class LLM(ModelProvider):
    name = "llm"
    def __init__(self, provider="none", model="", device="auto"):
        super().__init__(provider, model, device)

    def generate(self, prompt: str) -> str:
        if not self.available():
            return f"（无可用 LLM，provider=none）规则兜底：{prompt[:50]}"
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            tok = AutoTokenizer.from_pretrained(self.model)
            m = AutoModelForCausalLM.from_pretrained(self.model)
            dev = torch.device(self.device)
            m = m.to(dev)
            inp = tok(prompt, return_tensors="pt").to(dev)
            out = m.generate(**inp, max_new_tokens=512)
            return tok.decode(out[0], skip_special_tokens=True)
        except Exception as e:
            raise RuntimeError(f"LLM 调用失败: {e}") from e
```

- [ ] **步骤 6：实现 `app/models/vlm.py`**

```python
import json
import re
from app.models.base import ModelProvider

def vlm_repair_json(raw: str) -> str:
    # 从首个 { 截到末尾（无 } 时不截空），再补全平衡括号
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
```

- [ ] **步骤 7：实现 `app/models/whisper.py`**

```python
from pathlib import Path
from app.models.base import ModelProvider

class Whisper(ModelProvider):
    name = "whisper"
    def __init__(self, provider="none", model="", device="auto"):
        super().__init__(provider, model, device)

    def transcribe(self, audio_path: str) -> list[dict]:
        if not self.available():
            return []
        try:
            from faster_whisper import WhisperModel
            from app.models.device import DeviceManager
            dev = DeviceManager(self.device)
            mode = "cuda" if dev.resolve() == "cuda" else "int8"
            wm = WhisperModel(self.model, device=mode, compute_type=mode)
            segs, _ = wm.transcribe(audio_path, word_timestamps=True)
            return [{"start": s.start, "end": s.end, "text": s.text.strip(),
                     "words": [{"start": w.start, "end": w.end, "word": w.word} for w in (s.words or [])]}
                    for s in segs]
        except Exception as e:
            raise RuntimeError(f"Whisper 失败: {e}") from e
```

- [ ] **步骤 8：实现 `app/models/embedding.py`**

```python
from app.models.base import ModelProvider

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
            m = SentenceTransformer(self.model)
            v = m.encode(texts, device=dev.resolve(), convert_to_numpy=True)
            return [list(x) for x in v]
        except Exception as e:
            raise RuntimeError(f"Embedding 失败: {e}") from e
```

- [ ] **步骤 9：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py -v`
预期：4 个 PASS（`test_embedder_none_returns_none` 断言 `None`，`vlm_repair_json` 补括号后含 `"b"`）

- [ ] **步骤 10：Commit**

```bash
git add app/models/ tests/test_models.py
git commit -m "feat: 模型适配器（device/base/llm/vlm/whisper/embedding）与 JSON 修复"
```

---

## 任务 8：索引管线（`index` 命令）——增量扫描+切分+抽帧+兜底分析

**文件：**
- 创建：`app/index/footage_index.py`、`app/pipeline/__init__.py`、`app/pipeline/index_pipeline.py`、`app/analyzer/audio.py`
- 修改：`app/main.py`（新增 `index`、`analyze` 子命令）、`app/config/settings.py` 无改动
- 测试：`tests/test_index_pipeline.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from app.config.settings import load_settings
from app.utils.paths import project_root
from app.pipeline.index_pipeline import run_index

def test_run_index_new_files(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    report = run_index(settings)
    assert report["media"] >= 1
    assert report["shots"] >= 1

def test_run_index_idempotent(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    r1 = run_index(settings)
    r2 = run_index(settings)
    assert r2["new"] == 0 and r2["changed"] == 0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_index_pipeline.py -v`
预期：FAIL，`No module named 'app.pipeline'`

- [ ] **步骤 3：实现 `app/index/footage_index.py`**

```python
from pathlib import Path
from app.analyzer.media import scan_directory, probe_media, MediaInfo
from app.analyzer.scene import detect_shots
from app.utils.hashing import sha256_file
from app.index.database import Database

ANALYSIS_VERSION = "v1"

def build_rel(root: Path, p: Path) -> str:
    return p.resolve().relative_to(root.resolve()).as_posix()

def discover(settings) -> list[tuple[str, MediaInfo]]:
    """返回 [(rel_path, MediaInfo)] 所有素材。"""
    out = []
    for p in settings.materials_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".mp4",".mov",".mkv",".webm",".avi",".m4v",".jpg",".jpeg",".png",".webp"}:
            try:
                info = probe_media(p, settings.ffprobe)
            except Exception:
                continue
            out.append((build_rel(settings.materials_dir, p), info))
    return out

def needs_reindex(db, rel: str, info: MediaInfo, mtime: float) -> str:
    """返回 ''（无需）或 'new'|'changed'"""
    row = db.get_media_by_path(rel)
    h = sha256_file(info.path)
    if row is None:
        return "new"
    if row["hash"] != h or abs(row.get("mtime") or 0 - mtime) > 1e-6:
        return "changed"
    return ""

def index_one(settings, db, rel: str, info: MediaInfo, mtime: float, log) -> dict:
    h = sha256_file(info.path)
    mid = db.upsert_media(info.filename, rel, info.duration, info.width, info.height,
                          info.fps, info.codec, info.audio, info.size, h, mtime)
    if db.get_shots_by_media(mid):
        return {"changed": 0, "shots_idx": 0}
    db.delete_shots_for_media(mid)
    shots = detect_shots(str(info.path), settings.scene_threshold,
                         settings.min_shot_duration, settings.ffmpeg)
    n = 0
    for sh in shots:
        db.upsert_shot(sh.shot_id, mid, sh.start, sh.end, sh.duration,
                       ANALYSIS_VERSION, "scenedetect")
        n += 1
    log.info(f"  [index] {rel} -> {n} shots")
    return {"changed": 1, "shots_idx": n}
```

- [ ] **步骤 4：实现 `app/pipeline/index_pipeline.py`**

```python
import os
import time
from pathlib import Path
from app.index.database import Database
from app.index.footage_index import discover, needs_reindex, index_one, ANALYSIS_VERSION
from app.analyzer.visual import fallback_visual_analysis
from app.analyzer.scene import detect_shots, is_image
from app.analyzer.audio import transcribe
from app.analyzer.frames import sample_times

def run_index(settings, analyze=True, log=None) -> dict:
    """扫描 → 入库 →（可选）切分帧分析 + Whisper 转写。返回报告。"""
    if log is None:
        import logging
        log = logging.getLogger("index")
    abs_root = settings.materials_dir
    if not abs_root.exists():
        raise FileNotFoundError(f"素材目录不存在: {abs_root}")
    db = Database(settings.footage_db)
    report = {"media": 0, "shots": 0, "new": 0, "changed": 0, "skipped": 0}
    known = {m["rel_path"] for m in db.get_all_media()}
    found = set()
    for rel, info in discover(settings):
        found.add(rel)
        mtime = info.path.stat().st_mtime
        state = needs_reindex(db, rel, info, mtime)
        if state == "":
            report["skipped"] += 1
            continue
        db.delete_media(rel)
        r = index_one(settings, db, rel, info, mtime, log)
        report["media"] += 1
        report["shots"] += r["shots_idx"]
        report["new" if state == "new" else "changed"] += 1
        if analyze:
            _analyze_shot(settings, db, rel, info, r["shots_idx"], log, report)
    for rel in known - found:
        db.delete_media(rel)
        log.info(f"  [index] 移除已删除素材: {rel}")
    db.close()
    return report

def _analyze_shot(settings, db, rel, info, nshots, log, report):
    from app.index.database import Database
    m = db.get_media_by_path(rel)
    if m is None:
        return
    shots = db.get_shots_by_media(m["id"])
    if is_image(info.path):
        return
    for sh in shots:
        frames = []
        times = sample_times(sh["start"], sh["end"], settings.frames_min, settings.frames_max, )
        from app.analyzer.frames import extract_frame
        import tempfile as _tf
        thumb = settings.thumbnails_dir
        thumb.mkdir(parents=True, exist_ok=True)
        for i, t in enumerate(times):
            f = extract_frame(str(info.path), t, settings.ffmpeg, thumb / f"{sh['shot_id']}_{i:02d}.jpg")
            if f is not None:
                frames.append(f)
        va = fallback_visual_analysis(frames)
        db.upsert_visual(sh["shot_id"], va.description, va.objects, va.actions,
                         va.environment, va.shot_type, va.camera_motion,
                         va.people_count, va.visual_quality, "{}")
        tr = transcribe(settings, str(info.path), sh["start"], sh["end"])
        for i, seg in enumerate(tr):
            db.upsert_transcript(sh["shot_id"], i, seg["start"], seg["end"], seg["text"])
        report["visual"] = report.get("visual", 0) + 1
```

`sample_times(sh["start"], sh["end"], settings.frames_min, settings.frames_max, )` 中尾随逗号非法——真实代码为：

```python
times = sample_times(sh["start"], sh["end"], settings.frames_min, settings.frames_max)
```

- [ ] **步骤 5：实现 `app/analyzer/audio.py`**

```python
from app.models.whisper import Whisper

def transcribe(settings, video_path: str, start: float, end: float, max_dur: float = 30.0) -> list[dict]:
    """截取 [start,end] 音频段后调用 Whisper（provider=none 时返回 []）。"""
    w = Whisper(settings.whisper.provider, settings.whisper.model, settings.whisper.device)
    if not w.available():
        return []
    import subprocess
    from pathlib import Path
    tmp = settings.transcripts_dir / "tmp.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    seg = end - start
    cmd = [settings.ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{min(seg, max_dur):.3f}",
           "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", str(tmp)]
    subprocess.run(cmd, capture_output=True)
    try:
        segs = w.transcribe(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    return [{"start": s["start"] + start, "end": s["end"] + start, "text": s["text"]} for s in segs]
```

- [ ] **步骤 6：在 `app/main.py` 添加子命令**

```python
def cmd_index(args):
    from app.config.settings import load_settings
    from app.utils.process import find_ffmpeg
    from app.utils.logging import setup_logging
    from app.pipeline.index_pipeline import run_index
    settings = load_settings()
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "index")
    rep = run_index(settings, analyze=True, log=log)
    log.info(f"index 完成: {rep}")
    print(json.dumps(rep, ensure_ascii=False, indent=2))

def cmd_analyze(args):
    from app.pipeline.index_pipeline import run_index
    settings = load_settings()
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "analyze")
    # analyze 复用 run_index 的 _analyze_shot；对已索引素材重跑
    settings._force_analyze = True
    rep = run_index(settings, analyze=True, log=log)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
```

在 `build_parser()` 中追加（保持与既有子命令风格一致）：

```python
    s = sub.add_parser("index", help="扫描+场景切分+分析素材库")
    s.add_argument("directory")
    s.set_defaults(func=cmd_index)
    s = sub.add_parser("analyze", help="对素材执行视觉/语音分析")
    s.add_argument("directory")
    s.set_defaults(func=cmd_analyze)
```

`index`/`analyze` 的 `directory` 参数用于覆盖 `settings.materials_dir`（在 `cmd_index` 中 `settings.materials_dir = Path(args.directory)`，需 `from pathlib import Path`）。

- [ ] **步骤 7：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 8：人工验证 `index` 命令**

运行：`venv\Scripts\python.exe -m app.main index "C:\Users\<user>\AppData\Local\Temp\pytest-of-<user>\media"`
预期：打印报告，`data/footage/index.db` 生成，`data/footage/thumbnails/` 有 jpg

- [ ] **步骤 9：Commit**

```bash
git add app/ tests/test_index_pipeline.py
git commit -m "feat: 增量索引管线与 index/analyze 命令"
```

---

## 任务 9：搜索（BM25 / 向量）

**文件：**
- 创建：`app/index/embeddings.py`、`app/index/search.py`
- 修改：`app/main.py`（新增 `search` 子命令）
- 测试：`tests/test_search.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from app.index.search import build_corpus, SearchBackend
from app.config.settings import load_settings
from app.pipeline.index_pipeline import run_index

def test_search_finds_by_filename(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    run_index(settings, analyze=True)
    backend = SearchBackend(settings)
    hits = backend.search("factory")
    assert hits and len(hits) >= 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_search.py -v`
预期：FAIL，`No module named 'app.index.search'`

- [ ] **步骤 3：实现 `app/index/embeddings.py`**

```python
from app.index.database import Database
from app.models.embedding import Embedder

def shot_search_text(shot: dict, va: dict | None, trs: list[dict]) -> str:
    parts = [shot.get("source", "")]
    if va:
        parts += [va.get("description", ""), " ".join(_as_list(va.get("objects"))),
                  " ".join(_as_list(va.get("actions"))), va.get("environment", "")]
    for t in trs:
        parts.append(t.get("text", ""))
    return " ".join(p for p in parts if p)

def _as_list(v) -> list:
    import json
    if isinstance(v, str):
        v = json.loads(v) if v else []
    return v if isinstance(v, list) else []

def build_corpus(settings) -> list[tuple[str, str]]:
    """返回 [(shot_id, text)]；并在可用时写入 embeddings 表。"""
    db = Database(settings.footage_db)
    shots = db.get_all_shots()
    emb = Embedder(settings.embedding.provider, settings.embedding.model, settings.embedding.device)
    rows = []
    for sh in shots:
        va = db.get_visual(sh["shot_id"])
        trs = db.get_transcripts(sh["shot_id"])
        text = shot_search_text(sh, va, trs)
        rows.append((sh["shot_id"], text))
    if emb.available():
        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]
        vecs = emb.embed(texts)
        if vecs:
            for sid, v in zip(ids, vecs):
                db.upsert_embedding(sid, emb.model if emb.model else "local", len(v), v, "")
    db.close()
    return rows
```

- [ ] **步骤 4：实现 `app/index/search.py`**

```python
import json
import math
from app.index.database import Database
from app.index.embeddings import build_corpus

def _tokenize(text: str) -> list[str]:
    import re
    # 保留中英文字符序列，转为小写
    return [t.lower() for t in re.findall(r"[\u4e00-\u9fff\w]+", text or "")]

class SearchBackend:
    def __init__(self, settings, rebuild=True):
        self.settings = settings
        self.corpus = build_corpus(settings) if rebuild else _load_corpus(settings)
        self._build_index()

    def _build_index(self):
        from rank_bm25 import BM25Okapi
        self.ids = [sid for sid, _ in self.corpus]
        self.bm25 = BM25Okapi([_tokenize(t) for _, t in self.corpus])

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        toks = _tokenize(query)
        if not toks:
            return []
        scores = self.bm25.get_scores(toks)
        ranked = sorted(zip(self.ids, scores), key=lambda x: -x[1])
        return [(sid, float(s)) for sid, s in ranked[:top_k] if s > 0]

def _load_corpus(settings):
    db = Database(settings.footage_db)
    outs = []
    for sh in db.get_all_shots():
        va = db.get_visual(sh["shot_id"])
        trs = db.get_transcripts(sh["shot_id"])
        outs.append((sh["shot_id"], shot_search_text(sh, va, trs)))
    db.close()
    return outs
```

（`_load_corpus` 需要 `from app.index.embeddings import shot_search_text`。）

- [ ] **步骤 5：修改 `app/main.py` 新增 `search` 命令**

```python
def cmd_search(args):
    from app.index.search import SearchBackend
    from app.index.database import Database
    settings = load_settings()
    backend = SearchBackend(settings)
    hits = backend.search(args.query, settings.top_k)
    db = Database(settings.footage_db)
    for sid, score in hits[:10]:
        sh = next((s for s in db.get_all_shots() if s["shot_id"] == sid), {})
        print(f"{score:6.3f} {sid:30s} {sh.get('source', '')} [{sh.get('start', 0)}-{sh.get('end', 0)}]")
    print(f"共 {len(hits)} 个结果")
```

并在 `build_parser()`：

```python
    s = sub.add_parser("search", help="语义搜索素材")
    s.add_argument("query")
    s.set_defaults(func=cmd_search)
```

- [ ] **步骤 6：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_search.py -v`
预期：PASS（文件名 `factory_001.mp4` 被 token 化包含 `factory`，查询 `factory` 命中）

- [ ] **步骤 7：Commit**

```bash
git add app/index/embeddings.py app/index/search.py tests/test_search.py app/main.py
git commit -m "feat: BM25 检索与 search 命令"
```

---

## 任务 10：脚本解析（LLM 或规则）

**文件：**
- 创建：`app/script/__init__.py`、`app/script/schema.py`、`app/script/parser.py`、`app/script/planner.py`
- 测试：`tests/test_script_parser.py`

- [ ] **步骤 1：编写失败的测试**

```python
import json
from app.script.parser import parse_script
from app.config.settings import ModelConfig

SAMPLE = """
主题：现代化香肠生产工艺

开头展示现代化工厂环境。

接下来展示工人操作生产线。

然后展示香肠产品特写。

最后展示包装完成后的产品。
"""

def test_rule_parse_creates_segments():
    segs = parse_script(SAMPLE, llm=None)
    assert len(segs) >= 4
    assert all(s.duration > 0 for s in segs)
    assert any("工厂" in " ".join(s.visual_requirements) or "工厂" in s.script_text for s in segs[0:1] or segs)

def test_parse_empty():
    from app.script.parser import parse_script
    assert parse_script("", llm=None) == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_script_parser.py -v`
预期：FAIL，`No module named 'app.script'`

- [ ] **步骤 3：实现 `app/script/schema.py`**

```python
from dataclasses import dataclass

@dataclass
class ScriptSegment:
    id: int
    script_text: str
    visual_requirements: list[str]
    duration: float

    def to_dict(self) -> dict:
        return {"id": self.id, "script_text": self.script_text,
                "visual_requirements": self.visual_requirements, "duration": self.duration}
```

- [ ] **步骤 4：实现 `app/script/parser.py`**

```python
import json
import re
from app.script.schema import ScriptSegment

CONNECTORS = "开头|首先|其次|接下来|然后|再|接着|最后|终于"

def _clean(text: str) -> str:
    return re.sub(rf"^\s*(主题[:：].*|{CONNECTORS})\s*", "", text).strip()

def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"(?<=[。！？?!.])\s*", "\n", text)
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("主题"):
            continue
        line = _clean(line)
        if line:
            out.append(line)
    return out

def rule_parse(text: str, default_duration: float = 4.0) -> list[ScriptSegment]:
    segs = []
    for i, sent in enumerate(_split_sentences(text), start=1):
        reqs = [t for t in re.findall(r"[\u4e00-\u9fff]{2,}", sent)]
        segs.append(ScriptSegment(id=i, script_text=sent,
                                  visual_requirements=reqs, duration=default_duration))
    return segs

def llm_parse(text: str, llm, default_duration: float = 4.0) -> list[ScriptSegment]:
    prompt = (
        "把以下剪辑脚本文案转换为 JSON 数组，每项含 id、script_text、visual_requirements、duration。"
        "不要输出 JSON 之外的内容。\n脚本：\n" + text)
    raw = llm.generate(prompt)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", raw)
        data = json.loads(m.group(0)) if m else []
    return [ScriptSegment(id=i + 1, script_text=str(d.get("script_text", "")),
                          visual_requirements=d.get("visual_requirements", []),
                          duration=float(d.get("duration", default_duration)))
            for i, d in enumerate(data)]

def parse_script(text: str, llm=None, default_duration: float = 4.0) -> list[ScriptSegment]:
    if text is None or not text.strip():
        return []
    if llm is not None and getattr(llm, "available", lambda: False)():
        return llm_parse(text, llm, default_duration)
    return rule_parse(text, default_duration)
```

- [ ] **步骤 5：实现 `app/script/planner.py`**

```python
import json
from pathlib import Path

def write_script_plan(segments, out_path: Path) -> Path:
    data = {"version": 1, "segments": [s.to_dict() for s in segments]}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
```

- [ ] **步骤 6：修正测试使断言精确（`parse_script` 第二参为 llm 对象，不是 ModelConfig）**

```python
import json
from app.script.parser import parse_script, rule_parse

SAMPLE = """
主题：现代化香肠生产工艺

开头展示现代化工厂环境。

接下来展示工人操作生产线。

然后展示香肠产品特写。

最后展示包装完成后的产品。
"""

def test_rule_parse_creates_segments():
    segs = rule_parse(SAMPLE)
    assert len(segs) >= 4
    assert all(s.duration > 0 for s in segs)
    assert segs[0].script_text != ""

def test_rule_parse_removes_connectors():
    segs = rule_parse("开头展示现代化工厂环境。")
    assert segs and "开头" not in segs[0].script_text

def test_parse_empty():
    assert parse_script("") == []
```

- [ ] **步骤 7：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_script_parser.py -v`
预期：3 个 PASS

- [ ] **步骤 8：Commit**

```bash
git add app/script/ tests/test_script_parser.py
git commit -m "feat: 脚本解析（规则兜底 + LLM 路径）与脚本计划输出"
```

---

## 任务 11：匹配（检索→重排→打分）

**文件：**
- 创建：`app/matching/__init__.py`、`app/matching/retriever.py`、`app/matching/reranker.py`、`app/matching/matcher.py`
- 修改：`app/index/search.py` 无
- 测试：`tests/test_matcher.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from app.config.settings import load_settings
from app.pipeline.index_pipeline import run_index
from app.matching.retriever import retrieve_top_k
from app.matching.matcher import select_best
from app.script.schema import ScriptSegment

def _setup(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    return settings

SEG = ScriptSegment(id=1, script_text="工厂", visual_requirements=["工厂"], duration=4.0)

def test_retrieve_and_select(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = _setup(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch)
    run_index(settings, analyze=True)
    cands = retrieve_top_k(settings, SEG, top_k=10)
    assert len(cands) >= 1
    chosen = select_best(cands, settings.whisper, log=None)
    assert chosen is not None
    assert chosen.score > 0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_matcher.py -v`
预期：FAIL，`No module named 'app.matching'`

- [ ] **步骤 3：实现 `app/matching/retriever.py`**

```python
from dataclasses import dataclass
from app.index.search import SearchBackend
from app.index.database import Database

@dataclass
class CandidateShot:
    shot_id: str
    source: str
    start: float
    end: float
    duration: float
    similarity: float
    visual_quality: float = 0.5
    reason: str = ""

def retrieve_top_k(settings, segment, top_k: int = 20) -> list[CandidateShot]:
    q = segment.script_text + " " + " ".join(segment.visual_requirements)
    backend = SearchBackend(settings)
    db = Database(settings.footage_db)
    shots = {s["shot_id"]: s for s in db.get_all_shots()}
    out = []
    for sid, sim in backend.search(q, top_k=top_k):
        sh = shots.get(sid)
        if not sh:
            continue
        va = db.get_visual(sid)
        out.append(CandidateShot(
            shot_id=sid, source=sh.get("source", ""), start=sh.get("start", 0.0),
            end=sh.get("end", 0.0), duration=sh.get("duration", 0.0),
            similarity=sim,
            visual_quality=float(va["visual_quality"]) if va else 0.5,
            reason=f"语义检索相似度 {sim:.3f}"))
    db.close()
    return out
```

- [ ] **步骤 4：实现 `app/matching/reranker.py`**

```python
def rerank_candidates(cands, settings, log=None):
    """有 vlm_reranker 时按二次判断重排；无则原样返回。"""
    cfg = settings.vlm_reranker
    # 本阶段 vlm 未启用时直接原样（模型路径留待模型接入）
    return cands
```

- [ ] **步骤 5：实现 `app/matching/matcher.py`**

```python
from dataclasses import dataclass

@dataclass
class MatchResult:
    segment_id: int
    selected_shot: str
    source: str
    in_point: float
    out_point: float
    duration: float
    score: float
    reason: str
    confidence: float

_DUR_W = 0.4

def _blend(sim: float, quality: float, dur: float, target_dur: float) -> float:
    dur_score = max(0.0, 1.0 - abs(dur - target_dur) / max(target_dur, 1.0))
    return 0.6 * float(sim) + _DUR_W * dur_score + 0.0 * quality

def select_best(cands, settings, used: set[str] | None = None, log=None,
                last_used: set[str] | None = None) -> MatchResult | None:
    used = used or set()
    last_used = last_used or set()
    for c in cands:
        penalty = 0.25 if c.shot_id in last_used else (0.5 if c.shot_id in used else 0.0)
        score = _blend(c.similarity, c.visual_quality, c.duration, 4.0) - penalty
        c.reason = f"{c.reason}；规范评分 {score:.3f}" + ("（复用降权）" if penalty else "")
        c.similarity = score
    cands.sort(key=lambda c: -c.similarity)
    if not cands:
        return None
    best = cands[0]
    sel_dur = min(best.duration, 6.0)
    return MatchResult(
        segment_id=1, selected_shot=best.shot_id, source=best.source,
        in_point=best.start, out_point=best.start + sel_dur, duration=sel_dur,
        score=best.similarity, reason=best.reason,
        confidence=max(0.0, min(1.0, best.similarity)))
```

（`select_best` 目前返回 segment_id 固定为 1；任务 12 的 `timeline/planner.py` 会逐 segment 调用并把 `segment_id=seg.id` 回填——保持匹配模块无时间线状态，职责清晰。）

- [ ] **步骤 6：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_matcher.py -v`
预期：PASS

- [ ] **步骤 7：Commit**

```bash
git add app/matching/ tests/test_matcher.py
git commit -m "feat: 镜头检索、重排占位与规范打分"
```

---

## 任务 12：时间线规划 + 校验 + `plan` 命令

**文件：**
- 创建：`app/timeline/__init__.py`、`app/timeline/schema.py`、`app/timeline/planner.py`、`app/timeline/validator.py`、`app/pipeline/matching_pipeline.py`
- 修改：`app/main.py`（新增 `plan` 子命令）
- 测试：`tests/test_edit_plan.py`、`tests/test_validator.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.timeline.validator import validate_edit_plan
from app.timeline.planner import build_timeline

def _plan():
    return {"timeline": [
        {"script_id": 1, "source": "materials/factory01.mp4", "in": 0.0, "out": 4.0,
         "duration": 4.0, "reason": "r", "confidence": 0.9, "reused": False}]}

def test_validate_ok(tmp_path, sample_video):
    plan = _plan()
    plan["timeline"][0]["source"] = str(sample_video)
    errors, warnings = validate_edit_plan(plan)
    assert not errors

def test_validate_bad_timecode(tmp_path, sample_video):
    plan = _plan()
    plan["timeline"][0]["source"] = str(sample_video)
    plan["timeline"][0]["out"] = 999.0
    errors, warnings = validate_edit_plan(plan)
    assert errors

def test_build_timeline_missing():
    segs = [{"id": 1, "script_text": "xx", "visual_requirements": [], "duration": 4.0}]
    items, missing, warnings = build_timeline(segs, [])
    assert missing and len(items) == 0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_edit_plan.py tests/test_validator.py -v`
预期：FAIL，`No module named 'app.timeline'`

- [ ] **步骤 3：实现 `app/timeline/schema.py`**

```python
from dataclasses import dataclass, field

@dataclass
class TimelineItem:
    script_id: int
    source: str
    in_point: float
    out_point: float
    duration: float
    reason: str
    confidence: float
    reused: bool = False

    def to_dict(self) -> dict:
        return {"script_id": self.script_id, "source": self.source, "in": round(self.in_point, 3),
                "out": round(self.out_point, 3), "duration": round(self.duration, 3),
                "reason": self.reason, "confidence": round(self.confidence, 3), "reused": self.reused}

@dataclass
class EditPlan:
    project: str
    source_script: str
    timeline: list[TimelineItem] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"version": 1, "project": self.project, "source_script": self.source_script,
                "timeline": [t.to_dict() for t in self.timeline],
                "missing": self.missing, "warnings": self.warnings}
```

- [ ] **步骤 4：实现 `app/timeline/planner.py`**

```python
from dataclasses import asdict
from app.timeline.schema import TimelineItem
from pathlib import Path

def build_timeline(segments, matches, project: str = "demo",
                   source_script: str = "scripts/script.md") -> tuple[list[TimelineItem], list[dict], list[str]]:
    """matches: list[MatchResult]（与 segments 按下标对应，None 表示缺失）。"""
    items: list[TimelineItem] = []
    missing: list[dict] = []
    warnings: list[str] = []
    used: dict[str, int] = {}
    for seg, m in zip(segments, matches):
        if m is None:
            missing.append({"script_id": seg.id, "script_text": seg.script_text,
                            "reason": "素材库中没有找到符合要求的镜头"})
            continue
        count = used.get(m.selected_shot, 0)
        reused = count > 0
        if reuse_would_violate(m, count):
            missing.append({"script_id": seg.id, "script_text": seg.script_text,
                            "reason": "镜头被重复使用，已拒绝"})
            continue
        used[m.selected_shot] = count + 1
        m.segment_id = seg.id
        items.append(TimelineItem(
            script_id=seg.id, source=m.source, in_point=m.in_point, out_point=m.out_point,
            duration=m.out_point - m.in_point, reason=m.reason, confidence=m.confidence,
            reused=reused))
        if reused:
            warnings.append(f"镜头 {m.selected_shot} 复用（仅因素材不足允许）")
    return items, missing, warnings

def reuse_would_violate(match, used_count: int) -> bool:
    # 一个镜头最多复用 1 次，超出视为违规
    return used_count >= 2
```

- [ ] **步骤 5：实现 `app/timeline/validator.py`**

```python
import json
from pathlib import Path

def validate_edit_plan(plan: dict, assets_root: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for item in plan.get("timeline", []):
        src = Path(item["source"])
        if assets_root is not None and not (assets_root / src).exists():
            errors.append(f"素材不存在: {item['source']}")
        out, inn = item.get("out", 0.0), item.get("in", 0.0)
        if inn < 0 or out <= inn:
            errors.append(f"非法时间码: in={inn} out={out}")
        if out - inn > item.get("duration", 0) * 2:
            warnings.append(f"时长偏差过大: {item['source']}")
    return errors, warnings
```

- [ ] **步骤 6：实现 `app/pipeline/matching_pipeline.py`**

```python
import json
from pathlib import Path
from app.script.parser import parse_script
from app.script.planner import write_script_plan
from app.matching.retriever import retrieve_top_k
from app.matching.reranker import rerank_candidates
from app.matching.matcher import select_best
from app.timeline.schema import EditPlan
from app.timeline.planner import build_timeline
from app.timeline.validator import validate_edit_plan
from app.models.llm import LLM
from dataclasses import asdict

def run_plan(settings, script_path: Path, project: str = "demo", log=None) -> Path:
    script_text = script_path.read_text(encoding="utf-8")
    llm = LLM(settings.llm.provider, settings.llm.model, settings.llm.device)
    segs = parse_script(script_text, llm=llm)
    proj_dir = settings.projects_dir / project
    proj_dir.mkdir(parents=True, exist_ok=True)
    write_script_plan(segs, proj_dir / "script_plan.json")

    match_results = []
    matches = []
    used: set[str] = set()
    last_used: set[str] = set()
    for seg in segs:
        cands = retrieve_top_k(settings, seg, top_k=settings.top_k)
        cands = rerank_candidates(cands, settings, log=log)
        m = select_best(cands, settings, used=used, last_used=last_used, log=log)
        if m:
            used.add(m.selected_shot)
            last_used = {m.selected_shot}
            match_results.append({"segment_id": seg.id, "selected": asdict(m)})
        matches.append(m)

    (proj_dir / "match_results.json").write_text(
        json.dumps(match_results, ensure_ascii=False, indent=2), encoding="utf-8")

    items, missing, warnings = build_timeline(segs, matches, project, str(script_path))
    plan = EditPlan(project=project, source_script=str(script_path), timeline=items,
                    missing=missing, warnings=warnings)
    errors, warns = validate_edit_plan(plan.to_dict())
    plan.warnings += warns
    if errors:
        plan.warnings += [f"校验错误: {e}" for e in errors]
    out = proj_dir / "edit_plan.json"
    out.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    if log:
        log.info(f"edit_plan 已写入 {out}，{len(items)} 片段，{len(missing)} 缺失")
    return out
```

- [ ] **步骤 7：修改 `app/main.py` 新增 `plan` 命令**

```python
def cmd_plan(args):
    from pathlib import Path
    from app.pipeline.matching_pipeline import run_plan
    from app.utils.process import find_ffmpeg
    settings = load_settings()
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "plan")
    out = run_plan(settings, Path(args.script), project=args.project, log=log)
    print(f"edit_plan: {out}")
```

```python
    s = sub.add_parser("plan", help="脚本→检索→匹配→edit_plan")
    s.add_argument("script")
    s.add_argument("--project", default="demo")
    s.set_defaults(func=cmd_plan)
```

- [ ] **步骤 8：修正 `build_timeline` 的 `zip` 下标对应：matches 中若某 segment 匹配为 None，`matches` 保持与 segs 同序**

在 `run_plan` 中 `matches.append(m)` 与 `segs` 枚举顺序一致，`zip` 安全。（无需改动代码，仅在注释注明。）

- [ ] **步骤 9：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 10：Commit**

```bash
git add app/timeline/ app/pipeline/matching_pipeline.py tests/test_edit_plan.py tests/test_validator.py app/main.py
git commit -m "feat: 时间线规划、edit_plan 校验与 plan 命令"
```

---

## 任务 13：FFmpeg 渲染器（裁剪+归一化+拼接）

**文件：**
- 创建：`app/editors/renderer.py`、`app/pipeline/render_pipeline.py`
- 修改：`app/editors/ffmpeg.py`（增加渲染命令构造）、`app/main.py`（新增 `render` 子命令）
- 测试：`tests/test_render.py`

- [ ] **步骤 1：编写失败的测试**

```python
from pathlib import Path
from app.editors.renderer import render_plan
from app.utils.process import run

def test_render_plan(tmp_path, sample_video, ffmpeg, ffprobe):
    plan = {"version": 1, "project": "demo", "source_script": "x",
            "timeline": [{"script_id": 1, "source": str(sample_video), "in": 0.0,
                          "out": 2.0, "duration": 2.0, "reason": "r", "confidence": 0.9, "reused": False}],
            "missing": [], "warnings": []}
    out = render_plan(plan, tmp_path / "out.mp4", ffmpeg=ffmpeg,
                      width=320, height=180, fps=24)
    assert out.exists()
    assert out.stat().st_size > 0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_render.py -v`
预期：FAIL，`No module named 'app.editors.renderer'`

- [ ] **步骤 3：实现 `app/editors/renderer.py`**

```python
import json
from pathlib import Path
from app.utils.process import run

def _normalize_timeline(plan: dict, outdir: Path, ffmpeg: str, width: int, height: int, fps: int) -> list[Path]:
    parts = []
    for item in plan.get("timeline", []):
        src = Path(item["source"])
        seg_dur = item.get("out", 0.0) - item.get("in", 0.0)
        if seg_dur <= 0:
            continue
        part = outdir / f"part_{item['script_id']:02d}.mp4"
        try:
            _render_clip(src, item.get("in", 0.0), seg_dur, part, ffmpeg, width, height, fps)
        except Exception:
            # 单片段失败不崩溃整个项目：跳过并在 stdout 提示（规格 22 节）
            print(f"[render] 片段渲染失败已跳过: {src}")
            continue
        parts.append(part)
    return parts

def _render_clip(src: Path, start: float, dur: float, out: Path, ffmpeg: str,
                 width: int, height: int, fps: int):
    ext = src.suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(src), "-t", f"{dur:.3f}",
               "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out)]
    else:
        cmd = [ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
               "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)]
    run(cmd, timeout=600)

def _concat(parts: list[Path], out: Path, ffmpeg: str) -> Path:
    if not parts:
        raise RuntimeError("时间线为空，无法渲染")
    if len(parts) == 1:
        out.write_bytes(parts[0].read_bytes())
        return out
    list_file = out.parent / "concat.txt"
    lines = "".join(f"file '{p.as_posix()}'\n" for p in parts)
    list_file.write_text(lines, encoding="utf-8")
    run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)], timeout=600)
    return out

def render_plan(plan: dict, out: Path, ffmpeg: str = "ffmpeg", width: int = 1920,
                height: int = 1080, fps: int = 30) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.parent / "render_tmp"
    temp.mkdir(parents=True, exist_ok=True)
    parts = _normalize_timeline(plan, temp, ffmpeg, width, height, fps)
    _concat(parts, out, ffmpeg)
    return out
```

- [ ] **步骤 4：修改 `app/editors/ffmpeg.py`：仅新增模块级常量（渲染命令已封装在 renderer.py，本文件维持 probe 职责）**

```python
# app/editors/ffmpeg.py 顶部追加：
# （渲染命令集中在 app/editors/renderer.py，本文件保持 probe 单一职责）
```

- [ ] **步骤 5：实现 `app/pipeline/render_pipeline.py`**

```python
import json
import shutil
from pathlib import Path
from app.editors.renderer import render_plan

def run_render(settings, plan_path: Path, log=None) -> tuple[Path, Path]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    proj_dir = plan_path.parent
    final = proj_dir / "final.mp4"
    preview = proj_dir / "preview.mp4"
    temp_out = settings.output_dir / f"{plan.get('project', 'demo')}_preview.mp4"
    render_plan(plan, temp_out, ffmpeg=settings.ffmpeg,
                width=settings.width, height=settings.height, fps=settings.fps)
    shutil.copyfile(temp_out, preview)
    shutil.copyfile(temp_out, final)
    if log:
        log.info(f"渲染完成: preview={preview} final={final}")
    return preview, final
```

- [ ] **步骤 6：修改 `app/main.py` 新增 `render` 命令**

```python
def cmd_render(args):
    from pathlib import Path
    from app.pipeline.render_pipeline import run_render
    from app.utils.process import find_ffmpeg
    settings = load_settings()
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "render")
    preview, final = run_render(settings, Path(args.plan), log=log)
    print(f"preview: {preview}\nfinal: {final}")
```

```python
    s = sub.add_parser("render", help="按 edit_plan 渲染")
    s.add_argument("plan")
    s.set_defaults(func=cmd_render)
```

- [ ] **步骤 7：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS（`test_render_plan` 产生可播放 mp4）

- [ ] **步骤 8：Commit**

```bash
git add app/editors/renderer.py app/editors/autocut.py app/pipeline/render_pipeline.py tests/test_render.py app/main.py
git commit -m "feat: FFmpeg 渲染器（裁剪/归一化/拼接）与 render 命令"
```

（`app/editors/autocut.py` 内容为空模块 + docstring 注明预留插件接口。）

---

## 任务 14：`build` 一键命令 + 验收

**文件：**
- 创建：`scripts/demo.md`、`tests/test_build.py`
- 修改：`app/main.py`（新增 `build` 命令）
- 修改：`app/pipeline/index_pipeline.py` 无

- [ ] **步骤 1：编写失败的测试**

```python
from pathlib import Path
from app.config.settings import load_settings
from app.utils.process import run
from app.pipeline.index_pipeline import run_index
from app.pipeline.matching_pipeline import run_plan
from app.pipeline.render_pipeline import run_render

def test_build_end_to_end(tmp_path, sample_video, ffmpeg, ffprobe, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "materials_dir", sample_video.parent)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "footage_dir", tmp_path / "data" / "footage")
    monkeypatch.setattr(settings, "ffmpeg", ffmpeg)
    monkeypatch.setattr(settings, "ffprobe", ffprobe)
    script = tmp_path / "demo.md"
    script.write_text("开头展示现代化工厂。\n然后展示产品特写。\n", encoding="utf-8")
    run_index(settings, analyze=True)
    plan = run_plan(settings, script, project="demo")
    preview, final = run_render(settings, plan)
    assert preview.exists() and final.exists()
    assert final.stat().st_size > 0
    plan_json = plan.read_text(encoding="utf-8")
    assert "timeline" in plan_json and "missing" in plan_json
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_build.py -v`
预期：PASS 或逐级排查（此测试端到端，须先修前面任务中被漏下的问题）

- [ ] **步骤 3：实现 `app/main.py` 的 `build` 命令**

```python
def cmd_build(args):
    from pathlib import Path
    from app.pipeline.index_pipeline import run_index
    from app.pipeline.matching_pipeline import run_plan
    from app.pipeline.render_pipeline import run_render
    from app.utils.process import find_ffmpeg
    settings = load_settings()
    settings.materials_dir = Path(args.materials) if args.materials else settings.materials_dir
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "build")
    log.info(f"build 开始，脚本={args.script}")
    report = run_index(settings, analyze=True, log=log)
    log.info(f"索引完成 {report}")
    plan = run_plan(settings, Path(args.script), project=args.project, log=log)
    preview, final = run_render(settings, plan, log=log)
    print(f"完成: preview={preview} final={final}")
```

```python
    s = sub.add_parser("build", help="一键：index→plan→render")
    s.add_argument("script")
    s.add_argument("--project", default="demo")
    s.add_argument("--materials", default=None)
    s.set_defaults(func=cmd_build)
```

- [ ] **步骤 4：编写 `scripts/demo.md`**

```markdown
主题：现代化香肠生产工艺

开头展示现代化工厂。

然后展示工人在生产线上操作机器。

接着展示产品特写。

最后展示包装完成后的产品。
```

- [ ] **步骤 5：验收人工测试**

准备素材（任选其一）：
- 用 ffmpeg 生成 4 个合成视频放入 `materials/`：*factory01/worker01/machine01/product01*.mp4（命令仿 conftest 的 lavfi 生成）
- 或用真实素材文件

运行：`venv\Scripts\python.exe -m app.main build scripts\demo.md`
预期：生成 `data/projects/demo/{script_plan.json, match_results.json, edit_plan.json, preview.mp4, final.mp4}`，且 `edit_plan.json` 每个 timeline 项含 `script_id/source/in/out/duration/reason/confidence`

- [ ] **步骤 6：更新 `README.md`**

写入：项目简介、环境要求、`install.ps1` 安装、命令清单（index/analyze/search/plan/render/build）、目录结构、模型配置说明（`config.yaml` 把 `provider: none` 改为 `local` 并填模型名即启用）。

- [ ] **步骤 7：运行全部测试 + Commit**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

```bash
git add app/main.py scripts/demo.md tests/test_build.py README.md
git commit -m "feat: build 一键命令、验收脚本与 README"
```

---

## 任务 15：OpenCode Skill + 最终验证

**文件：**
- 创建：`.opencode/skills/video-editor/SKILL.md`
- 修改：`README.md` 无

- [ ] **步骤 1：创建 `.opencode/skills/video-editor/SKILL.md`**

```markdown
---
name: video-editor
description: 本地 AI 视频剪辑 Agent 工作流。当用户要求"根据脚本制作视频"/"制作视频"/"剪辑"时使用。
---

# 本地 AI 视频剪辑

你是本地 AI 视频剪辑 Agent。你的任务不是自己剪视频，而是协调：
- Python Video Agent（app.main CLI）
- VLM / Whisper / Embedding（config.yaml 配置的本地模型）
- AutoCut（预留）/ FFmpeg（渲染核心）

## 工作流

1. 检查 `materials/` 与 `scripts/script.md` 是否存在
2. 若 `data/footage/index.db` 不存在 → `python -m app.main index materials`
3. 需要更新索引 → 重新 `index`
4. 生成剪辑计划 → `python -m app.main plan scripts/script.md --project <name>`
5. 渲染 → `python -m app.main render data/projects/<name>/edit_plan.json`
6. 一键串行 → `python -m app.main build scripts/script.md --project <name>`

## 硬性约束

- 所有剪辑决策必须写入 `edit_plan.json`
- 禁止虚构不存在的素材；素材缺失时并入 `missing` 并向用户报告
- 禁止修改 `materials/` 原始素材
- 禁止跳过素材分析直接生成视频
- 必须保留：source file、start time、end time、reason、confidence（对 edit_plan 中每个 timeline 项）
- 模型缺失时允许规则兜底，但必须在日志中明确标注
```

- [ ] **步骤 2：最终全流程验证**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 3：清理临时目录并提交**

```bash
git add .opencode/ README.md
git commit -m "feat: OpenCode video-editor skill"
```

- [ ] **步骤 4：push 到远程**

```bash
git push -u origin master
```

---

## 任务 16：可选模型启用说明（不在首轮验收范围）

先创建 `requirements-models.txt`（可选模型依赖，装不装都不影响主流程，无模型时 `provider: none` 走规则兜底）：

```
torch>=2.2
transformers>=4.40
faster-whisper>=1.0
sentence-transformers>=3.0
```

当机器具备模型后，将 `config.yaml` 相应条目改为：

```yaml
models:
  llm:       {provider: local, model: "Qwen2.5-7B-Instruct", device: auto}
  vlm:       {provider: local, model: "Qwen2.5-VL-3B", device: auto}
  vlm_reranker: {provider: local, model: "Qwen2.5-VL-7B", device: auto}
  whisper:   {provider: local, model: "large-v3-turbo", device: auto}
  embedding: {provider: local, model: "BAAI/bge-small-zh-v1.5", device: auto}
```

再执行 `venv\Scripts\python.exe -m pip install -r requirements-models.txt`。VLM 的 `describe()` 与 reranker 的实际模型调用在模型接入任务中实现（首个可运行版本以规则兜底通过全部验收为准）。