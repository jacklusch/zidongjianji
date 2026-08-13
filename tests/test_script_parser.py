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
