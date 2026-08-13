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
    verdict = _judge_consistency(online, [None], "本地描述")
    assert verdict["consistent"] is True
    assert "本地描述" in verdict["prompt_used"]

def test_judge_consistency_parse_failure_fallback():
    online = type("V", (), {"describe": lambda self, frames, prompt: {"consistent": False}})()
    verdict = _judge_consistency(online, [None], "a")
    assert verdict["consistent"] is False

def test_judge_consistency_exception_is_unknown():
    def boom(self, frames, prompt):
        raise RuntimeError("限流")
    online = type("V", (), {"describe": boom})()
    verdict = _judge_consistency(online, [None], "本地描述")
    assert verdict["consistent"] == "unknown"
    assert "线上裁判失败" in verdict["diff"]

def test_judge_consistency_string_false_is_not_truthy():
    online = type("V", (), {"describe": lambda self, frames, prompt: {"consistent": "false"}})()
    verdict = _judge_consistency(online, [None], "a")
    assert verdict["consistent"] is False

def test_build_report_has_three_columns():
    shots = [FakeShot("s1", 0.0, 5.0, 5.0)]
    rows = [{"shot": "s1", "start": 0.0, "end": 5.0, "local": "L", "online": "O",
             "consistent": True, "diff": ""}]
    md = _build_report("factory01.mp4", rows, 1, 1)
    assert "本地描述" in md and "线上描述" in md and "一致性" in md
    assert "L" in md and "O" in md

def test_compare_video_output_file(tmp_path, monkeypatch):
    from app.analyzer.compare import compare_video
    class FakeSettings:
        data_dir = tmp_path
        vlm = type("MC", (), {"provider": "local", "model": "m", "device": "cpu", "base_url": "", "api_key": ""})()
        vlm_compare = type("MC", (), {"provider": "openai", "model": "glm-4v-flash", "device": "cpu", "base_url": "u", "api_key": "k"})()
        scene_threshold = 0.35
        min_shot_duration = 1.0
        ffmpeg = "ffmpeg"
        frames_min = 3
        frames_max = 8
    v = Path(tmp_path) / "x.mp4"
    v.write_bytes(b"fake")
    monkeypatch.setattr("app.analyzer.compare.detect_shots",
                        lambda *a, **k: [type("S", (), {"shot_id": "s1", "start": 0.0, "end": 4.0, "duration": 4.0})()])
    monkeypatch.setattr("app.analyzer.compare._subdivide", lambda shots, window: shots)
    monkeypatch.setattr("app.analyzer.compare._shot_frames", lambda *a, **k: [None])
    monkeypatch.setattr("app.analyzer.compare.VLM", lambda *a, **k: type("V", (), {
        "describe": lambda self, frames, prompt: {"description": "工厂画面"}
    })())
    out = compare_video(FakeSettings(), v)
    assert out.exists()
    assert "_compare.md" in out.name
    assert "工厂画面" in out.read_text(encoding="utf-8")
