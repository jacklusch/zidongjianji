from dataclasses import dataclass
from pathlib import Path
import scenedetect
from scenedetect import SceneManager
from scenedetect.detectors import ContentDetector
from app.analyzer.media import SUPPORTED

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Shot:
    shot_id: str
    source: str       # 相对路径（正斜杠）
    start: float
    end: float
    duration: float


def is_image(path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXT


def detect_shots(path, scene_threshold: float = 0.35,
                 min_duration: float = 1.0, ffmpeg: str | None = None) -> list[Shot]:
    p = Path(path)
    if is_image(p):
        return [Shot(shot_id=f"{p.stem}_shot1", source=str(p).replace("\\", "/"),
                     start=0.0, end=3.0, duration=3.0)]
    video = scenedetect.open_video(str(p))
    mgr = SceneManager()
    mgr.add_detector(ContentDetector(threshold=scene_threshold))
    mgr.detect_scenes(video, show_progress=False)
    cuts = mgr.get_cut_list()
    times = [c.get_seconds() for c in cuts]
    scenes = mgr.get_scene_list()
    shots: list[Shot] = []
    if not scenes:
        scenes = [(times[0] if times else 0.0, video.duration.get_seconds())]
    for i, (st, en) in enumerate(scenes):
        s = st.get_seconds() if hasattr(st, "get_seconds") else float(st)
        e = en.get_seconds() if hasattr(en, "get_seconds") else float(en)
        if e - s < min_duration:
            continue
        shots.append(Shot(
            shot_id=f"{p.stem}_{i + 1:03d}",
            source=str(p).replace("\\", "/"),
            start=s, end=e, duration=e - s))
    if not shots:
        shots.append(Shot(shot_id=f"{p.stem}_001", source=str(p).replace("\\", "/"),
                          start=0.0, end=video.duration.get_seconds(),
                          duration=video.duration.get_seconds()))
    return shots