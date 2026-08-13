from app.timeline.planner import build_timeline

def test_build_timeline_missing():
    segs = [{"id": 1, "script_text": "xx", "visual_requirements": [], "duration": 4.0}]
    items, missing, warnings = build_timeline(segs, [])
    assert missing and len(items) == 0
