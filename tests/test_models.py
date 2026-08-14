from app.models.device import DeviceManager
from app.models.base import ModelProvider
from app.models.llm import LLM
from app.models.vlm import vlm_repair_json, _resolve_gguf_paths, get_gguf_llm
from app.models.embedding import Embedder
from app.models.vlm import VLM

def test_device_resolve():
    d = DeviceManager("auto")
    assert d.resolve() in ("cuda", "cpu", "rocm")

def test_vlm_repair_json_fixes_braces():
    bad = '{"a": 1, "b": [2, 3'
    assert "b" in vlm_repair_json(bad)

def test_parse_vlm_json_tolerates_trailing_text():
    from app.models.vlm import parse_vlm_json
    raw = '好的，这是分析结果：{"a": 1, "b": [2, 3]} 以上是描述。'
    data = parse_vlm_json(raw)
    assert data["a"] == 1 and data["b"] == [2, 3]

def test_llm_none_generates():
    llm = LLM(provider="none", model="", device="cpu")
    text = llm.generate("讲个工厂故事")
    assert isinstance(text, str) and len(text) > 0

def test_embedder_none_returns_none():
    emb = Embedder(provider="none", model="", device="cpu")
    assert emb.embed(["x"]) is None

def test_provider_openai_available():
    p = ModelProvider(provider="openai", model="m", device="cpu", base_url="u", api_key="k")
    assert p.available() is True

def test_vlm_none_raises():
    v = VLM(provider="none", model="", device="cpu")
    try:
        v.describe([], "描述")
    except RuntimeError:
        pass
    else:
        raise AssertionError("provider=none 应抛 RuntimeError")

def test_vlm_openai_missing_key_raises(monkeypatch):
    import sys, types
    fake = types.ModuleType("openai")
    fake.OpenAI = object
    monkeypatch.setitem(sys.modules, "openai", fake)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v = VLM(provider="openai", model="m", device="cpu", api_key="")
    try:
        v.describe([], "描述")
    except RuntimeError as e:
        assert "api_key" in str(e)
    else:
        raise AssertionError("openai provider 缺 api_key 应抛 RuntimeError")

def test_vlm_local_deterministic_params(monkeypatch, tmp_path):
    import sys, types
    (tmp_path / "x.gguf").write_bytes(b"x")
    calls = {}
    class FakeLlama:
        def __init__(self, **kw):
            pass
        def __call__(self, prompt, **kw):
            calls["call"] = (prompt, kw)
            return {"choices": [{"text": '{"description": "x", "objects": [], "actions": [], "environment": "", "shot_type": "medium", "camera_motion": "static", "people_count": 0}'}]}
        def create_chat_completion(self, **kw):
            calls["chat"] = kw
            return {"choices": [{"message": {"content": '{"description": "x", "objects": [], "actions": [], "environment": "", "shot_type": "medium", "camera_motion": "static", "people_count": 0}'}}]}
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=FakeLlama))
    from app.models.vlm import VLM
    v = VLM("local", str(tmp_path / "x.gguf"), "cpu")
    # 无 frames → 走 llm(prompt) 文本路径
    v.describe([], "分析")
    assert calls["call"] is not None  # 文本路径被调用
    assert calls["call"][1].get("temperature") == 0.0  # 确定性核心：零温度
    assert calls["call"][1].get("top_p") == 1.0
    assert calls["call"][1].get("max_tokens") == 700

def test_vlm_local_multimodal_deterministic_params(monkeypatch, tmp_path):
    import sys, types
    (tmp_path / "x.gguf").write_bytes(b"x")
    (tmp_path / "mmproj-x-f16.gguf").write_bytes(b"m")
    calls = {}
    class FakeLlama:
        def __init__(self, **kw):
            pass
        def __call__(self, prompt, **kw):
            calls["call"] = (prompt, kw)
            return {"choices": [{"text": '{"description": "x", "objects": [], "actions": [], "environment": "", "shot_type": "medium", "camera_motion": "static", "people_count": 0}'}]}
        def create_chat_completion(self, **kw):
            calls["chat"] = kw
            return {"choices": [{"message": {"content": '{"description": "x", "objects": [], "actions": [], "environment": "", "shot_type": "medium", "camera_motion": "static", "people_count": 0}'}}]}
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=FakeLlama))
    import numpy as np
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    from app.models.vlm import VLM
    v = VLM("local", str(tmp_path / "x.gguf"), "cpu")
    # 有 frames 且有 mmproj → 走 create_chat_completion 多模态路径
    v.describe([frame], "分析")
    assert calls["chat"] is not None  # 多模态路径被调用
    assert calls["chat"].get("temperature") == 0.0
    assert calls["chat"].get("top_p") == 1.0
    assert calls["chat"].get("max_tokens") == 700

def test_vlm_local_text_completion(monkeypatch):
    class FakeLLM:
        def __call__(self, prompt, **kw):
            return {"choices": [{"text": '{"a": 1}'}]}
    monkeypatch.setattr("app.models.vlm.get_gguf_llm",
                        lambda model_path, device: (FakeLLM(), None))
    v = VLM(provider="local", model="models/vlm/x.gguf", device="cpu")
    assert v.describe([], "prompt") == {"a": 1}

def test_vlm_local_frames_without_mmproj_falls_back_to_text(monkeypatch):
    class FakeLLM:
        def __call__(self, prompt, **kw):
            return {"choices": [{"text": '{"ok": true}'}]}
    monkeypatch.setattr("app.models.vlm.get_gguf_llm",
                        lambda model_path, device: (FakeLLM(), None))
    v = VLM(provider="local", model="models/vlm/x.gguf", device="cpu")
    assert v.describe([object()], "prompt") == {"ok": True}

def test_resolve_gguf_paths_directory_prefers_q4_and_excludes_mmproj(tmp_path):
    (tmp_path / "model-mix-Q4_K_M.gguf").write_bytes(b"b" * 10)
    (tmp_path / "model-fp16.gguf").write_bytes(b"a" * 500)
    (tmp_path / "mmproj-model-f16.gguf").write_bytes(b"m")
    main, mm = _resolve_gguf_paths(str(tmp_path))
    assert main.name == "model-mix-Q4_K_M.gguf"
    assert mm is not None and mm.name == "mmproj-model-f16.gguf"

def test_resolve_gguf_paths_prefers_matching_mmproj(tmp_path):
    (tmp_path / "Qwen3VL-4B-Instruct-Q4_K_M.gguf").write_bytes(b"b" * 10)
    (tmp_path / "mmproj-Qwen3VL-2B-Instruct-F16.gguf").write_bytes(b"2")
    (tmp_path / "mmproj-Qwen3VL-4B-Instruct-F16.gguf").write_bytes(b"4")
    main, mm = _resolve_gguf_paths(str(tmp_path))
    assert main.name == "Qwen3VL-4B-Instruct-Q4_K_M.gguf"
    assert mm is not None and "4B" in mm.name

def test_resolve_gguf_paths_single_file_uses_it(tmp_path):
    (tmp_path / "x.gguf").write_bytes(b"x")
    main, mm = _resolve_gguf_paths(str(tmp_path / "x.gguf"))
    assert main.name == "x.gguf"
    assert mm is None

def test_gguf_cache_multientry(tmp_path, monkeypatch):
    import sys, types
    (tmp_path / "model-q4.gguf").write_bytes(b"x")
    calls = []
    class FakeLlama:
        def __init__(self, **kw):
            calls.append(kw)
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=FakeLlama))
    mpath = str(tmp_path)
    _ = get_gguf_llm(mpath, "cpu")
    _ = get_gguf_llm(mpath, "cpu")
    assert len(calls) == 1
    llm2, _ = get_gguf_llm(mpath, "auto")
    assert len(calls) == 2
    assert llm2 is not None

def test_llm_local_auto_device_no_crash(monkeypatch):
    # 无 torch CUDA 时 torch.device("cpu") 正常
    from app.models.llm import LLM
    monkeypatch.setattr("app.models.device.DeviceManager.resolve", lambda self: "cpu")
    llm = LLM("local", "m", "auto")
    assert llm.device == "auto"  # 构造不崩


def test_llm_local_generate_uses_resolved_device(monkeypatch):
    import sys, types
    calls = {}
    class FakeTensor:
        def to(self, d):
            return self
    class FakeBatch(dict):
        def to(self, d):
            return self
    class FakeM:
        def to(self, d):
            calls["device"] = d
            return self
        def generate(self, **kw):
            return [FakeTensor()]
    class FakeTok:
        @staticmethod
        def from_pretrained(m):
            calls["tok"] = m
            return FakeTok()
        def __call__(self, prompt, return_tensors="pt"):
            return FakeBatch(input_ids=FakeTensor())
        def decode(self, out, skip_special_tokens=True):
            return "ok"
    class FakeTransformers:
        AutoModelForCausalLM = type("AM", (), {"from_pretrained": staticmethod(lambda m: FakeM())})
        AutoTokenizer = FakeTok
    monkeypatch.setitem(sys.modules, "transformers", FakeTransformers)
    monkeypatch.setattr("app.models.device.DeviceManager.resolve", lambda self: "cpu")
    from app.models.llm import LLM
    out = LLM(provider="local", model="m", device="auto").generate("hi")
    assert out == "ok"
    assert str(calls["device"]) == "cpu"


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
    assert calls["messages"][0]["content"] == "讲个故事"
