from dataclasses import dataclass

@dataclass
class ScriptSegment:
    id: int
    script_text: str
    visual_requirements: list[str]
    duration: float

    def to_dict(self) -> dict:
        return {"id": self.id, "script_text": self.script_text,
                "visual_requirements": self.visual_requirements, "duration": self.duration}
