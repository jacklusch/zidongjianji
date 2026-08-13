from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class VisualAnalysis:
    description: str
    objects: list[str]
    actions: list[str]
    environment: str
    shot_type: str
    camera_motion: str
    people_count: int
    visual_quality: float


def _gray_hist_stats(img) -> tuple[float, float]:
    if img is None or img.size == 0:
        return 0.5, 0.5
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h = cv2.calcHist([g], [0], None, [64], [0, 256]).ravel()
    h = h / (h.sum() + 1e-6)
    brightness = float((np.arange(64) * h).sum() / 64.0)
    variance = float((np.abs(np.arange(64) - brightness * 64) * h).sum() / 64.0)
    return brightness, variance


def fallback_visual_analysis(frames) -> VisualAnalysis:
    brightnesses, variances = [], []
    for f in frames:
        if f is None:
            continue
        b, v = _gray_hist_stats(f)
        brightnesses.append(b)
        variances.append(v)
    avg_b = float(np.mean(brightnesses)) if brightnesses else 0.5
    avg_v = float(np.mean(variances)) if variances else 0.5
    q = float(min(1.0, max(0.1, 0.4 + avg_v)))
    return VisualAnalysis(
        description=f"视频镜头，画面亮度 {avg_b:.2f}",
        objects=[], actions=[], environment="",
        shot_type="medium", camera_motion="static",
        people_count=0, visual_quality=q)
