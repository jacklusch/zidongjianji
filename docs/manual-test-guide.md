# 手动测试文档（Manual Test Guide）

> 适用版本：AI 视频剪辑系统（模型下载 + 模型层重构后）。
> 环境：Windows，Python 3.11 venv，FFmpeg 位于 `bin\ffmpeg\bin\`，GPU 为 RTX 3060 12GB。

## 0. 前置准备

### 0.1 环境自检

```powershell
# 1) venv 存在且依赖完整
venv\Scripts\python.exe -c "import cv2, scenedetect, yaml, rank_bm25; print('基础依赖 OK')"

# 2) 可选模型依赖（已有模型时）
venv\Scripts\python.exe -c "import funasr, torchaudio; print('FunASR OK')"
venv\Scripts\python.exe -c "import huggingface_hub, modelscope; print('下载 SDK OK')"
venv\Scripts\python.exe -c "import openai; print('OpenAI SDK OK')"

# 3) FFmpeg
bin\ffmpeg\bin\ffmpeg.exe -version | Select-Object -First 1

# 4) config.yaml 存在（若不存在，从模板生成）
if (-not (Test-Path config.yaml)) { Copy-Item config.yaml.example config.yaml }
```

预期：无报错，FFmpeg 打印版本号。

### 0.2 准备测试素材

将测试视频放入 `materials\` 目录（可从 `测试素材\` 复制）：

```powershell
New-Item -ItemType Directory -Path materials -Force | Out-Null
Copy-Item "测试素材\*.mp4" materials\ -Force
Get-ChildItem materials\*.mp4 | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
```

> 素材文件名会参与 BM25 检索，建议使用语义化命名（如 `factory01.mp4`、`worker01.mp4`）。

---

## 1. 模型下载脚本测试

### 1.1 查看模型清单

```powershell
venv\Scripts\python.exe scripts\download_models.py --list
```

**预期**：打印 3 个模型（vlm / asr / embedding）的 HF 与 ModelScope 双源 ID。

### 1.2 错误解释器提示（健壮性）

```powershell
python scripts\download_models.py --source ms --model embedding
```

**预期**：报错并提示"请用项目虚拟环境运行本脚本：`...venv\Scripts\python.exe scripts\download_models.py ...`"，退出码 1（`No module named 'modelscope'` 这种误导性错误不应出现）。

### 1.3 从 HuggingFace 下载（单模型）

```powershell
venv\Scripts\python.exe scripts\download_models.py --source hf --model embedding --write-config
```

**预期**：
- 显示下载进度，结束后打印 `下载完成：1/1 成功`
- `[config] 已更新 config.yaml 的 model 路径`
- `models\embedding\` 下出现 config.json、model.safetensors 等文件

### 1.4 从 ModelScope（魔塔）下载

```powershell
venv\Scripts\python.exe scripts\download_models.py --source ms --model embedding --skip-install
```

**预期**：从 ModelScope 拉取成功（国内网络通常更稳）。`--skip-install` 跳过 pip 安装。

### 1.5 下载全部模型

```powershell
venv\Scripts\python.exe scripts\download_models.py --source ms --write-config
```

**预期**：依次下载 vlm / asr / embedding 三个模型，打印 `下载完成：3/3 成功`。

> 注意：vlm（约 1GB Q4_K_M + 424MB mmproj）、asr（约 890MB）耗时较长；失败会逐模型报错并提示切源，不中断其他模型。

### 1.6 校验下载产物

```powershell
Get-ChildItem models\vlm\*.gguf | Select-Object Name, @{n='GB';e={[math]::Round($_.Length/1GB,2)}}
Get-ChildItem models\asr\model.pt, models\embedding\model.safetensors -ErrorAction SilentlyContinue | Select-Object Name
```

**预期**：
- vlm：`Qwen3VL-2B-Instruct-Q4_K_M.gguf`（~1GB）+ `mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf`（~424MB）
- asr：`model.pt`
- embedding：`model.safetensors`

---

## 2. 配置与模型启用测试

### 2.1 查看当前配置

```powershell
Get-Content config.yaml
```

### 2.2 启用本地 embedding 与 asr（已 write-config 时已是 local）

```yaml
# config.yaml 确认：
models:
  embedding: {provider: local, model: "D:\...\models\embedding", device: auto}
  asr:       {provider: local, model: "D:\...\models\asr", device: auto}
```

### 2.3 实际加载 embedding

```powershell
venv\Scripts\python.exe -c "from app.models.embedding import Embedder; e=Embedder('local', r'D:\bak_f\001\zidongjianji\models\embedding', 'cpu'); v=e.embed(['工厂','视频']); print('embed OK, dim=', len(v[0]))"
```

**预期**：`embed OK, dim= 512`。

### 2.4 实际加载 asr（FunASR 转写）

```powershell
# 生成 2 秒测试音频并转写
venv\Scripts\python.exe -c "
from app.models.asr import ASR
from app.utils.process import run
run(['bin/ffmpeg/bin/ffmpeg.exe','-y','-f','lavfi','-i','sine=frequency=300:duration=2','-ar','16000','-ac','1',r'C:\Users\Administrator\AppData\Local\Temp\opencode\t.wav'])
a = ASR('local', r'D:\bak_f\001\zidongjianji\models\asr', 'cpu')
print('ASR segments:', len(a.transcribe(r'C:\Users\Administrator\AppData\Local\Temp\opencode\t.wav')))
"
```

**预期**：`ASR segments: 1`（首次加载模型需 20-60 秒；CPU 转写较慢属正常）。

### 2.5 启用 VLM（GGUF）

```yaml
# config.yaml 手动改（或 download_models.py --write-config 自动写）：
models:
  vlm: {provider: local, model: "D:\...\models\vlm", device: auto}
  vlm_reranker: {provider: local, model: "D:\...\models\vlm", device: auto}
```

验证加载：

```powershell
venv\Scripts\python.exe -c "from app.models.vlm import get_gguf_llm; llm, mm = get_gguf_llm(r'D:\bak_f\001\zidongjianji\models\vlm', 'auto'); print('VLM load OK, mmproj:', mm)"
```

**预期**：`VLM load OK, mmproj: <mmproj 路径>`（或 None）。

### 2.6 启用线上 LLM（OpenAI 兼容）

```yaml
# config.yaml 手动配置（api_key 也可只设环境变量 OPENAI_API_KEY 留空）：
models:
  llm: {provider: openai, model: "gpt-4o-mini", device: auto,
        base_url: "https://api.openai.com/v1", api_key: "sk-你的key"}
```

```powershell
# 用环境变量（推荐，避免 key 落盘）
$env:OPENAI_API_KEY = "sk-你的key"
venv\Scripts\python.exe -c "from app.models.llm import LLM; print(LLM('openai','gpt-4o-mini','cpu', 'https://api.openai.com/v1', '').generate('用一句话介绍视频剪辑'))"
```

**预期**：返回一句中文介绍；无 key 时抛 `RuntimeError: 未配置 api_key...`。

> 提示：国内用户可将 `base_url` 指向 DeepSeek/通义等 OpenAI 兼容端点（如 `https://api.deepseek.com/v1`），模型名对应改。

---

## 3. 核心流程测试（CLI 命令）

> 本节省略模型无关的规则兜底部分：即使所有模型为 none，以下命令也必须能跑通。

### 3.1 scan —— 扫描素材

```powershell
venv\Scripts\python.exe -m app.main scan materials
```

**预期**：列出每个文件的路径、时长、分辨率、编码、是否有音轨。

### 3.2 index —— 索引素材

```powershell
venv\Scripts\python.exe -m app.main index materials
```

**预期**：
- 输出 JSON 报告（`media`/`shots`/`visual`/`new`/`changed`/`skipped`）
- 生成 `data\footage\index.db`、`data\footage\thumbnails\*.jpg`、日志

### 3.3 index 幂等性

```powershell
venv\Scripts\python.exe -m app.main index materials
```

**预期**：第二次 `new=0`、`changed=0`、`skipped` 等于素材数（未变素材跳过）。

### 3.4 analyze —— 强制重分析

```powershell
venv\Scripts\python.exe -m app.main analyze materials
```

**预期**：`reanalyzed` 等于素材数（对已索引素材重跑视觉/语音分析）；结束后自动生成视觉校验报告 `data\footage\visual_review.md`。

### 3.5 export —— 导出视觉描述校验报告

```powershell
venv\Scripts\python.exe -m app.main export
```

**预期**：从索引库重新生成 `data\footage\visual_review.md`（Markdown 表格，每镜头一行：素材、时间码、时长、描述、对象、动作、环境、场景类型、机位、人数、质量、缩略图文件名），方便人类逐镜头核对画面描述是否准确。

### 3.6 describe —— 完整描述单个视频内容

```powershell
# 默认按镜头切分（无切点的长镜头按 5 秒窗口细分）
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4

# 自定义细分窗口（如 10 秒）
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4 --window 10
```

**预期**：直接分析该视频（无需先索引），生成 `data\descriptions\factory01.md`，包含三部分：
- **整体概述**：一句话总结视频内容
- **分镜头时间线**：每时间段的时间范围 + VLM 画面描述 + 对象/动作/环境（`--window` 控制长镜头/无切点视频的细分粒度，默认 5 秒）
- **内容汇总**：出现的对象/动作/环境去重列表、最大人数、镜头数、总时长

### 3.7 search —— 语义搜索

```powershell
venv\Scripts\python.exe -m app.main search 香肠
venv\Scripts\python.exe -m app.main search 工厂
```

**预期**：返回按相关度排序的候选镜头（shot_id、相似度、来源、时间码）。中文查询依赖素材文件名/描述词命中；若 corpus 词与查询无交集则结果为空属正常。

### 3.8 plan —— 生成剪辑计划

准备脚本文件（例如 `scripts\demo.md`）：

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

**预期**：生成 `data\projects\demo\script_plan.json`、`match_results.json`、`edit_plan.json`。`edit_plan.json` 的 timeline 项含 `script_id/source/in/out/duration/reason/confidence`；无匹配的片段进 `missing`。

### 3.9 render —— 渲染成片

```powershell
venv\Scripts\python.exe -m app.main render data\projects\demo\edit_plan.json
```

**预期**：生成 `data\projects\demo\preview.mp4` 与 `final.mp4`，大小 > 0。

### 3.10 build —— 一键全流程

```powershell
venv\Scripts\python.exe -m app.main build scripts\demo.md --project demo
```

**预期**：依次 index → plan → render，输出 `完成: preview=... final=...`，`final.mp4` 可播放。

> **重要（中文检索限制）**：BM25 检索不做中文分词，整句脚本（如"开头展示视频镜头"）会被当做一个 token，无法命中语料里的"视频镜头"；只有**与素材文件名/视觉描述完全一致的短词**能命中。因此：
> - 若脚本词无匹配，build 会打印 `无可用镜头...未渲染`（优雅跳过，非报错）——属预期行为
> - 要完整演示渲染，脚本需用语料中的词。例如素材为 `factory01.mp4`（视觉描述"视频镜头，画面亮度 X"）时，脚本写：
>   ```markdown
>   主题：镜头演示
>
>   视频镜头。
>
>   画面亮度。
>   ```
>   （两行分别命中 corpus 的 `视频镜头` 与 `画面亮度`，timeline 非空即可渲染）
> - 启用 embedding（provider=local）后仍以 BM25 检索为主，中文长句匹配受限，这是已知限制（后续可引入中文分词改善）

### 3.11 校验成片

```powershell
bin\ffmpeg\bin\ffprobe.exe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 data\projects\demo\final.mp4
```

**预期**：`duration > 0`，`codec_name=h264`，分辨率 `1920x1080`（默认配置）。

---

## 4. 模型驱动流程测试（启用模型后）

> 前提：执行 2.2-2.6 启用 embedding/asr/vlm/llm。

### 4.1 带 embedding 索引

```powershell
venv\Scripts\python.exe -m app.main index materials
```

**预期**：报告含 `embeddings` 相关写入；`data\footage\index.db` 的 embeddings 表有记录。验证：

```powershell
venv\Scripts\python.exe -c "from app.index.database import Database; from app.config.settings import load_settings; s=load_settings(); db=Database(s.footage_db); print('embedding rows:', len(db.get_all_embeddings())); db.close()"
```

### 4.2 带 asr 的转写（含时间戳）

```powershell
venv\Scripts\python.exe -m app.main analyze materials
```

**预期**：日志出现 ASR 转写；transcripts 表有逐字时间戳记录（如 `[0.39-0.65] hello`、`[0.65-0.81] 你`）。验证：

```powershell
venv\Scripts\python.exe -c "from app.index.database import Database; from app.config.settings import load_settings; db=Database(load_settings().footage_db); [print(r) for r in db.conn.execute('SELECT shot_id, round(start,2), round(end,2), text FROM transcripts LIMIT 5')]; db.close()"
```

> asr 模型用带 VAD/标点的 paraformer（`models/asr_vad`）才能输出逐字时间戳；纯 asr 模型无时间戳（start/end=0）。

### 4.3 带 vlm 的视觉分析

```powershell
venv\Scripts\python.exe -m app.main analyze materials
```

**预期**：visual 表 description 来自 VLM（provider=local 时）；模型不可用时自动降级为帧统计兜底（日志标注）。

### 4.4 带 llm 的脚本解析

```powershell
venv\Scripts\python.exe -m app.main plan scripts\demo.md --project demo2
```

**预期**：`script_plan.json` 的 segments 来自 LLM 结构化输出（而非规则句拆）。

---

## 5. 错误场景测试

| 场景 | 操作 | 预期 |
|---|---|---|
| 素材目录为空 | `index materials`（空目录） | 报告 `media=0`，不崩溃 |
| 不存在的素材 | `plan scripts\nonexist.md` | 报错：脚本不存在 |
| 缺 FFmpeg | 临时改名 `bin\ffmpeg` 后 `build` | 报错提示安装 FFmpeg |
| 损坏视频 | 复制 txt 改名 `.mp4` 放入 materials | probe/scenedetect 失败仅跳过该文件，其余继续 |
| api_key 缺失 | llm provider=openai 且无 key | `RuntimeError: 未配置 api_key` |
| VLM 模型文件缺失 | vlm provider=local 但 model 路径不存在 | `RuntimeError: 模型文件不存在: ...` |

---

## 6. 回归验收

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
```

**预期**：全部 PASS（当前基线 59 passed）。模型目录 `models\` 与 `config.yaml` 不入库（`git status` 不应显示它们）。

---

## 7. 常见问题排查

| 症状 | 原因 | 解决 |
|---|---|---|
| `No module named 'modelscope'` | 用了系统 python 而非 venv | 用 `venv\Scripts\python.exe` 运行 |
| 下载 404 | 源上 repo 不存在 | 换 `--source ms`/`--source hf`；核对 `download_models.py --list` 的 ID |
| `No module named 'torchaudio'` | 缺 FunASR 音频依赖 | `pip install -r requirements-models.txt` |
| FunASR 很慢 | CPU 推理 | 设 `asr.device: auto` 用 GPU |
| 搜索无结果 | BM25 需 token 精确命中 | 用与素材文件名/描述一致的短词（中文不分词）；见 3.10 说明 |
| build 渲染失败 | 单片段失败 | 查看日志，`edit_plan.json` 的 missing/warnings |
