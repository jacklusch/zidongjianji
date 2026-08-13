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


_RISK_KEYWORDS = ("刀", "血", "裸露", "危险", "违规", "烟雾", "火", "碰撞", "挤压")


def vlm_visual_analysis(frames, vlm) -> VisualAnalysis:
    """逐帧调用 VLM 并聚合结果；单帧失败跳过，全失败降级 fallback。

    安全/异常字段从严（任一带风险词即保留）、体验数值取均值、描述去重拼接。
    """
    results = []
    for f in frames:
        try:
            data = vlm.describe([f], _VLM_PROMPT)
            if isinstance(data, dict):
                results.append(data)
        except Exception:
            continue
    if not results:
        return fallback_visual_analysis(frames)

    all_objects, all_actions = [], []
    environments = []
    descriptions = []
    people = 0
    q_sum = 0.0
    shot_types, cams = [], []
    needs_review = False
    for d in results:
        objects = _as_str_list(d.get("objects"))
        actions = _as_str_list(d.get("actions"))
        for o in objects:
            if o not in all_objects:
                all_objects.append(o)
        for a in actions:
            if a not in all_actions:
                all_actions.append(a)
        env = str(d.get("environment", "") or "")
        if env and env not in environments:
            environments.append(env)
        desc = str(d.get("description", "") or "")
        if desc and desc not in descriptions:
            descriptions.append(desc)
        people = max(people, int(d.get("people_count", 0) or 0))
        try:
            q_sum += float(d.get("visual_quality", 0.5) or 0.5)
        except (TypeError, ValueError):
            q_sum += 0.5
        shot_types.append(str(d.get("shot_type", "medium") or "medium"))
        cams.append(str(d.get("camera_motion", "static") or "static"))
        if "无法判定" in desc or "未知" in desc:
            needs_review = True

    risk_objects = [o for o in all_objects if any(k in o for k in _RISK_KEYWORDS)]
    merged_objects = risk_objects + [o for o in all_objects if o not in risk_objects]
    desc_text = " ".join(descriptions)
    if needs_review:
        desc_text += "（需人工复核）"
    return VisualAnalysis(
        description=desc_text,
        objects=merged_objects,
        actions=all_actions,
        environment=", ".join(environments),
        shot_type=_most_common(shot_types) or "medium",
        camera_motion=_most_common(cams) or "static",
        people_count=people,
        visual_quality=float(min(1.0, max(0.0, q_sum / len(results)))),
    )


def _most_common(items: list[str]) -> str | None:
    from collections import Counter
    if not items:
        return None
    return Counter(items).most_common(1)[0][0]


def _as_str_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v]
    return []
