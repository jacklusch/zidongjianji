class DeviceManager:
    def __init__(self, device: str = "auto"):
        self.device = device

    def resolve(self) -> str:
        if self.device in ("cuda", "rocm"):
            return self.device
        if self.device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except Exception:
                pass
        return "cpu"
