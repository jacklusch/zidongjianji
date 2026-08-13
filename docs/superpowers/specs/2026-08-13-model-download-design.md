# 规格：模型下载脚本与模型层重构

日期：2026-08-13
状态：已批准

## 背景

首版系统在无模型环境下以规则兜底跑通全流程（`provider: none`）。为启用真实本地模型与线上 LLM，需：

1. 新增自动下载脚本，可从 **HuggingFace** 与 **魔塔社区（ModelScope）** 双源拉取本地模型。
2. 调整模型选型：LLM 走线上 OpenAI 兼容 API；VLM/reranker 复用 `Qwen3-VL-2B-Instruct-GGUF`（GGUF 量化，llama.cpp 推理）；语音转写改用 **FunASR**（`paraformer-zh`，中文更优更省空间，替代 faster-whisper）；Embedding 用 `bge-small-zh-v1.5`。

## 模型清单

| 角色 | 模型 | HF ID | ModelScope ID | 备注 |
|---|---|---|---|---|
| VLM + reranker | Qwen3-VL-2B-Instruct-GGUF | `Qwen/Qwen3-VL-2B-Instruct-GGUF` | `Qwen/Qwen3-VL-2B-Instruct-GGUF` | GGUF 量化 |
| ASR | paraformer-zh | `funasr/paraformer-zh` | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | 中文优先 |
| Embedding | bge-small-zh-v1.5 | `BAAI/bge-small-zh-v1.5` | `AI-ModelScope/bge-small-zh-v1.5` | 中文优化 |

下载到 `models/<role>/`（仓库根 `models/`，已被 `.gitignore` 排除）。

## 组件设计

### 1. `scripts/download_models.py`（新增）

- 参数：
  - `--source hf|ms`（默认 `hf`）：选择 HuggingFace 或 ModelScope
  - `--model <name>`：只下载指定模型（`vlm`/`asr`/`embedding`，默认全部）
  - `--list`：打印模型清单后退出
  - `--write-config`：下载完成后把本地路径写回 `config.yaml` 对应 `model` 字段
  - `--skip-install`：不自动 pip 安装依赖
- 用 `huggingface_hub.snapshot_download` 与 `modelscope.snapshot_download`，SDK 自带断点续传与文件校验。
- 依赖安装：首次运行检测 `venv` 中是否缺所需库，缺则 `pip install -r requirements-models.txt`（可用 `--skip-install` 跳过）。

### 2. 模型适配器重构（`app/models/`）

#### `base.py`
- `ModelProvider.available()` 从 `provider == "local"` 扩展为 `provider in ("local", "openai")` 均视为可用。
- 新增 `ModelConfig` 字段：`base_url: str = ""`、`api_key: str = ""`（见第 4 节配置）。

#### `llm.py`（线上 OpenAI 兼容）
- `generate(prompt)`：
  - `provider == "none"`：返回现有规则兜底文案（不变）。
  - `provider == "openai"`：用 `openai` SDK（`base_url` + `api_key`），`model` 为配置的模型名，返回文本。失败抛 `RuntimeError`（含错误信息）。
  - `provider == "local"`：保留现有 transformers 本地推理（模型已预下载时可用）。
- 删除对 `_DEFAULTS` 中 llm 段的影响（仅配置段扩展）。

#### `vlm.py`（GGUF / llama.cpp）
- `describe(frames, prompt)`：
  - `provider == "none"`：抛 `RuntimeError`（不变）。
  - `provider == "local"` 且 `model` 指向 `.gguf` 文件：用 `llama_cpp.Llama` 加载（`n_gpu_layers` 由 `DeviceManager` 决定，cuda 时全部层上 GPU），多模态对话，返回 `parse_vlm_json` 的结果。
  - 加载器做模块级单例缓存（同一模型文件只加载一次），供 reranker 复用。
- `vlm_repair_json` / `parse_vlm_json` 保持不变。

#### `reranker.py`（`app/matching/reranker.py`）
- `rerank_candidates(cands, settings, log)`：当 `settings.vlm_reranker` 可用时，用 VLM 加载器对候选做二次判断重排；不可用时原样返回（不变）。

#### `whisper.py` → `asr.py`（FunASR）
- 新建 `app/models/asr.py`，类名 `ASR`：
  - `transcribe(audio_path)`：`provider == "none"` 返回 `[]`；`local` 时用 `funasr.AutoModel` 加载 paraformer 模型转写，输出对齐为 `[{"start", "end", "text"}]`。
- 删除 `app/models/whisper.py`。
- 同步修改引用：
  - `app/analyzer/audio.py`：`from app.models.whisper import Whisper` → `from app.models.asr import ASR`；`Whisper(...)` → `ASR(...)`。
  - `app/config/settings.py`：`_DEFAULTS["models"]` 的 `"whisper"` 键改 `"asr"`；`Settings` 字段 `whisper` 改 `asr`；`load_settings` 同步。
  - `config.yaml` / `config.yaml.example`：`whisper:` 段改 `asr:`。
  - `app/index/search.py` / `app/pipeline/index_pipeline.py` 不直接引用 whisper，无需改（经 `audio.transcribe` 间接）。

#### `embedding.py`
- 保持不变（`SentenceTransformer` 从本地 `models/embedding/` 或 HF 缓存加载均可）。`--write-config` 会把路径写为本地路径。

### 3. `tests/test_download_models.py`（新增）

- 模型清单完整性（3 个角色齐全）。
- 双源 ID 映射正确（HF ↔ MS）。
- `--write-config` 写回逻辑：mock `snapshot_download`，验证 config.yaml 的 `model` 字段被写为本地路径。
- 参数解析：`--list`、`--model` 过滤、`--source` 校验。

### 4. 配置与安全

- `.gitignore` 增加 `config.yaml`；`git rm --cached config.yaml` 从仓库移除（本地文件保留）。
- `config.yaml.example` 保留为模板并含注释，覆盖新配置段：
  ```yaml
  models:
    llm:       {provider: openai, model: "gpt-4o-mini", base_url: "https://api.openai.com/v1", api_key: ""}
    vlm:       {provider: none, model: "", device: auto}
    vlm_reranker: {provider: none, model: "", device: auto}
    asr:       {provider: none, model: "", device: auto}
    embedding: {provider: none, model: "", device: auto}
  ```
- `requirements-models.txt` 增加：`openai`、`huggingface_hub`、`modelscope`、`llama-cpp-python`、`funasr`、`onnxruntime`。
- api_key 支持：优先 `llm.api_key` 配置，其次环境变量 `OPENAI_API_KEY` 兜底（`generate` 内读取）。

### 5. `app/config/settings.py` 扩展

- `ModelConfig` 增加 `base_url: str = ""`、`api_key: str = ""` 字段。
- `load_settings` 从 `merge["models"][k]` 透传（缺省保持空串）。
- `_DEFAULTS["models"]` 各段增加 `"base_url": "", "api_key": ""` 默认（仅 llm 需要，其余保持空）。

## 错误处理

- 下载失败：脚本打印源/模型/错误，建议切换 `--source` 重试，非零退出码。
- 网络不可达：SDK 异常捕获，提示 `--source ms`（国内网络 HF 常不可达）。
- LLM 线上调用失败：`RuntimeError` 上抛（调用方 `parse_script` 已按 Task 10 裁定做兜底/降级）。
- 模型文件缺失：对应 provider 加载时报错，主流程因 `available()` 为 False 走规则兜底。

## 验收标准

1. `python scripts/download_models.py --list` 打印 3 个模型的双源 ID。
2. `python scripts/download_models.py --source ms --model embedding --write-config`（或真实网络下载任一）成功。
3. 全量 `pytest tests/` 保持全绿（既有 38 个 + 新增）。
4. 无模型时主流程（build）仍正常规则兜底，不受重构影响。
