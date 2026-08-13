import json
from pathlib import Path

def write_script_plan(segments, out_path: Path) -> Path:
    data = {"version": 1, "segments": [s.to_dict() for s in segments]}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
