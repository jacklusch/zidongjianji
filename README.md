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

默认 `config.yaml` 中所有模型 `provider: none`，即完全离线规则兜底（BM25 检索、规则脚本解析、亮度直方图视觉分析）。如需启用本地模型，把对应项的 `provider: none` 改为 `local` 并填写模型名：

```yaml
models:
  llm:       {provider: local, model: "Qwen/Qwen2.5-7B-Instruct", device: auto}   # 脚本解析
  embedding: {provider: local, model: "BAAI/bge-small-zh-v1.5", device: auto}     # 向量检索
  vlm:       {provider: local, model: "Qwen/Qwen2.5-VL-7B-Instruct", device: auto} # 视觉分析
  whisper:   {provider: local, model: "openai/whisper-small", device: auto}        # 语音转写
```

启用模型需自行额外安装 `transformers`、`torch` 等依赖，并确保模型可在本地加载。

## 测试

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
```
