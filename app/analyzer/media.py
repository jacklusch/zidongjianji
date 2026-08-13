from dataclasses import dataclass
from pathlib import Path
from app.editors.ffmpeg import ffprobe_json, MissingMediaError

@dataclass
class MediaInfo:
    path: Path
    filename: str
    extension: str
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    audio: bool
    size: int

def probe_media(path, ffprobe: str = "ffprobe") -> MediaInfo:
    p = Path(path)
    data = ffprobe_json(p, ffprobe)
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur_s = float(data.get("format", {}).get("duration") or v.get("duration") or 0.0)
    fps_s = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
    num, den = fps_s.split("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    return MediaInfo(
        path=p, filename=p.name, extension=p.suffix.lower(),
        duration=dur_s, width=int(v.get("width", 0)), height=int(v.get("height", 0)),
        fps=fps, codec=v.get("codec_name", ""), audio=a is not None,
        size=p.stat().st_size,
    )