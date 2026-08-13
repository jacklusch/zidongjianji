from app.script.parser import parse_script, rule_parse

SAMPLE = """
主题：现代化香肠生产工艺

开头展示现代化工厂环境。

接下来展示工人操作生产线。

然后展示香肠产品特写。

最后展示包装完成后的产品。
"""

def test_rule_parse_creates_segments():
    segs = rule_parse(SAMPLE)
    assert len(segs) >= 4
    assert all(s.duration > 0 for s in segs)
    assert segs[0].script_text != ""

def test_rule_parse_removes_connectors():
    segs = rule_parse("开头展示现代化工厂环境。")
    assert segs and "开头" not in segs[0].script_text

def test_parse_empty():
    assert parse_script("") == []

def test_llm_parse_tolerates_null_fields():
    from app.script.parser import llm_parse
    import json
    class FakeLLM:
        def __init__(self, raw):
            self._raw = raw
        def available(self):
            return True
        def generate(self, prompt):
            return self._raw
    llm = FakeLLM(json.dumps([
        {"id": 1, "script_text": "a", "visual_requirements": None, "duration": None},
        {"id": 2, "script_text": "b", "visual_requirements": ["x"], "duration": "bad"},
        {"id": 3, "script_text": "c", "visual_requirements": ["y"], "duration": 3.5},
    ]))
    segs = llm_parse("脚本", llm)
    assert len(segs) == 3
    assert segs[0].duration == 4.0 and segs[0].visual_requirements == []
    assert segs[1].duration == 4.0
    assert segs[2].duration == 3.5
