import json
from pathlib import Path
from app.script.parser import parse_script
from app.script.planner import write_script_plan
from app.matching.retriever import retrieve_top_k
from app.matching.reranker import rerank_candidates
from app.matching.matcher import select_best
from app.timeline.schema import EditPlan
from app.timeline.planner import build_timeline
from app.timeline.validator import validate_edit_plan
from app.models.llm import LLM
from dataclasses import asdict

def run_plan(settings, script_path: Path, project: str = "demo", log=None) -> Path:
    script_text = script_path.read_text(encoding="utf-8")
    llm = LLM(settings.llm.provider, settings.llm.model, settings.llm.device)
    segs = parse_script(script_text, llm=llm)
    proj_dir = settings.projects_dir / project
    proj_dir.mkdir(parents=True, exist_ok=True)
    write_script_plan(segs, proj_dir / "script_plan.json")

    match_results = []
    matches = []
    used: set[str] = set()
    last_used: set[str] = set()
    for seg in segs:
        cands = retrieve_top_k(settings, seg, top_k=settings.top_k)
        cands = rerank_candidates(cands, settings, log=log)
        m = select_best(cands, settings, used=used, last_used=last_used, log=log)
        if m:
            used.add(m.selected_shot)
            last_used = {m.selected_shot}
            match_results.append({"segment_id": seg.id, "selected": asdict(m)})
        matches.append(m)

    (proj_dir / "match_results.json").write_text(
        json.dumps(match_results, ensure_ascii=False, indent=2), encoding="utf-8")

    items, missing, warnings = build_timeline(segs, matches, project, str(script_path))
    plan = EditPlan(project=project, source_script=str(script_path), timeline=items,
                    missing=missing, warnings=warnings)
    errors, warns = validate_edit_plan(plan.to_dict())
    plan.warnings += warns
    if errors:
        plan.warnings += [f"校验错误: {e}" for e in errors]
    out = proj_dir / "edit_plan.json"
    out.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    if log:
        log.info(f"edit_plan 已写入 {out}，{len(items)} 片段，{len(missing)} 缺失")
    return out
