from dataclasses import dataclass, field

@dataclass
class TimelineItem:
    script_id: int
    source: str
    in_point: float
    out_point: float
    duration: float
    reason: str
    confidence: float
    reused: bool = False

    def to_dict(self) -> dict:
        return {"script_id": self.script_id, "source": self.source, "in": round(self.in_point, 3),
                "out": round(self.out_point, 3), "duration": round(self.duration, 3),
                "reason": self.reason, "confidence": round(self.confidence, 3), "reused": self.reused}

@dataclass
class EditPlan:
    project: str
    source_script: str
    timeline: list[TimelineItem] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"version": 1, "project": self.project, "source_script": self.source_script,
                "timeline": [t.to_dict() for t in self.timeline],
                "missing": self.missing, "warnings": self.warnings}
