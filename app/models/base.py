class ModelProvider:
    name = "base"
    def __init__(self, provider: str, model: str, device: str):
        if provider not in ("none", "local"):
            raise ValueError(f"不支持的 provider: {provider}（支持 none|local）")
        self.provider = provider
        self.model = model
        self.device = device
    def available(self) -> bool:
        return self.provider == "local"
