# 规格：VLM 画面对比功能（本地 vs 线上）

日期：2026-08-13
状态：已批准

## 背景

本地 VLM（Qwen3-VL-2B）画面描述不准确（把 testsrc2 测试图案描述成"室内场景/行人"）。需要用线上视觉 LLM（智谱 GLM-4V-Flash，同一 api_key）对同一画面做描述，与本地 VLM 结果对比，供人类校验本地描述是否可靠。

## 关键事实（已实测）

- 当前 LLM `glm-4.7-flash` 是纯文本模型，不支持图像输入（`content.type` 仅限 `['text']`）。
- `glm-4.6v-flash` 返回 429 限流；**`glm-4v-flash` 已验证可用**，视觉描述准确（"一位穿着白色上衣的女士站在墙前..."），使用与 llm 相同的 `base_url`/`api_key`。
- 本地 VLM `describe()` 内部用 `_VLM_PROMPT` 要求 JSON 输出；传自定义提示词时可能得到纯文本导致 `parse_vlm_json` 失败——对比功能必须使用 `_VLM_PROMPT` 或统一提示词。

## 组件设计

### 1. 配置：`settings.vlm_compare`

- `app/config/settings.py`：`_DEFAULTS["models"]` 增加 `"vlm_compare"` 段（默认 none）；`Settings` 增加 `vlm_compare: ModelConfig` 字段；`load_settings` 透传。
- `config.yaml` / `config.yaml.example`：
  ```yaml
  vlm_compare: {provider: openai, model: "glm-4v-flash", device: auto,
                base_url: "https://open.bigmodel.cn/api/paas/v4", api_key: ""}
  ```
  （api_key 留空时走环境变量 `OPENAI_API_KEY` 兜底；config.yaml 不入库。）

### 2. `app/models/vlm.py`：VLM 支持 openai provider（复用现有）

- 现有 `VLM.describe()` 已有 openai 分支（`_describe_openai`，base64 图调用）。`available()` 对 openai 返回 True（基类已支持）。
- 无代码改动，仅确认 `_describe_openai` 使用 `self.model`（glm-4v-flash）作为 model 名。

### 3. `app/analyzer/compare.py`（新增）：`compare_video(settings, video_path, log) -> Path`

流程：
1. `detect_shots` + `_subdivide`（复用 describe.py 的镜头切分，窗口默认 5s）切镜头。
2. 每镜头抽首帧（`extract_frame`）。
3. 双路描述：
   - 本地：`VLM(vlm.provider, vlm.model, vlm.device, ...)`，用 `_VLM_PROMPT` 提示词调 `describe()`。
   - 线上：`VLM(vlm_compare.provider, vlm_compare.model, ..., vlm_compare.base_url, vlm_compare.api_key)`，用相同提示词调 `describe()`。
4. 一致性判断：把**画面 + 本地描述**发给线上 GLM-4V，让它输出 JSON `{"consistent": true/false, "diff": "差异说明"}`——线上模型同时看到图和本地描述，直接做视觉裁判。
5. 输出 `data/descriptions/<name>_compare.md`，表格：
   | 时间码 | 本地描述 | 线上描述 | 一致性 |
   每个镜头一行；另含汇总（一致镜头数/总数）。

### 4. `app/main.py`：新增 `compare <视频>` 子命令

- 参数 `video`（必选）、`--window`（默认 5s，与 describe 一致）。
- `cmd_compare`：find_ffmpeg → setup_logging → `compare_video` → 打印报告路径。

## 错误处理

- GLM-4V 限流/超时（429/超时）：该镜头线上描述标"线上失败"，一致性判断标"未知"，不中断整体。
- 本地 VLM 解析失败：该镜头本地描述降级 `fallback_visual_analysis`（复用现有逻辑）。
- 图片输入/空镜头：跳过。

## 验收标准

1. `python -m app.main compare materials\factory01.mp4` 生成 `data/descriptions/factory01_compare.md`。
2. 报告每镜头含本地描述、线上描述、一致性判断三列。
3. 全量 `pytest tests/` 保持全绿。
4. 线上失败时单镜头降级不崩溃。
