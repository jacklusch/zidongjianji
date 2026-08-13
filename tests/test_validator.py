from app.timeline.validator import validate_edit_plan

def _plan():
    return {"timeline": [
        {"script_id": 1, "source": "materials/factory01.mp4", "in": 0.0, "out": 4.0,
         "duration": 4.0, "reason": "r", "confidence": 0.9, "reused": False}]}

def test_validate_ok(tmp_path, sample_video):
    plan = _plan()
    plan["timeline"][0]["source"] = str(sample_video)
    errors, warnings = validate_edit_plan(plan)
    assert not errors

def test_validate_bad_timecode(tmp_path, sample_video):
    plan = _plan()
    plan["timeline"][0]["source"] = str(sample_video)
    plan["timeline"][0]["out"] = -1.0
    errors, warnings = validate_edit_plan(plan)
    assert errors

def test_validate_missing_asset(tmp_path):
    plan = _plan()
    errors, warnings = validate_edit_plan(plan, assets_root=tmp_path)
    assert any("素材不存在" in e for e in errors)

def test_validate_absolute_source_with_assets_root(tmp_path, sample_video):
    plan = _plan()
    plan["timeline"][0]["source"] = str(sample_video)
    errors, warnings = validate_edit_plan(plan, assets_root=tmp_path)
    assert not errors
