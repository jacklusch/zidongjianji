import subprocess
from app.models.asr import ASR

def transcribe(settings, video_path: str, start: float, end: float, max_dur: float = 30.0) -> list[dict]:
    """截取 [start,end] 音频段后调用 ASR（provider=none 时返回 []）。"""
    w = ASR(settings.asr.provider, settings.asr.model, settings.asr.device)
    if not w.available():
        return []
    tmp = settings.transcripts_dir / "tmp.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    seg = end - start
    cmd = [settings.ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{min(seg, max_dur):.3f}",
           "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", str(tmp)]
    subprocess.run(cmd, capture_output=True)
    try:
        segs = w.transcribe(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    return [{"start": s["start"] + start, "end": s["end"] + start, "text": s["text"]} for s in segs]
