# 规格：本地 VLM 准确率提升（零温度推理 + 多帧聚合）

日期：2026-08-13
状态：已批准

## 背景

本地 VLM（Qwen3VL-4B Q4_K_M）画面识别存在随机性幻觉、单帧漏检/误判。目标：提升识别准确率与稳定性。

方案范围（用户确认）：**零温度确定性推理 + 多帧聚合**，不引入 YOLO。应用范围（用户确认）：**全局 + 多帧聚合**（VLM.describe 全局确定性，describe/analyze 镜头多帧聚合）。

## 关键事实（已实测）

- `llama_cpp.Llama.create_chat_completion` 支持 `temperature`/`top_p`/`max_tokens` 参数（`__init__` 构造器不支持 temperature，须在推理调用时传）。
- `VLM.describe` 的 GGUF 路径用 `llm.create_chat_completion(messages=[...])`（多模态）或 `llm(prompt)`（文本补全）。
- `index_pipeline._analyze_shot` / `describe_video` 已传多帧（`frames` 列表，由 `frames_min`/`frames_max` 控制）。

## 组件设计

### 1. `app/models/vlm.py`：零温度确定性推理

- `VLM.describe` 的 GGUF 路径：`create_chat_completion` 与 `llm(prompt)` 均传入确定性参数：
  ```python
  _DETERMINISTIC = {"temperature": 0.0, "top_p": 1.0, "max_tokens": 700}
  ```
- 效果：同一帧每次推理结果完全一致，消除随机幻觉与枚举值乱输出。
- openai provider 路径（`_describe_openai`）保持现有参数（线上模型已有确定性）。

### 2. `app/analyzer/visual.py`：多帧聚合

- `vlm_visual_analysis(frames, vlm)` 改为**逐帧**调用 VLM（对 frames 每帧单独 `describe`，最多 `settings` 允许的帧数），聚合结果：
  - **安全/异常字段（从严）**：objects/actions/environment 中任一带风险词（`刀|血|裸露|危险|违规|烟雾|火` 等关键词）→ 聚合结果保留该风险项；people_count 取最大值。
  - **体验/数值字段（从众/均值）**：visual_quality 取均值；shot_type/camera_motion 取多数。
  - **description**：多帧描述去重拼接（每帧一段，避免重复）。
- 单帧 VLM 失败 → 跳过该帧；全部失败 → `fallback_visual_analysis`。
- 任一帧输出含"无法判定/未知" → 该镜头标人工复核（`needs_review=True` 标记，写入 description 后缀或单独字段）。

### 3. 调用方

- `index_pipeline._analyze_shot` / `describe_video` 无需改动（已传多帧，聚合在 `vlm_visual_analysis` 内部完成）。

## 错误处理

- 单帧 VLM 异常：捕获跳过，不中断镜头。
- 全部帧失败：降级 `fallback_visual_analysis`（现有逻辑）。
- 聚合时逻辑矛盾（如一帧"昏暗"一帧"过亮"）：按从严取负面结果。

## 测试

- `tests/test_models.py`：mock `create_chat_completion`，断言描述调用传入 `temperature=0.0`/`top_p=1.0`/`max_tokens=700`。
- `tests/test_frames.py`：多帧聚合测试——两帧中一帧 objects 含风险词 → 聚合保留风险项；quality 取均值；单帧失败跳过、全失败降级 fallback。

## 验收标准

1. 全量 `pytest tests/` 保持全绿。
2. `describe`/`compare` 命令对同一视频两次运行，本地 VLM 描述输出一致（确定性）。
3. 多帧聚合生效：`_analyze_shot`/`describe_video` 输出覆盖整镜头信息（非仅首帧）。
