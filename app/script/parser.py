import json
import re
from app.script.schema import ScriptSegment

CONNECTORS = "开头|首先|其次|接下来|然后|再|接着|最后|终于"

def _clean(text: str) -> str:
    return re.sub(rf"^\s*(主题[:：].*|{CONNECTORS})\s*", "", text).strip()

def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"(?<=[。！？?!.])\s*", "\n", text)
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("主题"):
            continue
        line = _clean(line)
        if line and re.search(r"[0-9A-Za-z\u4e00-\u9fff]", line):
            out.append(line)
    return out

def rule_parse(text: str, default_duration: float = 4.0) -> list[ScriptSegment]:
    segs = []
    for i, sent in enumerate(_split_sentences(text), start=1):
        reqs = [t for t in re.findall(r"[\u4e00-\u9fff]{2,}", sent)]
        segs.append(ScriptSegment(id=i, script_text=sent,
                                  visual_requirements=reqs, duration=default_duration))
    return segs

def llm_parse(text: str, llm, default_duration: float = 4.0) -> list[ScriptSegment]:
    prompt = (
        "把以下剪辑脚本文案转换为 JSON 数组，每项含 id、script_text、visual_requirements、duration。"
        "不要输出 JSON 之外的内容。\n脚本：\n" + text)
    raw = llm.generate(prompt)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", raw)
        data = json.loads(m.group(0)) if m else []
    return [ScriptSegment(id=i + 1, script_text=str(d.get("script_text", "")),
                          visual_requirements=d.get("visual_requirements") or [],
                          duration=_safe_duration(d.get("duration"), default_duration))
            for i, d in enumerate(data)]

def _safe_duration(value, default: float) -> float:
    try:
        f = float(value)
        return f if f > 0 else default
    except (TypeError, ValueError):
        return default

def parse_script(text: str, llm=None, default_duration: float = 4.0) -> list[ScriptSegment]:
    if text is None or not text.strip():
        return []
    if llm is not None and getattr(llm, "available", lambda: False)():
        return llm_parse(text, llm, default_duration)
    return rule_parse(text, default_duration)
