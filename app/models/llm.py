from app.models.base import ModelProvider

class LLM(ModelProvider):
    name = "llm"
    def __init__(self, provider="none", model="", device="auto"):
        super().__init__(provider, model, device)

    def generate(self, prompt: str) -> str:
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
