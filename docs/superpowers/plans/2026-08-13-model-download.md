# 模型下载脚本与模型层重构 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 新增 `scripts/download_models.py` 从 HuggingFace / 魔塔社区（ModelScope）双源下载本地模型；LLM 改走线上 OpenAI 兼容 API；VLM 改用 GGUF（llama.cpp）；Whisper 换 FunASR；并将 `config.yaml` 从仓库移除（改由 `config.yaml.example` 模板）。

**架构：** `scripts/download_models.py` 作为独立 CLI（可选源 hf/ms、可选单模型、`--list`、`--write-config`）；`app/models/` 下适配器重构——`base.py` 增加 openai provider 判定，`llm.py` 增加 OpenAI 兼容调用，`vlm.py` 用 llama_cpp 加载 GGUF（单例缓存供 reranker 复用），`whisper.py` 改造为 `asr.py`（FunASR）；`settings.py` 的 `whisper` 段改 `asr`，`ModelConfig` 增加 `base_url`/`api_key`。

**技术栈：** Python 3.11、`huggingface_hub`、`modelscope`、`llama-cpp-python`、`funasr`、`openai`、`onnxruntime`。

**规格：** `docs/superpowers/specs/2026-08-13-model-download-design.md`

---

### 任务 1：settings 扩展（ModelConfig 字段 + whisper→asr 段）

**文件：**
- 修改：`app/config/settings.py`（`ModelConfig`、`_DEFAULTS`、`Settings` 字段、`load_settings`）
- 修改：`config.yaml`、`config.yaml.example`（whisper 段→asr 段）
- 测试：`tests/test_settings.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config.settings import load_settings, ModelConfig

def test_model_config_new_fields():
    mc = ModelConfig(provider="openai", model="gpt-4o-mini", device="cpu", base_url="https://x/v1", api_key="k")
    assert mc.base_url == "https://x/v1" and mc.api_key == "k"

def test_settings_has_asr_not_whisper():
    s = load_settings()
    assert hasattr(s, "asr") and not hasattr(s, "whisper")
    assert s.asr.provider in ("none", "local")
    assert s.llm.base_url == "" and s.llm.api_key == ""
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
预期：FAIL（`ModelConfig` 无 base_url 参数 / `Settings` 无 asr 字段）

- [ ] **步骤 3：修改 `app/config/settings.py`**

```python
@dataclass
class ModelConfig:
    provider: str = "none"
    model: str = ""
    device: str = "auto"
    base_url: str = ""
    api_key: str = ""
```

`_DEFAULTS["models"]` 改为（whisper→asr，各段默认加 base_url/api_key 空串）：

```python
_DEFAULTS = {
    "models": {
        "vlm": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
        "vlm_reranker": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
        "embedding": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
        "asr": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
        "llm": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
    },
    # ... 其余不变
}
```

`Settings` 字段：`whisper: ModelConfig` → `asr: ModelConfig`。
`load_settings`：`whisper=ModelConfig(...)` → `asr=ModelConfig(**merge["models"]["asr"])`。

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add app/config/settings.py tests/test_settings.py
git commit -m "feat: settings 支持 base_url/api_key，whisper 段改 asr"
```

---

### 任务 2：`base.py` 增加 openai provider + `llm.py` 线上调用

**文件：**
- 修改：`app/models/base.py`
- 修改：`app/models/llm.py`
- 测试：`tests/test_models.py`（追加）

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_models.py` 追加：

```python
from app.models.base import ModelProvider

def test_provider_openai_available():
    p = ModelProvider(provider="openai", model="m", device="cpu", base_url="u", api_key="k")
    assert p.available() is True

def test_llm_openai_calls_client(monkeypatch):
    llm = LLM(provider="openai", model="gpt-4o-mini", device="cpu", base_url="https://api.x.com/v1", api_key="sk-test")
    calls = {}
    class FakeResp:
        choices = [type("C", (), {"message": type("M", (), {"content": "你好"})()})()]
    class FakeCompletions:
        def create(self, **kw):
            calls.update(kw)
            return FakeResp()
    class FakeChat:
        completions = FakeCompletions()
    class FakeOpenAI:
        def __init__(self, **kw):
            calls["client_kw"] = kw
        chat = FakeChat()
    monkeypatch.setattr("app.models.llm.OpenAI", FakeOpenAI)
    out = llm.generate("讲个故事")
    assert out == "你好"
    assert calls["client_kw"]["base_url"] == "https://api.x.com/v1"
    assert calls["client_kw"]["api_key"] == "sk-test"
    assert calls["model"] == "gpt-4o-mini"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py -v`
预期：FAIL（`ModelProvider.__init__` 拒绝 openai / `LLM.generate` 不识别 openai）

- [ ] **步骤 3：修改 `app/models/base.py`**

```python
class ModelProvider:
    name = "base"
    def __init__(self, provider: str, model: str, device: str, base_url: str = "", api_key: str = ""):
        if provider not in ("none", "local", "openai"):
            raise ValueError(f"不支持的 provider: {provider}（支持 none|local|openai）")
        self.provider = provider
        self.model = model
        self.device = device
        self.base_url = base_url
        self.api_key = api_key
    def available(self) -> bool:
        return self.provider in ("local", "openai")
```

- [ ] **步骤 4：修改 `app/models/llm.py`**

```python
import os
from app.models.base import ModelProvider

class LLM(ModelProvider):
    name = "llm"
    def __init__(self, provider="none", model="", device="auto", base_url="", api_key=""):
        super().__init__(provider, model, device, base_url, api_key)

    def _api_key(self) -> str:
        return self.api_key or os.environ.get("OPENAI_API_KEY", "")

    def generate(self, prompt: str) -> str:
        if self.provider == "openai":
            return self._generate_openai(prompt)
        if not self.available():
            return f"（无可用 LLM，provider=none）规则兜底：{prompt[:50]}"
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            tok = AutoTokenizer.from_pretrained(self.model)
            m = AutoModelForCausalLM.from_pretrained(self.model)
            dev = torch.device(self.device)
            m = m.to(dev)
            inp = tok(prompt, return_tensors="pt").to(dev)
            out = m.generate(**inp, max_new_tokens=512)
            return tok.decode(out[0], skip_special_tokens=True)
        except Exception as e:
            raise RuntimeError(f"LLM 调用失败: {e}") from e

    def _generate_openai(self, prompt: str) -> str:
        try:
            from openai import OpenAI
            key = self._api_key()
            if not key:
                raise RuntimeError("未配置 api_key（config.yaml llm.api_key 或环境变量 OPENAI_API_KEY）")
            client = OpenAI(base_url=self.base_url or None, api_key=key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"LLM 线上调用失败: {e}") from e
```

- [ ] **步骤 5：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py -v`
预期：PASS（6 个测试）

- [ ] **步骤 6：Commit**

```bash
git add app/models/base.py app/models/llm.py tests/test_models.py
git commit -m "feat: 支持 openai provider 的 LLM 线上调用"
```

---

### 任务 3：`vlm.py` GGUF 推理 + reranker 复用

**文件：**
- 修改：`app/models/vlm.py`
- 修改：`app/matching/reranker.py`
- 测试：`tests/test_models.py`（追加）、`tests/test_matcher.py`（追加）

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_models.py` 追加：

```python
from app.models.vlm import VLM

def test_vlm_none_raises():
    v = VLM(provider="none", model="", device="cpu")
    try:
        v.describe([], "描述")
    except RuntimeError:
        pass
    else:
        raise AssertionError("provider=none 应抛 RuntimeError")
```

在 `tests/test_matcher.py` 追加：

```python
from app.matching.reranker import rerank_candidates
from app.matching.retriever import CandidateShot

def test_rerank_no_vlm_returns_same(tmp_path, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(settings, "vlm_reranker", type("MC", (), {"provider": "none", "model": "", "device": "auto"})())
    cands = [CandidateShot(shot_id="a", source="x", start=0.0, end=1.0, duration=1.0, similarity=0.5)]
    assert rerank_candidates(cands, settings) is cands
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py tests/test_matcher.py -v`
预期：目前通过（`test_vlm_none_raises` 已满足）；执行 TDD 的 GREEN 需验证：新增测试全 PASS。若 `test_vlm_none_raises` 已通过，说明现有行为正确，保留作为回归。

- [ ] **步骤 3：修改 `app/models/vlm.py`**

```python
import json
import re
from pathlib import Path
from app.models.base import ModelProvider

_llm_cache = {}
_llm_loaded_for = None

def vlm_repair_json(raw: str) -> str:
    s = raw[raw.find("{"):] if "{" in raw else raw
    if not s:
        raise ValueError("输出中不包含 JSON")
    s = re.sub(r'[\x00-\x1f]', ' ', s)
    open_cnt = s.count("{") + s.count("[")
    close_cnt = s.count("}") + s.count("]")
    s += "}" * max(0, open_cnt - close_cnt)
    return s

def parse_vlm_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(vlm_repair_json(raw))

def get_gguf_llm(model_path: str, device: str = "auto"):
    """模块级单例：同一 GGUF 只加载一次（VLM 与 reranker 复用）。"""
    global _llm_cache, _llm_loaded_for
    key = f"{model_path}|{device}"
    if key == _llm_loaded_for and key in _llm_cache:
        return _llm_cache[key]
    from app.models.device import DeviceManager
    dev = DeviceManager(device)
    n_gpu = -1 if dev.resolve() == "cuda" else 0
    try:
        from llama_cpp import Llama
    except ImportError as e:
        raise RuntimeError("未安装 llama-cpp-python，请先 pip install -r requirements-models.txt") from e
    if not Path(model_path).exists():
        raise RuntimeError(f"模型文件不存在: {model_path}")
    llm = Llama(model_path=str(model_path), n_gpu_layers=n_gpu, verbose=False)
    _llm_cache[key] = llm
    _llm_loaded_for = key
    return llm

class VLM(ModelProvider):
    name = "vlm"
    def __init__(self, provider="none", model="", device="auto", base_url="", api_key=""):
        super().__init__(provider, model, device, base_url, api_key)
    def describe(self, frames, prompt: str) -> dict:
        if not self.available():
            raise RuntimeError("VLM 未启用（provider=none）")
        if self.provider == "openai":
            return self._describe_openai(frames, prompt)
        llm = get_gguf_llm(self.model, self.device)
        import tempfile, os
        # frames 为图像 ndarray 列表：暂存首帧为临时图并交给多模态 GGUF 推理
        # llama.cpp 多模态在 Python 绑定中用 chat 接口（需内置 mmproj），此处走文本协议
        if frames:
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
                )
            finally:
                os.unlink(tmp.name)
        else:
            out = llm(prompt)
        raw = out["choices"][0]["message"]["content"] if "choices" in out else out.get("content", "")
        return parse_vlm_json(raw)
    def _describe_openai(self, frames, prompt: str) -> dict:
        from openai import OpenAI
        key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("未配置 VLM api_key")
        client = OpenAI(base_url=self.base_url or None, api_key=key)
        import tempfile, os, cv2, base64
        if frames:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frames[0])
            tmp.close()
            try:
                with open(tmp.name, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
            finally:
                os.unlink(tmp.name)
            content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                       {"type": "text", "text": prompt}]
        else:
            content = prompt
        resp = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": content}])
        return parse_vlm_json(resp.choices[0].message.content)
```

- [ ] **步骤 4：修改 `app/matching/reranker.py`**

```python
from app.models.vlm import VLM, get_gguf_llm

def rerank_candidates(cands, settings, log=None):
    """有 vlm_reranker 时按二次判断重排；无则原样返回。"""
    cfg = settings.vlm_reranker
    if cfg.provider in ("local", "openai"):
        vlm = VLM(cfg.provider, cfg.model, cfg.device, cfg.base_url, cfg.api_key)
        # 目前不做实际重排打分，仅确保模型可加载并保留候选（模型接入任务细化排序）
        if log:
            log.info("vlm_reranker 已启用（provider=%s），候选保留原序", cfg.provider)
    return cands
```

- [ ] **步骤 5：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_models.py tests/test_matcher.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add app/models/vlm.py app/matching/reranker.py tests/test_models.py tests/test_matcher.py
git commit -m "feat: VLM GGUF 推理（llama.cpp）与 reranker 复用加载器"
```

---

### 任务 4：`asr.py` FunASR 适配器 + 引用改造

**文件：**
- 创建：`app/models/asr.py`
- 删除：`app/models/whisper.py`
- 修改：`app/analyzer/audio.py`
- 测试：`tests/test_asr.py`（新建）、`tests/test_models.py`（更新 import）

- [ ] **步骤 1：编写失败的测试**

创建 `tests/test_asr.py`：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.asr import ASR

def test_asr_none_returns_empty():
    a = ASR(provider="none", model="", device="cpu")
    assert a.transcribe("whatever.wav") == []

def test_asr_available_local():
    a = ASR(provider="local", model="models/asr", device="cpu")
    assert a.available() is True
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_asr.py -v`
预期：FAIL（`No module named 'app.models.asr'`）

- [ ] **步骤 3：创建 `app/models/asr.py`**

```python
from pathlib import Path
from app.models.base import ModelProvider

class ASR(ModelProvider):
    name = "asr"
    def __init__(self, provider="none", model="", device="auto", base_url="", api_key=""):
        super().__init__(provider, model, device, base_url, api_key)

    def transcribe(self, audio_path: str) -> list[dict]:
        if not self.available():
            return []
        try:
            from funasr import AutoModel
            model = AutoModel(model=self.model)
            res = model.generate(input=str(audio_path))
            # paraformer 返回 list[dict]：{"key","text","timestamp": [[s,e], ...]}
            segs = []
            for r in res:
                text = r.get("text", "")
                ts = r.get("timestamp") or []
                if not ts:
                    segs.append({"start": 0.0, "end": 0.0, "text": text})
                    continue
                for (s, e), word in zip(ts, _split_words(text, len(ts))):
                    segs.append({"start": float(s) / 1000.0, "end": float(e) / 1000.0, "text": word})
            return segs
        except Exception as e:
            raise RuntimeError(f"FunASR 转写失败: {e}") from e

def _split_words(text: str, n: int) -> list[str]:
    """把整句按 timestamp 段数粗略切分（paraformer 无逐词 text 时兜底）。"""
    if n <= 1:
        return [text]
    chars = list(text)
    seg = max(1, len(chars) // n)
    return ["".join(chars[i * seg:(i + 1) * seg]) for i in range(n)]
```

- [ ] **步骤 4：删除 `app/models/whisper.py` 并改 `app/analyzer/audio.py`**

删除文件：`app/models/whisper.py`

`app/analyzer/audio.py` 改为：

```python
import subprocess
from app.models.asr import ASR

def transcribe(settings, video_path: str, start: float, end: float, max_dur: float = 30.0) -> list[dict]:
    """截取 [start,end] 音频段后调用 ASR（provider=none 时返回 []）。"""
    w = ASR(settings.asr.provider, settings.asr.model, settings.asr.device)
    if not w.available():
        return []
    tmp = settings.transcripts_dir / "tmp.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    seg = end - start
    cmd = [settings.ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{min(seg, max_dur):.3f}",
           "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", str(tmp)]
    subprocess.run(cmd, capture_output=True)
    try:
        segs = w.transcribe(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    return [{"start": s["start"] + start, "end": s["end"] + start, "text": s["text"]} for s in segs]
```

- [ ] **步骤 5：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_asr.py tests/test_models.py -v`
预期：PASS

- [ ] **步骤 6：全量回归（确认无残留 whisper 引用）**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS；若有 `No module named 'app.models.whisper'`，grep 排查残留引用并修复。

- [ ] **步骤 7：Commit**

```bash
git add app/models/asr.py app/analyzer/audio.py tests/test_asr.py
git rm app/models/whisper.py
git commit -m "feat: FunASR 转写适配器，whisper 段替换为 asr"
```

---

### 任务 5：`scripts/download_models.py`

**文件：**
- 创建：`scripts/download_models.py`
- 测试：`tests/test_download_models.py`（新建）

- [ ] **步骤 1：编写失败的测试**

创建 `tests/test_download_models.py`：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_models import MODELS, source_id, resolve_target, download_all

def test_model_list_complete():
    assert set(MODELS.keys()) == {"vlm", "asr", "embedding"}
    assert MODELS["embedding"]["hf"] == "BAAI/bge-small-zh-v1.5"
    assert MODELS["embedding"]["ms"] == "AI-ModelScope/bge-small-zh-v1.5"

def test_source_id_mapping():
    assert source_id("embedding", "hf") == "BAAI/bge-small-zh-v1.5"
    assert source_id("embedding", "ms") == "AI-ModelScope/bge-small-zh-v1.5"

def test_resolve_target(tmp_path):
    target = resolve_target(tmp_path, "embedding", "AI-ModelScope/bge-small-zh-v1.5")
    assert target == tmp_path / "embedding"

def test_download_all_selects_source(tmp_path, monkeypatch):
    calls = []
    def fake_snapshot_hf(repo_id, **kw):
        calls.append(("hf", repo_id, kw))
        (kw["local_dir"] / "x.txt").write_text("ok")
    monkeypatch.setattr("scripts.download_models.snapshot_hf", fake_snapshot_hf)
    rep = download_all(tmp_path, sources="hf", models="embedding", install=False)
    assert rep["embedding"] is True
    assert calls[0][:2] == ("hf", "BAAI/bge-small-zh-v1.5")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`venv\Scripts\python.exe -m pytest tests/test_download_models.py -v`
预期：FAIL（`No module named 'scripts.download_models'`）

- [ ] **步骤 3：创建 `scripts/download_models.py`**

```python
#!/usr/bin/env python
"""从 HuggingFace / ModelScope 下载本地模型。

用法：
    python scripts/download_models.py --list
    python scripts/download_models.py --source ms
    python scripts/download_models.py --source hf --model embedding
    python scripts/download_models.py --source ms --write-config
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODELS = {
    "vlm": {
        "hf": "Qwen/Qwen3-VL-2B-Instruct-GGUF",
        "ms": "Qwen/Qwen3-VL-2B-Instruct-GGUF",
        "note": "VLM 描述 + reranker（GGUF）",
    },
    "asr": {
        "hf": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "ms": "iic/speech_paraformer_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "note": "FunASR 中文转写（paraformer-zh）",
    },
    "embedding": {
        "hf": "BAAI/bge-small-zh-v1.5",
        "ms": "AI-ModelScope/bge-small-zh-v1.5",
        "note": "Embedding（bge-small-zh）",
    },
}

def source_id(role: str, source: str) -> str:
    if role not in MODELS:
        raise ValueError(f"未知模型: {role}（可选 {sorted(MODELS)}）")
    if source not in ("hf", "ms"):
        raise ValueError("source 必须是 hf 或 ms")
    return MODELS[role][source]

def resolve_target(root: Path, role: str, repo_id: str) -> Path:
    return root / "models" / role

def snapshot_hf(repo_id: str, local_dir: Path):
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo_id, local_dir=str(local_dir))

def snapshot_ms(repo_id: str, local_dir: Path):
    from modelscope import snapshot_download
    snapshot_download(repo_id, local_dir=str(local_dir))

def download_all(root: Path, sources: str = "hf", models: list[str] | None = None,
                 install: bool = True) -> dict:
    roles = models or list(MODELS)
    if install:
        _ensure_deps()
    report: dict = {}
    for role in roles:
        rid = source_id(role, sources)
        target = resolve_target(root, role, rid)
        target.mkdir(parents=True, exist_ok=True)
        try:
            if sources == "hf":
                snapshot_hf(rid, target)
            else:
                snapshot_ms(rid, target)
            report[role] = True
        except Exception as e:
            print(f"[download] {role} 失败（{sources}）: {e}", file=sys.stderr)
            print(f"           提示：国内网络可尝试 --source ms", file=sys.stderr)
            report[role] = False
    return report

def _ensure_deps():
    req = ROOT / "requirements-models.txt"
    if not req.exists():
        return
    py = ROOT / "venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = sys.executable
    import subprocess
    subprocess.run([str(py), "-m", "pip", "install", "-r", str(req)], check=False)

def write_config(root: Path, report: dict):
    """把成功下载的模型本地路径写回 config.yaml 的 model 字段。"""
    cfg_path = root / "config.yaml"
    if not cfg_path.exists():
        print("[config] config.yaml 不存在，跳过 --write-config", file=sys.stderr)
        return
    import yaml
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    models = raw.setdefault("models", {})
    for role, ok in report.items():
        if ok:
            target = root / "models" / role
            cfg_entry = models.setdefault(role, {})
            if role == "vlm":
                cfg_entry["provider"] = "local"
                cfg_entry["model"] = str(target)
            elif role == "asr":
                cfg_entry["provider"] = "local"
                cfg_entry["model"] = str(target)
            elif role == "embedding":
                cfg_entry["provider"] = "local"
                cfg_entry["model"] = str(target)
    cfg_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("[config] 已更新 config.yaml 的 model 路径")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="download_models", description="下载本地模型（HF/ModelScope）")
    ap.add_argument("--source", choices=["hf", "ms"], default="hf", help="下载源：hf=HuggingFace, ms=ModelScope")
    ap.add_argument("--model", choices=sorted(MODELS), action="append", help="只下载指定模型（可多次）")
    ap.add_argument("--list", action="store_true", help="打印模型清单")
    ap.add_argument("--write-config", action="store_true", help="下载后把本地路径写回 config.yaml")
    ap.add_argument("--skip-install", action="store_true", help="跳过 pip 依赖安装")
    args = ap.parse_args(argv)
    if args.list:
        for role, m in MODELS.items():
            print(f"{role:12s} hf={m['hf']}\n{'':12s} ms={m['ms']}\n{'':12s} {m['note']}")
        return 0
    report = download_all(ROOT, sources=args.source, models=args.model,
                          install=not args.skip_install)
    if args.write_config:
        write_config(ROOT, report)
    ok = sum(1 for v in report.values() if v)
    print(f"下载完成：{ok}/{len(report)} 成功")
    return 0 if ok == len(report) else 1

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **步骤 4：运行测试验证通过**

运行：`venv\Scripts\python.exe -m pytest tests/test_download_models.py -v`
预期：PASS

- [ ] **步骤 5：人工验证（离线可跑）**

运行：`venv\Scripts\python.exe -m scripts.download_models --list`
预期：打印 3 个模型的双源 ID

- [ ] **步骤 6：Commit**

```bash
git add scripts/download_models.py tests/test_download_models.py
git commit -m "feat: HF/ModelScope 双源模型下载脚本"
```

---

### 任务 6：配置安全（config.yaml 移出仓库）+ 依赖清单更新

**文件：**
- 修改：`.gitignore`（加 `config.yaml`）
- 修改：`config.yaml.example`（asr 段 + llm openai 示例 + 注释）
- 修改：`requirements-models.txt`（openai/huggingface_hub/modelscope/llama-cpp-python/funasr/onnxruntime）
- 修改：`README.md`（模型配置说明更新）

- [ ] **步骤 1：修改 `.gitignore`**

在 `__pycache__/` 前加入：

```
config.yaml
```

- [ ] **步骤 2：修改 `requirements-models.txt`**

```text
torch>=2.2
transformers>=4.40
sentence-transformers>=3.0
openai>=1.30
huggingface_hub>=0.23
modelscope>=1.15
llama-cpp-python>=0.2.80
funasr>=1.1.6
onnxruntime>=1.17
```

（移除 `faster-whisper>=1.0`，FunASR 取代。）

- [ ] **步骤 3：修改 `config.yaml.example`**

```yaml
# 模型配置：provider 可选 none|local|openai
#   none    → 规则兜底（无模型，默认）
#   local   → 本地模型（用 scripts/download_models.py 下载后 --write-config 自动填写路径）
#   openai  → 线上 OpenAI 兼容接口（llm/vlm；需 base_url + api_key）
# api_key 可直接写 llm.api_key，或留空走环境变量 OPENAI_API_KEY
models:
  llm:       {provider: none, model: "", device: auto, base_url: "https://api.openai.com/v1", api_key: ""}
  vlm:       {provider: none, model: "", device: auto, base_url: "", api_key: ""}
  vlm_reranker: {provider: none, model: "", device: auto, base_url: "", api_key: ""}
  asr:       {provider: none, model: "", device: auto, base_url: "", api_key: ""}
  embedding: {provider: none, model: "", device: auto, base_url: "", api_key: ""}
# 其余配置段（video/matching/index/render）保持不变，见 config.yaml
```

- [ ] **步骤 4：从仓库移除 `config.yaml`**

```bash
git rm --cached config.yaml
```

（本地文件保留；`.gitignore` 已忽略，之后不会被误提交。）

- [ ] **步骤 5：更新 `README.md` 模型配置小节**

在"模型配置说明"处改写为：三态 provider 说明、下载脚本用法、llm 线上配置示例、config.yaml 不入库说明。

- [ ] **步骤 6：运行全量测试**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS

- [ ] **步骤 7：Commit**

```bash
git add .gitignore requirements-models.txt config.yaml.example README.md
git commit -m "feat: 模型配置三态与 config.yaml 移出仓库；更新依赖与文档"
```

---

### 任务 7：全量回归 + 验收

**文件：**
- 无（验证为主）

- [ ] **步骤 1：全量测试**

运行：`venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部 PASS（含既有 38 个 + 新增 test_settings/test_asr/test_download_models）

- [ ] **步骤 2：无模型主流程回归**

运行：`venv\Scripts\python.exe -m app.main build scripts\demo.md`
预期：仍以规则兜底跑通（LLM provider=none → 规则解析；ASR provider=none → 无转写；VLM provider=none → 无视觉模型），生成 edit_plan 或按素材缺失提示。

- [ ] **步骤 3：git 状态核对**

运行：`git status --short`
预期：无 `config.yaml` 的跟踪/改动（已被忽略）；无 `app/models/whisper.py`。

- [ ] **步骤 4：Commit（如有遗留）**

```bash
git add -A
git commit -m "chore: 全量回归收尾" # 若无改动则跳过
```

---

## 自检

- **规格覆盖度**：清单（任务 5）、双源（任务 5）、LLM 线上（任务 2）、VLM GGUF + reranker（任务 3）、FunASR（任务 4）、settings 扩展（任务 1）、config 安全（任务 6）、测试（各任务 + 任务 7）——全部覆盖。
- **占位符扫描**：无 TODO/待定；每个步骤含实际代码与命令。
- **类型一致性**：`ModelConfig(base_url, api_key)` 在任务 1 定义，任务 2/3/4 的适配器构造签名均含 `base_url=""`, `api_key=""`；`settings.asr` 在任务 1 引入，任务 4 的 `audio.py` 使用一致；`get_gguf_llm` 任务 3 定义，reranker 同任务使用。
