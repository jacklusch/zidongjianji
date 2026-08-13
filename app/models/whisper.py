from pathlib import Path
from app.models.base import ModelProvider

class Whisper(ModelProvider):
    name = "whisper"
    def __init__(self, provider="none", model="", device="auto"):
        super().__init__(provider, model, device)

    def transcribe(self, audio_path: str) -> list[dict]:
        if not self.available():
            return []
        try:
            from faster_whisper import WhisperModel
            from app.models.device import DeviceManager
            dev = DeviceManager(self.device)
            mode = "cuda" if dev.resolve() == "cuda" else "int8"
            wm = WhisperModel(self.model, device=mode, compute_type=mode)
            segs, _ = wm.transcribe(audio_path, word_timestamps=True)
            return [{"start": s.start, "end": s.end, "text": s.text.strip(),
                     "words": [{"start": w.start, "end": w.end, "word": w.word} for w in (s.words or [])]}
                    for s in segs]
        except Exception as e:
            raise RuntimeError(f"Whisper 失败: {e}") from e
