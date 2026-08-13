import json
from pathlib import Path
from app.utils.process import run

class MissingMediaError(FileNotFoundError):
    pass

def ffprobe_json(path, ffprobe: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise MissingMediaError(f"素材不存在: {p}")
    try:
        return json.loads(run([ffprobe, "-v", "error", "-print_format", "json",
                               "-show_format", "-show_streams", str(p)]).stdout)
    except Exception as e:
        raise MissingMediaError(f"FFprobe 解析失败 {p}: {e}") from e