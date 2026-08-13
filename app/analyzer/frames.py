import subprocess
from pathlib import Path

import cv2
import numpy as np


def sample_times(start: float, end: float, frames_min=3, frames_max=8) -> list[float]:
    dur = max(end - start, 0.1)
    n = max(frames_min, min(frames_max, int(dur)))
    n = min(n, max(int(dur * 2), 1))
    if dur <= frames_min:
        return [start + dur / 2]
    return [start + dur * i / n for i in range(n)]


def extract_frame(video_path: str, t: float, ffmpeg: str, out: Path,
                  width: int = 320) -> np.ndarray | None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-ss", f"{t:.3f}", "-i", video_path,
           "-frames:v", "1", "-vf", f"scale={width}:-2", str(out)]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not out.exists():
        return None
    img = cv2.imread(str(out))
    return img


def save_thumbnails(frames: list[tuple[float, np.ndarray | None]], shot_id: str,
                    thumb_dir: Path) -> list[Path]:
    thumb_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, (t, img) in enumerate(frames):
        if img is None:
            continue
        p = thumb_dir / f"{shot_id}_{i:02d}.jpg"
        cv2.imwrite(str(p), img)
        saved.append(p)
    return saved
