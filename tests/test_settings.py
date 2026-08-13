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
