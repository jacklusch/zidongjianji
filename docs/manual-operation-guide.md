# 手动操作文档（Manual Operation Guide）

> 版本：2026-08-13
> 环境：Windows 10/11 x64，Python 3.11 venv，FFmpeg，NVIDIA RTX 3060 12GB（可选 GPU）
> 项目：本地 AI 自动视频剪辑系统

---

## 目录

- [1. 环境准备](#1-环境准备)
- [2. 模型下载与配置](#2-模型下载与配置)
- [3. GPU 加速](#3-gpu-加速)
- [4. 素材准备](#4-素材准备)
- [5. CLI 命令操作](#5-cli-命令操作)
  - [5.1 scan 扫描素材](#51-scan-扫描素材)
  - [5.2 index 索引素材](#52-index-索引素材)
  - [5.3 analyze 强制重分析](#53-analyze-强制重分析)
  - [5.4 search 语义搜索](#54-search-语义搜索)
  - [5.5 export 导出视觉校验报告](#55-export-导出视觉校验报告)
  - [5.6 describe 完整描述单个视频](#56-describe-完整描述单个视频)
  - [5.7 compare 对比本地/线上 VLM](#57-compare-对比本地线上-vlm)
  - [5.8 plan 生成剪辑计划](#58-plan-生成剪辑计划)
  - [5.9 render 渲染成片](#59-render-渲染成片)
  - [5.10 build 一键全流程](#510-build-一键全流程)
- [6. 完整工作流演示](#6-完整工作流演示)
- [7. 产物目录结构](#7-产物目录结构)
- [8. 常见问题排查](#8-常见问题排查)

---

## 1. 环境准备

### 1.1 一键安装

```powershell
# 在项目根目录执行（创建 venv、装依赖、下载 FFmpeg）
.\scripts\install.ps1
```

### 1.2 手动验证环境

```powershell
# 基础依赖
venv\Scripts\python.exe -c "import cv2, scenedetect, yaml, rank_bm25, jieba; print('基础依赖 OK')"

# 模型依赖（已有模型时）
venv\Scripts\python.exe -c "import funasr, torchaudio; print('FunASR OK')"
venv\Scripts\python.exe -c "import huggingface_hub, modelscope; print('下载 SDK OK')"
venv\Scripts\python.exe -c "import openai; print('OpenAI SDK OK')"

# FFmpeg
bin\ffmpeg\bin\ffmpeg.exe -version | Select-Object -First 1

# config.yaml（不存在则从模板生成）
if (-not (Test-Path config.yaml)) { Copy-Item config.yaml.example config.yaml }
```

### 1.3 统一命令前缀说明

> 本文所有 `venv\Scripts\python.exe` 均可用 `python` 替代，**但必须确保用的是 venv 内的 Python**。
> 误用系统 Python 会报 `No module named 'modelscope'` 等缺失依赖错误。可用 `python -c "import sys; print(sys.executable)"` 核对路径应含 `venv`。

---

## 2. 模型下载与配置

### 2.1 查看可下载模型清单

```powershell
venv\Scripts\python.exe scripts\download_models.py --list
```

输出 4 个模型的双源（HuggingFace / 魔塔 ModelScope）ID：

| 角色 | 模型 | 用途 |
|---|---|---|
| vlm | Qwen3-VL-4B-Instruct-Q4_K_M (GGUF) | 本地画面描述 + reranker |
| vlm2b | Qwen3-VL-2B-Instruct (备用) | 轻量回退 |
| asr | paraformer-large-vad-punc | FunASR 中文转写（含时间戳） |
| embedding | bge-small-zh-v1.5 | 语义向量 |

### 2.2 下载模型

```powershell
# 下载全部（国内网络用 ms，海外用 hf）
venv\Scripts\python.exe scripts\download_models.py --source ms --write-config

# 只下载单个
venv\Scripts\python.exe scripts\download_models.py --source ms --model embedding --write-config

# 不写回 config（只下载）
venv\Scripts\python.exe scripts\download_models.py --source hf --model vlm --skip-install
```

参数说明：
- `--source hf|ms`：下载源（hf=HuggingFace，ms=魔塔，国内推荐 ms）
- `--model <名>`：只下载指定模型，可重复
- `--write-config`：下载后把本地路径写回 `config.yaml`
- `--skip-install`：跳过 pip 依赖安装
- `--list`：打印清单

### 2.3 验证模型已下载

```powershell
Get-ChildItem models\vlm\*.gguf | Select-Object Name, @{n='GB';e={[math]::Round($_.Length/1GB,2)}}
Get-ChildItem models\asr_vad\model.pt, models\embedding\model.safetensors -ErrorAction SilentlyContinue | Select-Object Name
```

预期：
- `models\vlm\Qwen3VL-4B-Instruct-Q4_K_M.gguf`（~2.3GB）+ `mmproj-Qwen3VL-4B-Instruct-F16.gguf`（~0.8GB）
- `models\asr_vad\model.pt`
- `models\embedding\model.safetensors`

### 2.4 配置 `config.yaml`

`config.yaml` 不在 git 仓库中（避免 api_key 泄露），首次运行由 `install.ps1` 从模板生成。手动编辑时参考：

```yaml
models:
  llm:          # 线上大语言模型（OpenAI 兼容）
    provider: openai
    model: glm-4.7-flash
    base_url: https://open.bigmodel.cn/api/paas/v4   # 智谱；也可换 DeepSeek/OpenAI
    api_key: <你的key>                                # 或留空走环境变量 OPENAI_API_KEY
  vlm:          # 本地视觉模型（GGUF）
    provider: local
    model: D:\path\to\models\vlm
  vlm_reranker: # VLM 重排（当前未启用）
    provider: none
  vlm_compare:  # 线上对比用视觉模型
    provider: openai
    model: glm-4v-flash
    base_url: https://open.bigmodel.cn/api/paas/v4
    api_key: <你的key>
  asr:          # 本地语音转写（FunASR）
    provider: local
    model: D:\path\to\models\asr_vad
  embedding:    # 本地向量模型
    provider: local
    model: D:\path\to\models\embedding
gpu:
  enabled: auto        # auto|on|off
  memory_fraction: 0.7 # 可用显存利用比例
```

**provider 取值**：
- `none`：规则兜底（无模型，最省资源，功能降级）
- `local`：本地模型（VLM/ASR/Embedding）
- `openai`：线上 OpenAI 兼容接口（LLM/VLM，需 base_url + api_key）

### 2.5 实际加载验证各模型

```powershell
# Embedding（输出 512 维向量）
venv\Scripts\python.exe -c "from app.models.embedding import Embedder; e=Embedder('local', r'D:\bak_f\001\zidongjianji\models\embedding', 'auto'); v=e.embed(['工厂','视频']); print('embed OK, dim=', len(v[0]))"

# VLM（GGUF 描述画面）
venv\Scripts\python.exe -c "from app.models.vlm import VLM; from app.analyzer.visual import _VLM_PROMPT; import cv2; f=cv2.imread('data/footage/thumbnails/factory01_001_00.jpg'); v=VLM('local', r'D:\bak_f\001\zidongjianji\models\vlm', 'auto'); print(v.describe([f], _VLM_PROMPT).get('description'))"

# ASR（FunASR 转写）
venv\Scripts\python.exe -c "from app.models.asr import ASR; a=ASR('local', r'D:\bak_f\001\zidongjianji\models\asr_vad', 'auto'); import subprocess,tempfile; w=tempfile.mktemp(suffix='.wav'); subprocess.run(['bin/ffmpeg/bin/ffmpeg.exe','-y','-f','lavfi','-i','sine=frequency=300:duration=2','-ar','16000','-ac','1',w],capture_output=True); print('ASR segs:', len(a.transcribe(w)))"

# LLM（线上）
$env:OPENAI_API_KEY = "<你的key>"  # 若 config 未填 api_key
venv\Scripts\python.exe -c "from app.models.llm import LLM; from app.config.settings import load_settings; s=load_settings(); print(LLM(s.llm.provider,s.llm.model,s.llm.device,s.llm.base_url,s.llm.api_key).generate('用一句话介绍视频剪辑'))"
```

---

## 3. GPU 加速

### 3.1 检测 GPU 与当前模式

```powershell
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
venv\Scripts\python.exe -c "from app.models.device import DeviceManager; d=DeviceManager('auto'); print('当前设备:', d.resolve()); print('CUDA 支持:', d.resolve_cuda_support())"
```

- `resolve()` 返回 `cuda` = 模型走 GPU
- `resolve()` 返回 `cpu` = 模型走 CPU（可能是依赖为 CPU 版）

**判断依据**（三者缺一不可才用 GPU）：
1. torch 支持 CUDA（`torch.cuda.is_available()`）
2. llama-cpp-python 带 CUDA 编译（`llama_supports_gpu_offload`）
3. 存在 `nvidia-smi`

### 3.2 启用 GPU（需重装依赖）

当前环境若 `resolve()` 为 `cpu` 但 `nvidia-smi` 有 GPU，说明装的是 CPU 版依赖。运行安装脚本会自动检测：

```powershell
.\scripts\install.ps1   # 检测到 GPU 自动装 CUDA 版 torch/torchaudio/llama-cpp
```

或手动：

```powershell
venv\Scripts\python.exe -m pip install "torch==2.5.1+cu121" "torchaudio==2.5.1+cu121" --index-url https://download.pytorch.org/whl/cu121
venv\Scripts\python.exe -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

### 3.3 GPU 配置

```yaml
gpu:
  enabled: auto        # auto=自动检测, on=强制尝试(异常回退CPU), off=强制CPU
  memory_fraction: 0.7 # 可用显存的利用比例，不足自动回退CPU
```

### 3.4 确认 GPU 生效

运行任一命令后看日志中的设备决策行（如 `GPU 加载 ... device=cuda, n_gpu_layers=N`）：

```powershell
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4 --window 10
```

### 3.5 FFmpeg 硬件编码（NVENC）

渲染会自动探测 `h264_nvenc`，可用时用 GPU 编码，不可用回退 `libx264`：

```powershell
bin\ffmpeg\bin\ffmpeg.exe -hide_banner -encoders | Select-String "h264_nvenc"  # 有输出=支持
```

---

## 4. 素材准备

将待剪辑视频放入 `materials\` 目录：

```powershell
New-Item -ItemType Directory -Path materials -Force | Out-Null
Copy-Item "测试素材\*.mp4" materials\ -Force
Get-ChildItem materials\*.mp4 | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
```

> **素材命名建议**：文件名会参与 BM25 语义检索，建议语义化命名（如 `factory01.mp4`、`worker01.mp4`）。中文文件名也可，但检索需分词命中。

---

## 5. CLI 命令操作

### 5.1 scan 扫描素材

```powershell
venv\Scripts\python.exe -m app.main scan materials
```

**输出**：每个文件一行，含路径、时长、分辨率、编码、是否有音轨。

**预期**：
```
materials\001.mp4 | 22.78s | 1080x1920 | h264 | audio=yes
```

---

### 5.2 index 索引素材

```powershell
venv\Scripts\python.exe -m app.main index materials
```

**功能**：扫描 → FFprobe 入库 → 场景切分 → 抽帧缩略图 → VLM 画面描述 → ASR 语音转写 → embedding 向量（检索时写入）。

**输出**：JSON 报告，字段含义：
| 字段 | 含义 |
|---|---|
| media | 新增素材数 |
| shots | 新增镜头数 |
| new / changed / skipped | 新 / 变更 / 未变素材数 |
| visual | 完成视觉分析的镜头数 |

**幂等性**：重复执行 `index`，未变素材 `skipped`（不重复处理）。再次执行应看到 `skipped` 等于素材数。

---

### 5.3 analyze 强制重分析

```powershell
venv\Scripts\python.exe -m app.main analyze materials
```

**功能**：对已索引素材强制重跑视觉 + 语音分析（模型升级或换模型后使用）。结束后自动生成视觉校验报告。

**输出**：`reanalyzed` 等于素材数。

---

### 5.4 search 语义搜索

```powershell
venv\Scripts\python.exe -m app.main search 疏通剂
venv\Scripts\python.exe -m app.main search 洋葱
venv\Scripts\python.exe -m app.main search factory
```

**功能**：BM25 + jieba 中文分词检索素材镜头（语料 = 文件名 + VLM 描述 + ASR 转写文本）。

**输出**：每行 `相似度 shot_id 来源文件 [起-止时间]`，末尾显示结果数。

**注意**：中文查询需语料中存在对应词。若素材 ASR 转写包含"疏通剂"，`search 疏通剂` 应命中对应素材。

---

### 5.5 export 导出视觉校验报告

```powershell
venv\Scripts\python.exe -m app.main export
```

**功能**：从索引库生成 `data\footage\visual_review.md`，逐镜头列出：素材、时间码、时长、VLM 描述、对象、动作、环境、场景类型、机位、人数、质量、缩略图。用于人工校验画面描述准确性。

---

### 5.6 describe 完整描述单个视频

```powershell
# 默认按镜头切分，长镜头按 5 秒窗口细分
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4

# 自定义细分窗口（如 10 秒）
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4 --window 10
```

**功能**：直接分析单个视频（无需先索引），生成 `data\descriptions\<文件名>.md`，含：
- **整体概述**：一句话总结
- **分镜头时间线**：每段的时间范围 + VLM 描述 + 对象/动作/环境
- **内容汇总**：对象/动作/环境去重、最大人数、镜头数、总时长

> VLM 已启用确定性推理（零温度）+ 多帧聚合：同一视频两次运行描述一致；每段描述覆盖整段时间（多帧拼接）。

---

### 5.7 compare 对比本地/线上 VLM

```powershell
venv\Scripts\python.exe -m app.main compare materials\factory01.mp4
```

**功能**：对同一画面，本地 VLM（Qwen3-VL-4B）与线上 GLM-4V-Flash 分别描述，线上模型做一致性裁判，生成 `data\descriptions\<文件名>_compare.md`：

| 时间码 | 本地描述 | 线上描述 | 一致性 | 差异 |

用于人工校验本地 VLM 描述是否准确（一致性：✅ 一致 / ❌ 不一致 / ❔ 未知）。

**前置**：`config.yaml` 的 `vlm_compare` 段需配置线上 GLM-4V（model 用 `glm-4v-flash`，base_url 与 llm 相同）。

---

### 5.8 plan 生成剪辑计划

准备脚本文件（如 `scripts\demo.md`）：

```markdown
主题：现代化香肠生产工艺

开头展示现代化工厂。
然后展示工人在生产线上操作机器。
接着展示产品特写。
最后展示包装完成后的产品。
```

```powershell
venv\Scripts\python.exe -m app.main plan scripts\demo.md --project demo
```

**功能**：脚本 → 检索候选镜头 → 匹配 → 生成 `data\projects\demo\` 下的：
- `script_plan.json`：脚本解析结果（LLM 或规则）
- `match_results.json`：检索匹配记录
- `edit_plan.json`：最终剪辑计划（timeline + missing + warnings）

**edit_plan.json** 的 timeline 每项含：`script_id / source / in / out / duration / reason / confidence / reused`。无匹配的片段进 `missing`。

> **中文检索限制**：BM25 需 token 精确命中。脚本长句（如"开头展示现代化工厂"）会被当整串 token，可能匹配不到语料中的短词。若 timeline 为空，用与素材描述一致的短词脚本重试（见 6.2 演示）。

---

### 5.9 render 渲染成片

```powershell
venv\Scripts\python.exe -m app.main render data\projects\demo\edit_plan.json
```

**功能**：按 edit_plan 渲染。每片段裁剪 → 统一分辨率/帧率（1920x1080@30）→ concat 拼接。生成 `preview.mp4` 与 `final.mp4`。

- 视频编码：自动探测 `h264_nvenc`（GPU）→ 否则 `libx264`（CPU）
- 单片段失败自动跳过（不中断整体），空时间线报错

**校验产物**：

```powershell
bin\ffmpeg\bin\ffprobe.exe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 data\projects\demo\final.mp4
```

---

### 5.10 build 一键全流程

```powershell
venv\Scripts\python.exe -m app.main build scripts\demo.md --project demo

# 指定素材目录
venv\Scripts\python.exe -m app.main build scripts\demo.md --project demo --materials D:\素材
```

**功能**：index → plan → render 一键串行，输出 `完成: preview=... final=...`。

若 timeline 为空（无匹配镜头），优雅跳过渲染并提示"无可用镜头（缺失 N 段），未渲染"——属预期行为，非报错。

---

## 6. 完整工作流演示

### 6.1 素材 → 索引 → 检索

```powershell
# 1) 准备素材（语义化命名）
Copy-Item "测试素材\001.mp4" materials\factory01.mp4
Copy-Item "测试素材\002.mp4" materials\worker01.mp4
Copy-Item "测试素材\003.mp4" materials\machine01.mp4
Copy-Item "测试素材\004.mp4" materials\product01.mp4

# 2) 索引
venv\Scripts\python.exe -m app.main index materials

# 3) 检索（中文命中 ASR 转写）
venv\Scripts\python.exe -m app.main search 疏通剂
venv\Scripts\python.exe -m app.main search 洋葱

# 4) 导出视觉校验报告
venv\Scripts\python.exe -m app.main export
```

### 6.2 完整剪辑流程（脚本词与语料匹配）

若素材视觉描述含"视频镜头/画面亮度"（兜底），用匹配词脚本走通渲染：

```powershell
# scripts\demo2.md 内容：
# 主题：镜头演示
# 视频镜头。
# 画面亮度。

venv\Scripts\python.exe -m app.main build scripts\demo2.md --project demo2

# 产物
Get-ChildItem data\projects\demo2 | Select-Object Name
# final.mp4 可播放
bin\ffmpeg\bin\ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1 data\projects\demo2\final.mp4
```

### 6.3 模型效果校验

```powershell
# 完整描述单个视频（时间线 + 概述 + 汇总）
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4 --window 10

# 本地 vs 线上描述对比（人工核对准确率）
venv\Scripts\python.exe -m app.main compare materials\factory01.mp4
```

---

## 7. 产物目录结构

```
data/
├── footage/
│   ├── index.db              # SQLite 主库（media/shots/visual/transcripts/embeddings）
│   ├── thumbnails/           # 镜头缩略图（*.jpg）
│   └── visual_review.md      # 视觉校验报告（export 生成）
├── descriptions/
│   ├── <视频名>.md           # describe 完整描述
│   └── <视频名>_compare.md   # compare 对比报告
├── projects/
│   └── <项目名>/
│       ├── script_plan.json  # 脚本解析
│       ├── match_results.json# 检索匹配
│       ├── edit_plan.json    # 剪辑计划
│       ├── preview.mp4       # 预览
│       └── final.mp4         # 成片
└── logs/
    └── YYYY-MM-DD_HHMMSS_<cmd>.log   # 各命令日志

models/               # 本地模型（gitignored）
├── vlm/              # Qwen3-VL-4B GGUF + mmproj
├── asr_vad/          # FunASR paraformer（VAD+punc，含时间戳）
├── asr/              # （旧）纯 asr 模型，可删
└── embedding/        # bge-small-zh-v1.5

config.yaml           # 运行时配置（gitignored，含 api_key）
config.yaml.example   # 配置模板（入库）
```

---

## 8. 常见问题排查

| 症状 | 原因 | 解决 |
|---|---|---|
| `No module named 'modelscope'` / `'funasr'` 等 | 用了系统 Python 而非 venv | 用 `venv\Scripts\python.exe`，核对 `python -c "import sys; print(sys.executable)"` |
| 下载模型 404 | 源上 repo 不存在 | 换 `--source ms`/`--source hf`；`download_models.py --list` 核对 ID |
| `No module named 'torchaudio'` | 缺 FunASR 音频依赖 | `pip install -r requirements-models.txt` |
| FunASR 转写慢 | CPU 推理 | 启用 GPU（见 §3.2）或换 `asr.device` 配置 |
| VLM 描述不准确 | 小模型/测试图案 | 用 `compare` 命令对比线上模型人工核对；或换 8B 模型 |
| 搜索无结果 | BM25 需 token 精确命中 | 用与文件名/描述一致的短词；中文长句不分词是已知限制 |
| `resolve()=cpu` 但有 GPU | 依赖是 CPU 版 | 运行 `install.ps1` 重装 CUDA 版（§3.2） |
| build 提示"无可用镜头" | 脚本词无匹配 | 属预期；换匹配语料的脚本词（§6.2） |
| 渲染失败单片段跳过 | 某片段 ffmpeg 失败 | 查看日志；edit_plan 的 missing/warnings |
| GPU 加载报错 | 显存不足/驱动问题 | 自动回退 CPU（已内置）；可调低 `memory_fraction` |
| `config.yaml` 改了不生效 | 未保存/语法错误 | 用 `python -c "import yaml; yaml.safe_load(open('config.yaml',encoding='utf-8'))"` 校验 YAML |
