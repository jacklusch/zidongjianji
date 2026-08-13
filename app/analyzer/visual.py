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


_VLM_PROMPT = (
    "请分析这张视频画面，只输出一个 JSON 对象（不要输出其他内容），字段："
    "description(一句话中文描述画面), objects(主要物体中文列表), "
    "actions(正在发生的动作中文列表), environment(环境/场景中文), "
    "shot_type(镜头类型: close/medium/wide), camera_motion(运镜: static/pan/tilt/zoom), "
    "people_count(人数整数)。"
)


def vlm_visual_analysis(frames, vlm) -> VisualAnalysis:
    """用 VLM 分析画面；解析失败或异常时降级为 fallback。"""
    try:
        data = vlm.describe(frames, _VLM_PROMPT)
        if not isinstance(data, dict):
            raise ValueError("VLM 返回非字典")
        q = float(data.get("visual_quality", 0.5) or 0.5)
        return VisualAnalysis(
            description=str(data.get("description", "") or ""),
            objects=_as_str_list(data.get("objects")),
            actions=_as_str_list(data.get("actions")),
            environment=str(data.get("environment", "") or ""),
            shot_type=str(data.get("shot_type", "medium") or "medium"),
            camera_motion=str(data.get("camera_motion", "static") or "static"),
            people_count=int(data.get("people_count", 0) or 0),
            visual_quality=float(min(1.0, max(0.0, q))),
        )
    except Exception:
        return fallback_visual_analysis(frames)


def _as_str_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v]
    return []
