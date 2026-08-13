import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.analyzer.compare import _judge_consistency, _build_report

class FakeShot:
    def __init__(self, shot_id, start, end, duration):
        self.shot_id = shot_id
        self.start = start
        self.end = end
        self.duration = duration

def test_judge_consistency_consistent():
    online = type("V", (), {"describe": lambda self, frames, prompt: {"consistent": True, "diff": ""}})()
    verdict = _judge_consistency(online, [None], "本地描述", "线上描述")
    assert verdict["consistent"] is True
    assert "本地描述" in verdict["prompt_used"]

def test_judge_consistency_parse_failure_fallback():
    online = type("V", (), {"describe": lambda self, frames, prompt: {"consistent": False}})()
    verdict = _judge_consistency(online, [None], "a", "b")
    assert verdict["consistent"] is False

def test_build_report_has_three_columns():
    shots = [FakeShot("s1", 0.0, 5.0, 5.0)]
    rows = [{"shot": "s1", "start": 0.0, "end": 5.0, "local": "L", "online": "O",
             "consistent": True, "diff": ""}]
    md = _build_report("factory01.mp4", rows, 1, 1)
    assert "本地描述" in md and "线上描述" in md and "一致性" in md
    assert "L" in md and "O" in md
