from app.models.device import DeviceManager
from app.models.llm import LLM
from app.models.vlm import vlm_repair_json
from app.models.embedding import Embedder

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
