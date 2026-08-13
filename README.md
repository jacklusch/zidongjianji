# 本地 AI 视频剪辑系统

根据分镜脚本自动完成素材检索、匹配与剪辑：索引素材库 → 脚本切段 → 逐段检索匹配镜头 → 生成时间线 → 渲染成片。全流程本地运行，无需云端。

## 环境要求

- Windows 10/11，Python 3.11
- FFmpeg（含 ffprobe）——可预装到 PATH，或由 `install.ps1` 自动下载到 `bin\ffmpeg`

## 安装

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

安装脚本会创建 `venv` 虚拟环境、安装 `requirements.txt` 依赖、检测/下载 FFmpeg、生成 `config.yaml`。

## 命令清单

```powershell
venv\Scripts\python.exe -m app.main scan <目录>            # 扫描素材基本信息
venv\Scripts\python.exe -m app.main index <目录>           # 索引：扫描+场景切分+视觉/语音分析
venv\Scripts\python.exe -m app.main analyze <目录>         # 强制重新执行视觉/语音分析
venv\Scripts\python.exe -m app.main search "<查询>"        # 语义搜索素材镜头
venv\Scripts\python.exe -m app.main plan scripts\demo.md --project demo
                                                          # 脚本→检索→匹配→生成 edit_plan
venv\Scripts\python.exe -m app.main render data\projects\demo\edit_plan.json
                                                          # 按 edit_plan 渲染成片
venv\Scripts\python.exe -m app.main build scripts\demo.md --project demo [--materials <目录>]
                                                          # 一键：index→plan→render
```

`build` 会把三个阶段串起来执行：索引素材（含分析）→ 脚本匹配生成 `edit_plan.json` → 渲染 `preview.mp4` 与 `final.mp4`，产物落在 `data/projects/<project>/`。

## 目录结构

```
app/              核心代码
  analyzer/       媒体探测、场景切分、帧/视觉/语音分析
  config/         配置加载（config.yaml → Settings）
  editors/        FFmpeg 渲染器
  index/          素材库索引、数据库、BM25/向量检索
  matching/       检索、重排、镜头匹配
  models/         LLM/VLM/Embedding/Whisper 模型封装
  pipeline/       index→plan→render 流水线编排
  script/         脚本解析与脚本计划
  timeline/       时间线构建与校验
  utils/          路径、日志、外部命令
scripts/          安装与示例脚本（install.ps1 / start.ps1 / demo.md）
materials/        素材目录（默认）
data/
  footage/        索引数据库与缩略图
  projects/<项目>/ script_plan.json / match_results.json / edit_plan.json / preview.mp4 / final.mp4
  logs/           运行日志
output/           render 中间产物
config.yaml       模型与参数配置
```

## 模型配置

`config.yaml` 的 `models` 段用 `provider` 三态控制各模型（llm/vlm/vlm_reranker/asr/embedding）的启用方式：

- `none`（默认）→ 规则兜底，不加载任何模型，完全离线运行（BM25 检索、规则脚本解析、亮度直方图视觉分析）。
- `local` → 本地模型。用 `scripts/download_models.py` 从 HuggingFace / ModelScope 下载后，以 `--write-config` 自动把本地路径写回 `config.yaml`：

  ```powershell
  venv\Scripts\python.exe scripts\download_models.py --list
  venv\Scripts\python.exe scripts\download_models.py --source ms --write-config   # 国内网络可用 --source ms
  ```

- `openai` → 线上 OpenAI 兼容接口（仅 llm/vlm），需填 `base_url` 与 `api_key`。示例：

  ```yaml
  models:
    llm: {provider: openai, model: "gpt-4o-mini", base_url: "https://api.openai.com/v1", api_key: ""}
  ```

  `api_key` 可直接写入 `config.yaml`，或留空走环境变量 `OPENAI_API_KEY`。

本地模型（provider: local）需在 `requirements-models.txt` 中安装对应依赖（torch/transformers/llama-cpp-python/funasr 等）。

注意：`config.yaml` 含个人配置（如 `api_key`），**不入库**（见 `.gitignore`）。参考模板见 `config.yaml.example`，安装脚本会基于模板生成 `config.yaml`。

## 测试

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
```
