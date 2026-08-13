from app.models.device import DeviceManager
from app.models.base import ModelProvider
from app.models.llm import LLM
from app.models.vlm import vlm_repair_json
from app.models.embedding import Embedder
from app.models.vlm import VLM

def test_device_resolve():
    d = DeviceManager("auto")
    assert d.resolve() in ("cuda", "cpu", "rocm")

def test_vlm_repair_json_fixes_braces():
    bad = '{"a": 1, "b": [2, 3'
    assert "b" in vlm_repair_json(bad)

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
