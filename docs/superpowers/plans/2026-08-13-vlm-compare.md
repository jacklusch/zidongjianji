# VLM 画面对比功能 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 新增 `compare` 命令：对单个视频，同一画面分别用本地 VLM（Qwen3-VL-2B）与线上 VLM（GLM-4V-Flash）描述，并让线上模型做一致性裁判，输出 Markdown 对比报告供人工校验。

**架构：** `app/analyzer/compare.py` 提供 `compare_video()`——切镜头（复用 describe.py 的 `_subdivide`/`_shot_frames`），每镜头首帧分别喂给本地与线上 `VLM` 实例（openai provider 走现有 `_describe_openai`），一致性判断让线上模型同时看图+本地描述输出 JSON。`app/main.py` 新增 `compare` 子命令；`app/config/settings.py` 新增 `vlm_compare` 配置段。

**技术栈：** Python、openai SDK（已装）、llama_cpp（已装）、现有 VLM/describe 模块。

**规格：** `docs/superpowers/specs/2026-08-13-vlm-compare-design.md`

---

### 任务 1：settings 增加 vlm_compare 配置段

**文件：**
- 修改：`app/config/settings.py`（`_DEFAULTS["models"]`、`Settings` 字段、`load_settings`）
- 修改：`config.yaml`、`config.yaml.example`
- 测试：`tests/test_settings.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_settings.py` 追加：

```python
def test_settings_has_vlm_compare():
    s = load_settings()
    assert hasattr(s, "vlm_compare")
    assert isinstance(s.vlm_compare.base_url, str)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
预期：FAIL（`Settings` 无 `vlm_compare` 属性）

- [ ] **步骤 3：修改 `app/config/settings.py`**

`_DEFAULTS["models"]` 增加：

```python
"vlm_compare": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
```

`Settings` 字段（在 `vlm_reranker` 后）：

```python
vlm_compare: ModelConfig = field(default_factory=ModelConfig)
```

`load_settings`：

```python
vlm_compare=ModelConfig(**merge["models"]["vlm_compare"]),
```

- [ ] **步骤 4：修改 `config.yaml` 与 `config.yaml.example`**

在 `vlm_reranker:` 段后加入：

```yaml
  vlm_compare:
    provider: openai
    model: glm-4v-flash
    device: auto
    base_url: https://open.bigmodel.cn/api/paas/v4
    api_key: ''
```

（config.yaml 不入库；api_key 留空走 `OPENAI_API_KEY` 环境变量兜底。）

- [ ] **步骤 5：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add app/config/settings.py config.yaml config.yaml.example tests/test_settings.py
git commit -m "feat: settings 增加 vlm_compare 配置段"
```

---

### 任务 2：`app/analyzer/compare.py` 对比逻辑

**文件：**
- 创建：`app/analyzer/compare.py`
- 测试：`tests/test_compare.py`（新建）

- [ ] **步骤 1：编写失败的测试**

创建 `tests/test_compare.py`：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.analyzer.compare import _judge_consistency, _build_report

class FakeShot:
    def __init__(self, shot_id, start, end, duration):
        self.shot_id = shot_id
        self.start = start
        self.end = end
        self.duration = duration

def test_judge_consistency_consistent():
    online = type("V", (), {"describe": lambda self, frames, prompt: {"consistent": True, "diff": ""}})()
    verdict = _judge_consistency(online, [None], "本地描述", "线上描述")
    assert verdict["consistent"] is True
    assert "本地描述" in verdict["prompt_used"]

def test_judge_consistency_parse_failure_fallback():
    online = type("V", (), {"describe": lambda self, frames, prompt: {"consistent": False}})()
    verdict = _judge_consistency(online, [None], "a", "b")
    assert verdict["consistent"] is False

def test_build_report_has_three_columns():
    shots = [FakeShot("s1", 0.0, 5.0, 5.0)]
    rows = [{"shot": "s1", "start": 0.0, "end": 5.0, "local": "L", "online": "O",
             "consistent": True, "diff": ""}]
    md = _build_report("factory01.mp4", rows, 1, 1)
    assert "本地描述" in md and "线上描述" in md and "一致性" in md
    assert "L" in md and "O" in md
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_compare.py -v`
预期：FAIL（`No module named 'app.analyzer.compare'`）

- [ ] **步骤 3：实现 `app/analyzer/compare.py`**

```python
"""本地 VLM 与线上 VLM 的画面对比（供人工校验本地描述）。"""
import json
from pathlib import Path
from app.models.vlm import VLM
from app.analyzer.scene import detect_shots, is_image
from app.analyzer.describe import _subdivide, _shot_frames, _fmt_range
from app.analyzer.visual import fallback_visual_analysis, _VLM_PROMPT

_COMPARE_PROMPT = (
    "这是一张视频画面。以下是另一个模型对它的描述：\n"
    '"{local_desc}"\n\n'
    "请判断该描述是否与画面内容一致（对象、动作、场景是否准确）。"
    "只输出 JSON：{\"consistent\": true或false, \"diff\": \"不一致时的差异说明或空\"}"
)


def _judge_consistency(online_vlm, frames, local_desc, online_desc) -> dict:
    """让线上 VLM 同时看图 + 本地描述，输出一致性判断。"""
    prompt = _COMPARE_PROMPT.format(local_desc=local_desc)
    try:
        data = online_vlm.describe(frames, prompt)
        consistent = bool(data.get("consistent", False))
        diff = str(data.get("diff", "") or "")
    except Exception:
        consistent = False
        diff = "线上裁判失败（限流或解析错误）"
    return {"consistent": consistent, "diff": diff}


def _build_report(video_name: str, rows: list[dict], n_consistent: int, n_total: int) -> str:
    lines = [
        f"# VLM 画面对比：{video_name}",
        "",
        f"一致镜头：{n_consistent}/{n_total}",
        "",
        "| 时间码 | 本地描述 | 线上描述 | 一致性 | 差异 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        c = "✅" if r["consistent"] else "❌"
        lines.append(
            f"| {_fmt_range(r['start'], r['end'])} | {r['local']} | {r['online']} | {c} | {r['diff']} |"
        )
    return "\n".join(lines) + "\n"


def compare_video(settings, video_path, log=None, window: float = 5.0) -> Path:
    """对比单个视频的本地/线上 VLM 描述，输出 data/descriptions/<name>_compare.md。"""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"文件不存在: {video_path}")
    if is_image(video_path):
        raise ValueError(f"compare 需要视频文件: {video_path}")
    out_dir = Path(settings.data_dir) / "descriptions"
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = out_dir / "tmp_thumb"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    local_vlm = VLM(settings.vlm.provider, settings.vlm.model, settings.vlm.device,
                    settings.vlm.base_url, settings.vlm.api_key)
    compare_cfg = settings.vlm_compare
    online_vlm = VLM(compare_cfg.provider, compare_cfg.model, compare_cfg.device,
                     compare_cfg.base_url, compare_cfg.api_key)

    shots = _subdivide(detect_shots(str(video_path), settings.scene_threshold,
                                    settings.min_shot_duration, settings.ffmpeg),
                       window=window)
    rows = []
    n_consistent = 0
    for shot in shots:
        frames = _shot_frames(video_path, shot, settings, thumb_dir, shot.shot_id)
        local_desc = "-"
        online_desc = "-"
        try:
            ld = local_vlm.describe(frames, _VLM_PROMPT)
            local_desc = str(ld.get("description", "") or "")
        except Exception as e:
            if log:
                log.warning(f"  [compare] {shot.shot_id} 本地 VLM 失败: {e}")
        try:
            od = online_vlm.describe(frames, _VLM_PROMPT)
            online_desc = str(od.get("description", "") or "")
        except Exception as e:
            if log:
                log.warning(f"  [compare] {shot.shot_id} 线上 VLM 失败: {e}")
            online_desc = "（线上失败）"
        verdict = {"consistent": False, "diff": ""}
        if local_desc != "-" and online_desc != "（线上失败）":
            verdict = _judge_consistency(online_vlm, frames, local_desc, online_desc)
            if verdict["consistent"]:
                n_consistent += 1
        rows.append({"shot": shot.shot_id, "start": shot.start, "end": shot.end,
                     "local": local_desc, "online": online_desc,
                     "consistent": verdict["consistent"], "diff": verdict["diff"]})

    md = _build_report(video_path.name, rows, n_consistent, len(rows))
    out = out_dir / f"{video_path.stem}_compare.md"
    out.write_text(md, encoding="utf-8")
    return out
```

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_compare.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add app/analyzer/compare.py tests/test_compare.py
git commit -m "feat: VLM 本地/线上画面对比逻辑"
```

---

### 任务 3：`compare` 子命令 + 验收

**文件：**
- 修改：`app/main.py`
- 修改：`docs/manual-test-guide.md`
- 测试：`tests/test_compare.py`（追加）

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_compare.py` 追加：

```python
def test_compare_video_output_file(tmp_path, monkeypatch):
    from app.analyzer.compare import compare_video
    class FakeSettings:
        data_dir = tmp_path
        vlm = type("MC", (), {"provider": "local", "model": "m", "device": "cpu", "base_url": "", "api_key": ""})()
        vlm_compare = type("MC", (), {"provider": "openai", "model": "glm-4v-flash", "device": "cpu", "base_url": "u", "api_key": "k"})()
        scene_threshold = 0.35
        min_shot_duration = 1.0
        ffmpeg = "ffmpeg"
        frames_min = 3
        frames_max = 8
    # 用一个真实存在的视频文件（conftest 的 sample_video）
    import shutil
    from pathlib import Path
    v = Path(tmp_path) / "x.mp4"
    v.write_bytes(b"fake")  # 占位，会被下面的 monkeypatch 拦截
    monkeypatch.setattr("app.analyzer.compare.detect_shots",
                        lambda *a, **k: [type("S", (), {"shot_id": "s1", "start": 0.0, "end": 4.0, "duration": 4.0})()])
    monkeypatch.setattr("app.analyzer.compare._subdivide", lambda shots, window: shots)
    monkeypatch.setattr("app.analyzer.compare._shot_frames", lambda *a, **k: [None])
    monkeypatch.setattr("app.analyzer.compare.VLM", lambda *a, **k: type("V", (), {
        "describe": lambda self, frames, prompt: {"description": "工厂画面"}
    })())
    out = compare_video(FakeSettings(), v)
    assert out.exists()
    assert "_compare.md" in out.name
    assert "工厂画面" in out.read_text(encoding="utf-8")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_compare.py -v`
预期：FAIL（`compare_video` 未定义）——步骤 3 后转为 PASS

- [ ] **步骤 3：修改 `app/main.py`**

新增 `cmd_compare`：

```python
def cmd_compare(args):
    from pathlib import Path
    from app.analyzer.compare import compare_video
    settings = load_settings()
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "compare")
    out = compare_video(settings, Path(args.video), log=log, window=args.window)
    print(f"VLM 对比报告: {out}")
    print(out.read_text(encoding="utf-8"))
```

在 `build_parser()` 的 describe 后：

```python
    s = sub.add_parser("compare", help="对比本地/线上 VLM 画面描述")
    s.add_argument("video")
    s.add_argument("--window", type=float, default=5.0, help="镜头细分窗口秒数")
    s.set_defaults(func=cmd_compare)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_compare.py -v`
预期：PASS

- [ ] **步骤 5：人工验收**

运行：`venv\Scripts\python.exe -m app.main compare materials\factory01.mp4`
预期：生成 `data\descriptions\factory01_compare.md`，每镜头含本地/线上描述与一致性列；线上 GLM-4V 限流时该行标注"线上失败"，不中断。

- [ ] **步骤 6：更新 `docs/manual-test-guide.md`**

在 3.6 describe 后新增 3.7 compare 小节：

```markdown
### 3.7 compare —— 对比本地/线上 VLM 画面描述

```powershell
venv\Scripts\python.exe -m app.main compare materials\factory01.mp4
```

**预期**：生成 `data\descriptions\factory01_compare.md`，每镜头一行：时间码、本地 VLM 描述、线上 GLM-4V 描述、一致性（✅/❌）、差异说明。线上限流时该镜头标"线上失败"不中断。
```

- [ ] **步骤 7：运行全量测试**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 8：Commit**

```bash
git add app/main.py docs/manual-test-guide.md tests/test_compare.py
git commit -m "feat: compare 命令对比本地/线上 VLM 画面描述"
```

---

## 自检

- **规格覆盖度**：配置段（任务 1）、对比逻辑（任务 2）、命令+报告（任务 3）、错误处理（限流降级在 compare_video 内）——全部覆盖。
- **占位符扫描**：无 TODO/待定；每步骤含实际代码与命令。
- **类型一致性**：`settings.vlm_compare`（任务 1 定义）→ 任务 2/3 使用一致；`VLM.describe(frames, prompt)` 契约复用；`_subdivide`/`_shot_frames`/`_fmt_range` 从 describe.py 导入（已存在）；`_VLM_PROMPT` 从 visual.py 导入（已存在）。
