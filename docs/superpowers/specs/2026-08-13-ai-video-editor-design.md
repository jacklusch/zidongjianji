# AI 自动视频剪辑系统 — 设计规格

- 日期：2026-08-13
- 状态：已确认（用户批准）

## 1. 目标与范围

在 **Windows 10/11 x64** 上运行的本地 AI 自动视频剪辑系统。

用户只提供：

- `materials/` 素材目录（视频 / 图片）
- `scripts/script.md` 剪辑脚本文案

系统自动完成：理解脚本 → 分析素材 → 建立语义索引 → 拆分为镜头需求 → 检索候选镜头 → VLM 二次判断 → 生成 `edit_plan.json` → FFmpeg 渲染 → `preview.mp4` → 检查 → `final.mp4`。

**第一版明确不做 GUI**（第二阶段再做），只做 CLI 完整链路。

### 非目标

- 不实现视频编解码、Whisper、VLM、向量数据库算法、视频裁切核心（全部复用成熟工具）
- 不接入在线 AI API（完全本地）
- 不依赖 WSL / Docker / Linux / Cygwin

## 2. 环境约束（已实测确认）

| 项目 | 值 |
|---|---|
| 系统 | Windows 10/11 x64（本机已确认） |
| GPU | RTX 3060 12GB（CUDA 可用） |
| Python | 3.11.9（venv 基准版本；本机 `python` 即 3.11.9） |
| FFmpeg | 本机未安装，`install.ps1` 须自动获取 |
| git | 已安装（2.53），仓库 `git@github.com:jacklusch/zidongjianji.git` |
| 模型 | 本机当前无任何模型，必须可无模型运行 |

## 3. 关键技术决策（用户已确认）

### D1. 渲染引擎：FFmpeg 核心，AutoCut 可选插件

- **FFmpeg** 是唯一渲染核心。`renderer.py` 统一走"裁剪+归一化+拼接"：先将每个片段渲染为规范化临时片段（`scale=1920x1080`、`fps=30`、`x264`/`libx264`），再用 concat demuxer 拼接输出 `final.mp4`（单片段则跳过拼接直接输出）。策略固定、可复现、不依赖源码格式一致性。
- **AutoCut**（bilibili/autocut）不作为主路径：其定位是字幕/静音切点裁剪，不适配"按 edit_plan 多片段拼接"。仅通过 `editors/autocut.py` 适配层保留接口，可选用于后续静音/停顿优化，**缺失/失败不影响主流程**。
- 原因：AutoCut 基本不维护、对新 Python 兼容差；FFmpeg 拼多片段是成熟且可控的路径。

### D2. 无模型环境可运行（规则兜底）

模型适配器全部走统一抽象，**可用则用、缺失则降级**，保证：

- 无 LLM → 规则解析器拆分脚本（按"开头/然后/接下来/接着/最后"等连接词与段落分镜，补充默认时长）
- 无 VLM → shot 语义描述用「帧采样 + 确定性启发式」（亮度/色彩统计、默认 shot_type=medium）兜底并标记 `analysis_method: "fallback"`；检索完全不依赖 VLM 也可完成
- 无 Whisper → 跳过转写，transcript 为空，检索时只用视觉文本
- 无 Embedding → 用 TF-IDF / BM25（`rank_bm25`）做确定性检索
- 模型放入 `config.yaml` 并实际可用时自动启用真实适配器

任何降级都在日志与 `edit_plan.json` 显式记录，保证可追溯。

### D3. 场景切分用 PySceneDetect

- 用 `scenedetect`（`AdaptiveDetector`/`ContentDetector`）切分 shot，不手写直方图算法。
- 最小 shot 时长、阈值从 `config.yaml` 读取（`scene_threshold`、`min_shot_duration`）。

### D4. 底层数据库第一批用 SQLite

- Python 内置 `sqlite3`，不引入 ORM。路径、元数据、嵌入向量（JSON blob，+`embedding` 前 N 维到列以支持简单相似度）全部持久化。
- 增量分析：以 `(hash, size, mtime, 分析版本, 模型版本)` 判定缓存有效性。

## 4. 架构

分层管线，模块职责单一、接口清晰：

```
scripts/script.md ─┐
materials/ ────────┤
                   ▼
        ┌─────────────────────── pipeline
        │ ① index  扫描+FFprobe+场景切分+抽帧+thumbnails
        │ ② analyze 可选：VLM 语义 / Whisper 转写
        │ ③ embed   文本组合→向量（或 TF-IDF/BM25）
        │ ④ plan    脚本→分镜需求→检索→重排→edit_plan.json
        │ ⑤ validate 时间码/引用/重复校验
        │ ⑥ render  FFmpeg 裁剪拼接→preview.mp4→final.mp4
        └───────────────────────
                   ▼
  data/projects/<project>/  +  output/
```

命令入口：`python -m app.main <command>`。分命令（index/analyze/search/plan/render）+ 一键 `build`。

### 模块清单（按规格目录）

- `app/config/settings.py` — 读 `config.yaml`，路径一律 `pathlib.Path` 推导
- `app/models/` — `vlm.py` / `llm.py` / `embedding.py` / `whisper.py`，适配器接口 + 规则兜底实现
- `app/analyzer/` — `media.py`（FFprobe 媒体信息）、`scene.py`（PySceneDetect 切分）、`frames.py`（抽帧+缩略图）、`visual.py`（帧统计/启发式语义）、`audio.py`（Whisper 转写）
- `app/index/` — `database.py`（SQLite 建表/迁移）、`footage_index.py`（增量扫描/入库）、`embeddings.py`、`search.py`（向量/TF-IDF 查询）
- `app/script/` — `parser.py`（LLM 或规则解析成 segments）、`planner.py`、`schema.py`
- `app/matching/` — `retriever.py`（Top-K）、`reranker.py`（VLM 二次判断，无则跳过）、`matcher.py`（打分融合）
- `app/timeline/` — `schema.py`、`planner.py`、`validator.py`
- `app/editors/` — `ffmpeg.py`（命令构造，shell=False）、`autocut.py`（预留）、`renderer.py`（策略选择与执行）
- `app/pipeline/` — `index_pipeline.py` / `analysis_pipeline.py` / `matching_pipeline.py` / `render_pipeline.py`，`build` 在此编排
- `app/utils/` — `process.py`（subprocess 封装）、`paths.py`、`logging.py`、`hashing.py`
- `app/models/device.py` — DeviceManager（auto/cpu/cuda/rocm，GPU 不可用自动 fallback CPU 并记日志）

### 设备抽象（替代直接写 `.cuda()`）

`DeviceManager.resolve(name)` 返回 `torch.device`；业务代码一律不直接触碰设备字符串。

## 5. 数据模型

### SQLite 表（`data/footage/index.db`）

- `media(id, path, rel_path, filename, duration, width, height, fps, codec, has_audio, size, hash, mtime, indexed_at)`
- `shots(id, shot_id, media_id, start, end, duration, frame_count, analysis_version, analysis_method)`
- `visual_analysis(shot_id, description, objects, actions, environment, shot_type, camera_motion, people_count, visual_quality, raw_json)`
- `transcripts(shot_id, segment_index, start, end, text, speaker)`
- `embeddings(shot_id, model, dim, vector_json, text)`

索引键：`(hash, size, mtime)` + `analysis_version` 决定是否重分析。

### `edit_plan.json`（核心中间产物，`data/projects/<project>/edit_plan.json`）

按规格第十六节结构，含 `version/project/source_script/timeline[]/missing[]/warnings[]`：
每个 timeline 项含 `script_id/source/in/out/duration/reason/confidence`，以及 `reused: true`（当同一 shot 因素材不足被允许复用）、`analysis_method`（溯源：模型或 fallback）。

## 6. CLI

| 命令 | 行为 |
|---|---|
| `python -m app.main index materials` | 扫描、FFprobe、场景切分、入库、增量更新 |
| `python -m app.main analyze materials` | VLM/Whisper 分析（有模型则跑） |
| `python -m app.main search "工人在生产线上操作机器"` | 检索 Top-K 并打印 |
| `python -m app.main plan scripts/script.md` | 脚本解析→检索→重排→`script_plan.json`+`match_results.json`+`edit_plan.json` |
| `python -m app.main render data/projects/demo/edit_plan.json` | 渲染 `preview.mp4` |
| `python -m app.main build scripts/script.md` | 完整流水线一键 |

子命令 `build` 流程：*check index → update index → parse script → retrieve → rerank → edit_plan → validate → render preview → 检查 → render final*。

## 7. 配置（`config.yaml`）

- `models.{vlm, vlm_reranker, embedding, whisper, llm}.{provider,model,device}` — provider 支持 `local`；`provider: none` 表示禁用该模型并启用 fallback
- `video.scene_threshold / min_shot_duration`
- `matching.top_k / rerank_k`
- `render.resolution / fps / format`
- `index.{frames_per_shot_min, frames_per_shot_max}`
- 所有模型名不硬编码进业务逻辑，一律从配置读取。

## 8. 错误处理与恢复

逐类处理（规格第二十二节）：模型缺失、FFmpeg/AutoCut 缺失、视频损坏、VLM 非法 JSON、Whisper/Embedding 失败、磁盘不足、素材不存在、时间码越界。

- VLM 非法 JSON：第一次自动修复（格式化/截断修括号）→ 第二次重试 → 第三次标记该 shot failed，**不崩溃整体**。
- 单个素材失败只影响该素材，记入 warnings，流程继续。

## 9. 日志

全部写入 `data/logs/YYYY-MM-DD_HHMMSS_<cmd>.log`，记录：扫描→VLM→Whisper→Embedding→检索→候选→最终→FFmpeg/AutoCut 命令→错误。绝不记录密钥。

## 10. 测试

`tests/` 至少含：`test_paths.py`（Windows 路径/中文文件名）、`test_media.py`、`test_script_parser.py`（LLM 与规则两模式）、`test_edit_plan.py`、`test_matcher.py`、`test_validator.py`、`test_scene.py`。覆盖：中文文件名、空目录、不存在文件、非法时间码、重复素材、VLM 非法 JSON、无模型 fallback。

用 `venv\Scripts\python.exe -m pytest` 运行。

## 11. 安装与启动

- `scripts/install.ps1`：创建 3.11 venv → `pip install -r requirements.txt` → 检测/下载 FFmpeg 到 `bin/ffmpeg/` → 写 `config.yaml`，输出"安装完成"
- `scripts/start.ps1`：激活 venv 并展示可用命令
- `requirements.txt` 作为重建环境依据；`bin/` 内的 ffmpeg 不提交，由 install 获取

## 12. 开发阶段（Phase 1–9，照规格第二十八节）

每阶段结束：运行 → 测试 → 修复 → 更新 README → 再前进。

## 13. 验收标准

`materials/{factory01,worker01,machine01,product01}.mp4` + `scripts/demo.md`，执行 `python -m app.main build scripts/demo.md` 后产出：

```
data/projects/demo/script_plan.json
data/projects/demo/match_results.json
data/projects/demo/edit_plan.json
data/projects/demo/preview.mp4
data/projects/demo/final.mp4
```

`edit_plan.json` 可完整追溯：脚本文案→匹配素材→源文件→原始时间码→选择原因→置信度→最终时间线。

## 14. 项目仓库

git 仓库远程 `git@github.com:jacklusch/zidongjianji.git`。黑名单（`.gitignore`）：`venv/`、`bin/`、`materials/`、`data/`、`output/`、`models/`、`__pycache__/`。