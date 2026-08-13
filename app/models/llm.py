import os
from app.models.base import ModelProvider

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

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
            if OpenAI is None:
                raise RuntimeError("未安装 openai SDK（pip install openai）")
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
