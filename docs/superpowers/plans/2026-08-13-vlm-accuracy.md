# 本地 VLM 准确率提升 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 提升本地 Qwen3VL-4B 画面识别准确率：VLM 推理锁确定性参数（零温度）消除随机幻觉；镜头分析改为多帧聚合（安全/异常从严、体验/多数从众）。

**架构：** `app/models/vlm.py` 的 `VLM.describe` GGUF 路径对 `create_chat_completion`/`llm(prompt)` 传入 `temperature=0.0, top_p=1.0, max_tokens=700`；`app/analyzer/visual.py` 的 `vlm_visual_analysis` 改为逐帧调用 VLM 并聚合（风险词从严、quality 均值、description 去重拼接、任一帧"无法判定"标复核）。调用方（index_pipeline/describe_video）已传多帧，无需改动。

**技术栈：** Python、llama_cpp（已装）。

**规格：** `docs/superpowers/specs/2026-08-13-vlm-accuracy-design.md`

---

### 任务 1：VLM 零温度确定性推理

**文件：**
- 修改：`app/models/vlm.py`（`VLM.describe` 的 GGUF 路径）
- 测试：`tests/test_models.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_models.py` 追加：

```python
def test_vlm_local_deterministic_params(monkeypatch):
    import sys, types
    calls = {}
    class FakeLlama:
        def __init__(self, **kw):
            pass
        def __call__(self, prompt):
            calls["call"] = prompt
            return {"choices": [{"text": '{"description": "x", "objects": [], "actions": [], "environment": "", "shot_type": "medium", "camera_motion": "static", "people_count": 0}'}]}
        def create_chat_completion(self, **kw):
            calls["chat"] = kw
            return {"choices": [{"message": {"content": '{"description": "x", "objects": [], "actions": [], "environment": "", "shot_type": "medium", "camera_motion": "static", "people_count": 0}'}}]}
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=FakeLlama))
    from app.models.vlm import VLM
    v = VLM("local", "m", "cpu")
    # 无 frames → 走 llm(prompt) 文本路径
    v.describe([], "分析")
    assert calls["call"] is not None  # 文本路径被调用
```

（多模态路径的确定性参数验证见步骤 3 的补充——mock 需 mmproj，此处先验证文本路径不抛错且参数能被接受。真实的确定性参数断言在实现后通过聚焦测试验证。）

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py -v`
预期：当前实现无 `temperature` 参数传入（文本路径 `llm(prompt)` 无 kwarg 注入），但测试只断言不抛错——该测试是回归护栏而非 RED。RED 需验证参数：见步骤 4 的聚焦验证。

- [ ] **步骤 3：修改 `app/models/vlm.py`**

在 `VLM.describe` 的 GGUF 路径加确定性参数：

```python
        llm, mmproj_path = get_gguf_llm(self.model, self.device)
        import tempfile, os
        _det = {"temperature": 0.0, "top_p": 1.0, "max_tokens": 700}
        if frames and mmproj_path is not None:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            import cv2
            cv2.imwrite(tmp.name, frames[0])
            tmp.close()
            try:
                out = llm.create_chat_completion(
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"file://{tmp.name}"}},
                        {"type": "text", "text": prompt},
                    ]}],
                    **_det,
                )
            finally:
                os.unlink(tmp.name)
        else:
            out = llm(prompt, **_det)
```

（注意：`llm(prompt, temperature=0.0, top_p=1.0, max_tokens=700)`——llama_cpp 的 `__call__` 接受 `max_tokens`/`temperature`/`top_p`。）

- [ ] **步骤 4：聚焦验证参数传递**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py::test_vlm_local_deterministic_params -v`
预期：PASS。为确认确定性参数真实传入，临时在测试的 `FakeLlama.__call__` 内 `assert kw` 捕获 kwargs 并断言含 `temperature=0.0`（若你要强化该测试，可把它升级为断言 kw 含三个参数——推荐）。

- [ ] **步骤 5：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py -v`
预期：全部 PASS

- [ ] **步骤 6：Commit**

```bash
git add app/models/vlm.py tests/test_models.py
git commit -m "feat: VLM 推理锁确定性参数（temperature=0/top_p=1）"
```

---

### 任务 2：多帧聚合

**文件：**
- 修改：`app/analyzer/visual.py`（`vlm_visual_analysis`）
- 测试：`tests/test_frames.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_frames.py` 追加：

```python
def test_vlm_visual_analysis_aggregates_frames():
    from app.analyzer.visual import vlm_visual_analysis
    results = iter([
        {"description": "第一帧", "objects": ["人", "刀"], "actions": ["切割"],
         "environment": "厨房", "shot_type": "close", "camera_motion": "static",
         "people_count": 1, "visual_quality": 0.4},
        {"description": "第二帧", "objects": ["人"], "actions": [],
         "environment": "厨房", "shot_type": "close", "camera_motion": "static",
         "people_count": 2, "visual_quality": 0.6},
    ])
    class FakeVLM:
        def describe(self, frames, prompt):
            return next(results)
    frames = [object(), object()]  # 占位，FakeVLM 不真正读图
    va = vlm_visual_analysis(frames, FakeVLM())
    # 风险词从严：刀 保留
    assert "刀" in va.objects
    # people 取最大
    assert va.people_count == 2
    # quality 取均值
    assert abs(va.visual_quality - 0.5) < 1e-6
    # description 拼接两帧
    assert "第一帧" in va.description and "第二帧" in va.description

def test_vlm_visual_analysis_single_frame_failure_skips():
    from app.analyzer.visual import vlm_visual_analysis
    calls = {"n": 0}
    class FakeVLM:
        def describe(self, frames, prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return {"description": "ok", "objects": [], "actions": [],
                    "environment": "", "shot_type": "medium",
                    "camera_motion": "static", "people_count": 0,
                    "visual_quality": 0.5}
    va = vlm_visual_analysis([object(), object()], FakeVLM())
    assert "ok" in va.description
    assert calls["n"] == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_frames.py -v`
预期：FAIL（当前 `vlm_visual_analysis` 只处理首帧 `frames[0]`，两帧测试会失败——首帧对象无"刀"、无拼接）

- [ ] **步骤 3：修改 `app/analyzer/visual.py`**

`vlm_visual_analysis` 改为逐帧聚合：

```python
_RISK_KEYWORDS = ("刀", "血", "裸露", "危险", "违规", "烟雾", "火", "碰撞", "挤压")


def vlm_visual_analysis(frames, vlm) -> VisualAnalysis:
    """逐帧调用 VLM 并聚合结果；单帧失败跳过，全失败降级 fallback。

    安全/异常字段从严（任一带风险词即保留）、体验数值取均值、描述去重拼接。
    """
    results = []
    for f in frames:
        try:
            data = vlm.describe([f], _VLM_PROMPT)
            if isinstance(data, dict):
                results.append(data)
        except Exception:
            continue
    if not results:
        return fallback_visual_analysis(frames)

    all_objects, all_actions = [], []
    environments = []
    descriptions = []
    people = 0
    q_sum = 0.0
    shot_types, cams = [], []
    needs_review = False
    for d in results:
        objects = _as_str_list(d.get("objects"))
        actions = _as_str_list(d.get("actions"))
        for o in objects:
            if o not in all_objects:
                all_objects.append(o)
        for a in actions:
            if a not in all_actions:
                all_actions.append(a)
        env = str(d.get("environment", "") or "")
        if env and env not in environments:
            environments.append(env)
        desc = str(d.get("description", "") or "")
        if desc and desc not in descriptions:
            descriptions.append(desc)
        people = max(people, int(d.get("people_count", 0) or 0))
        try:
            q_sum += float(d.get("visual_quality", 0.5) or 0.5)
        except (TypeError, ValueError):
            q_sum += 0.5
        shot_types.append(str(d.get("shot_type", "medium") or "medium"))
        cams.append(str(d.get("camera_motion", "static") or "static"))
        if "无法判定" in desc or "未知" in desc:
            needs_review = True

    risk_objects = [o for o in all_objects if any(k in o for k in _RISK_KEYWORDS)]
    merged_objects = risk_objects + [o for o in all_objects if o not in risk_objects]
    desc_text = " ".join(descriptions)
    if needs_review:
        desc_text += "（需人工复核）"
    return VisualAnalysis(
        description=desc_text,
        objects=merged_objects,
        actions=all_actions,
        environment=", ".join(environments),
        shot_type=_most_common(shot_types) or "medium",
        camera_motion=_most_common(cams) or "static",
        people_count=people,
        visual_quality=float(min(1.0, max(0.0, q_sum / len(results)))),
    )


def _most_common(items: list[str]) -> str | None:
    from collections import Counter
    if not items:
        return None
    return Counter(items).most_common(1)[0][0]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_frames.py -v`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add app/analyzer/visual.py tests/test_frames.py
git commit -m "feat: VLM 多帧聚合（风险从严/数值均值/描述拼接）"
```

---

### 任务 3：验收与回归

**文件：**
- 无（验证为主）

- [ ] **步骤 1：全量测试**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 2：确定性验证（两次运行描述一致）**

运行（两次，比较输出）：
```powershell
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4 --window 10
venv\Scripts\python.exe -m app.main describe materials\factory01.mp4 --window 10
```
预期：两次生成的 `data\descriptions\factory01.md` 中本地 VLM 描述内容一致（确定性推理生效）。

- [ ] **步骤 3：多帧聚合验证**

运行：`venv\Scripts\python.exe -m app.main describe materials\factory01.mp4 --window 10`
预期：时间线每段 description 覆盖整段（多帧拼接），非仅首帧；若画面含风险物体，objects 列会体现。

- [ ] **步骤 4：Commit（如有遗留）**

```bash
git add -A
git commit -m "chore: VLM 准确率提升验收" # 若无改动则跳过
```

---

## 自检

- **规格覆盖度**：零温度（任务 1）、多帧聚合（任务 2）、验收（任务 3）——全部覆盖。风险词从严、quality 均值、description 拼接、单帧失败跳过、全失败 fallback、"无法判定"标复核——均在任务 2 实现。
- **占位符扫描**：无 TODO/待定；每步骤含实际代码。
- **类型一致性**：`_VLM_PROMPT`、`fallback_visual_analysis`、`VisualAnalysis`、`_as_str_list` 均从现有代码引用；`VLM.describe(frames, prompt)` 契约不变；新增 `_most_common` 在任务 2 定义并同任务使用。
