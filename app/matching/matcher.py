from dataclasses import dataclass

@dataclass
class MatchResult:
    segment_id: int
    selected_shot: str
    source: str
    in_point: float
    out_point: float
    duration: float
    score: float
    reason: str
    confidence: float

_DUR_W = 0.4

def _blend(sim: float, quality: float, dur: float, target_dur: float) -> float:
    dur_score = max(0.0, 1.0 - abs(dur - target_dur) / max(target_dur, 1.0))
    return 0.6 * float(sim) + _DUR_W * dur_score + 0.0 * quality

def select_best(cands, settings, used: set[str] | None = None, log=None,
                last_used: set[str] | None = None) -> MatchResult | None:
    used = used or set()
    last_used = last_used or set()
    for c in cands:
        penalty = 0.25 if c.shot_id in last_used else (0.5 if c.shot_id in used else 0.0)
        score = _blend(c.similarity, c.visual_quality, c.duration, 4.0) - penalty
        c.reason = f"{c.reason}；规范评分 {score:.3f}" + ("（复用降权）" if penalty else "")
        c.similarity = score
    cands.sort(key=lambda c: -c.similarity)
    if not cands:
        return None
    best = cands[0]
    sel_dur = min(best.duration, 6.0)
    return MatchResult(
        segment_id=1, selected_shot=best.shot_id, source=best.source,
        in_point=best.start, out_point=best.start + sel_dur, duration=sel_dur,
        score=best.similarity, reason=best.reason,
        confidence=max(0.0, min(1.0, best.similarity)))
