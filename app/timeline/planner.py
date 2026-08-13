from dataclasses import asdict
from app.timeline.schema import TimelineItem

def build_timeline(segments, matches, project: str = "demo",
                   source_script: str = "scripts/script.md") -> tuple[list[TimelineItem], list[dict], list[str]]:
    """matches: list[MatchResult]（与 segments 按下标对应，None 表示缺失）。"""
    items: list[TimelineItem] = []
    missing: list[dict] = []
    warnings: list[str] = []
    used: dict[str, int] = {}
    for i, seg in enumerate(segments):
        s = asdict(seg) if not isinstance(seg, dict) else seg
        m = matches[i] if i < len(matches) else None
        if m is None:
            missing.append({"script_id": s["id"], "script_text": s["script_text"],
                            "reason": "素材库中没有找到符合要求的镜头"})
            continue
        count = used.get(m.selected_shot, 0)
        reused = count > 0
        if reuse_would_violate(m, count):
            missing.append({"script_id": s["id"], "script_text": s["script_text"],
                            "reason": "镜头被重复使用，已拒绝"})
            continue
        used[m.selected_shot] = count + 1
        m.segment_id = s["id"]
        items.append(TimelineItem(
            script_id=s["id"], source=m.source, in_point=m.in_point, out_point=m.out_point,
            duration=m.out_point - m.in_point, reason=m.reason, confidence=m.confidence,
            reused=reused))
        if reused:
            warnings.append(f"镜头 {m.selected_shot} 复用（仅因素材不足允许）")
    return items, missing, warnings

def reuse_would_violate(match, used_count: int) -> bool:
    # 一个镜头最多复用 1 次，超出视为违规
    return used_count >= 2
