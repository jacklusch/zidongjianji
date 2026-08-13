import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.analyzer.describe import _build_timeline, _summarize

class FakeShot:
    def __init__(self, sid, start, end, duration):
        self.shot_id = sid
        self.start = start
        self.end = end
        self.duration = duration

class FakeVA:
    def __init__(self, description, objects, actions, environment, people=0):
        self.description = description
        self.objects = objects
        self.actions = actions
        self.environment = environment
        self.shot_type = "medium"
        self.camera_motion = "static"
        self.people_count = people
        self.visual_quality = 0.5

def test_build_timeline():
    shots = [FakeShot("s1", 0.0, 5.0, 5.0), FakeShot("s2", 5.0, 10.0, 5.0)]
    analyses = [FakeVA("室内有人行走", ["人"], ["行走"], "室内"),
                FakeVA("室外街道", ["车"], ["行驶"], "街道")]
    lines = _build_timeline(shots, analyses)
    assert len(lines) == 2
    assert "00:00-00:05" in lines[0]
    assert "室内有人行走" in lines[0]
    assert "车" in lines[1]

def test_summarize_aggregates():
    shots = [FakeShot("s1", 0.0, 5.0, 5.0)]
    analyses = [FakeVA("室内", ["人", "桌子"], ["行走"], "室内", 2)]
    summary = _summarize(shots, analyses)
    assert summary["duration"] == "5.0s"
    assert "人" in summary["objects"]
    assert "桌子" in summary["objects"]
    assert summary["people"] == 2
    assert "室内" in summary["environments"]

def test_subdivide_long_shot():
    from app.analyzer.describe import _subdivide
    shots = [FakeShot("s1", 0.0, 25.0, 25.0)]
    parts = _subdivide(shots, window=5.0)
    assert len(parts) == 5
    assert abs(parts[0].start - 0.0) < 1e-6
    assert abs(parts[0].end - 5.0) < 1e-6
    assert abs(parts[-1].end - 25.0) < 1e-6

def test_subdivide_keeps_short_shots():
    from app.analyzer.describe import _subdivide
    shots = [FakeShot("s1", 0.0, 3.0, 3.0)]
    parts = _subdivide(shots, window=5.0)
    assert len(parts) == 1
