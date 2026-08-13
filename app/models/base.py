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
