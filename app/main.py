import argparse
import json
import sys
from pathlib import Path
from app.config.settings import load_settings
from app.utils.process import find_ffmpeg
from app.utils.logging import setup_logging

def cmd_scan(args):
    settings = load_settings()
    log = setup_logging(settings.logs_dir, "scan")
    ffmpeg, ffprobe = find_ffmpeg(settings)
    from app.analyzer.media import scan_directory
    log.info(f"扫描目录: {args.directory}")
    items = scan_directory(args.directory, ffprobe=ffprobe)
    log.info(f"找到 {len(items)} 个文件")
    for it in items:
        print(f"{it.path} | {it.duration:.2f}s | {it.width}x{it.height} | {it.codec} | audio={'yes' if it.audio else 'no'}")

def cmd_index(args):
    from app.pipeline.index_pipeline import run_index
    settings = load_settings()
    settings.materials_dir = Path(args.directory)
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "index")
    rep = run_index(settings, analyze=True, log=log)
    log.info(f"index 完成: {rep}")
    print(json.dumps(rep, ensure_ascii=False, indent=2))

def cmd_analyze(args):
    from app.pipeline.index_pipeline import run_index
    from app.index.review_export import export_visual_review
    settings = load_settings()
    settings.materials_dir = Path(args.directory)
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "analyze")
    rep = run_index(settings, analyze=True, force_analyze=True, log=log)
    log.info(f"analyze 完成: {rep}")
    try:
        review = export_visual_review(settings)
        log.info(f"视觉校验报告已生成: {review}")
        print(f"视觉校验报告: {review}")
    except Exception as e:
        log.warning(f"生成视觉校验报告失败: {e}")
    print(json.dumps(rep, ensure_ascii=False, indent=2))

def cmd_search(args):
    from app.index.search import SearchBackend
    from app.index.database import Database
    settings = load_settings()
    backend = SearchBackend(settings)
    hits = backend.search(args.query, settings.top_k)
    db = Database(settings.footage_db)
    for sid, score in hits[:10]:
        sh = next((s for s in db.get_all_shots() if s["shot_id"] == sid), {})
        print(f"{score:6.3f} {sid:30s} {sh.get('source', '')} [{sh.get('start', 0)}-{sh.get('end', 0)}]")
    db.close()
    print(f"共 {len(hits)} 个结果")

def cmd_export(args):
    from app.index.review_export import export_visual_review
    settings = load_settings()
    review = export_visual_review(settings)
    print(f"视觉校验报告: {review}")

def cmd_describe(args):
    from pathlib import Path
    from app.analyzer.describe import describe_video
    settings = load_settings()
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "describe")
    out = describe_video(settings, Path(args.video), log=log, window=args.window)
    print(f"视频内容描述: {out}")
    print(out.read_text(encoding="utf-8"))

def cmd_plan(args):
    from pathlib import Path
    from app.pipeline.matching_pipeline import run_plan
    settings = load_settings()
    log = setup_logging(settings.logs_dir, "plan")
    out = run_plan(settings, Path(args.script), project=args.project, log=log)
    print(f"edit_plan: {out}")

def cmd_render(args):
    from pathlib import Path
    from app.pipeline.render_pipeline import run_render
    from app.utils.process import find_ffmpeg
    settings = load_settings()
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "render")
    preview, final = run_render(settings, Path(args.plan), log=log)
    print(f"preview: {preview}\nfinal: {final}")

def cmd_build(args):
    from pathlib import Path
    from app.pipeline.index_pipeline import run_index
    from app.pipeline.matching_pipeline import run_plan
    from app.pipeline.render_pipeline import run_render
    from app.utils.process import find_ffmpeg
    settings = load_settings()
    settings.materials_dir = Path(args.materials) if args.materials else settings.materials_dir
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "build")
    log.info(f"build 开始，脚本={args.script}")
    report = run_index(settings, analyze=True, log=log)
    log.info(f"索引完成 {report}")
    plan = run_plan(settings, Path(args.script), project=args.project, log=log)
    plan_json = json.loads(plan.read_text(encoding="utf-8"))
    if not plan_json.get("timeline"):
        missing = len(plan_json.get("missing", []))
        log.warning(f"无可用镜头（缺失 {missing} 段），跳过渲染")
        print(f"无可用镜头（缺失 {missing} 段），未渲染；edit_plan: {plan}")
        return
    preview, final = run_render(settings, plan, log=log)
    print(f"完成: preview={preview} final={final}")

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="app.main", description="本地 AI 视频剪辑系统")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan", help="扫描素材目录")
    s.add_argument("directory")
    s.set_defaults(func=cmd_scan)
    s = sub.add_parser("index", help="扫描+场景切分+分析素材库")
    s.add_argument("directory")
    s.set_defaults(func=cmd_index)
    s = sub.add_parser("analyze", help="对素材执行视觉/语音分析")
    s.add_argument("directory")
    s.set_defaults(func=cmd_analyze)
    s = sub.add_parser("search", help="语义搜索素材")
    s.add_argument("query")
    s.set_defaults(func=cmd_search)
    s = sub.add_parser("export", help="导出镜头视觉描述校验报告 (Markdown)")
    s.set_defaults(func=cmd_export)
    s = sub.add_parser("describe", help="完整描述单个视频内容（时间线+概述+汇总）")
    s.add_argument("video")
    s.add_argument("--window", type=float, default=5.0, help="镜头细分窗口秒数（长镜头/无切点视频默认 5 秒）")
    s.set_defaults(func=cmd_describe)
    s = sub.add_parser("plan", help="脚本→检索→匹配→edit_plan")
    s.add_argument("script")
    s.add_argument("--project", default="demo")
    s.set_defaults(func=cmd_plan)
    s = sub.add_parser("render", help="按 edit_plan 渲染")
    s.add_argument("plan")
    s.set_defaults(func=cmd_render)
    s = sub.add_parser("build", help="一键：index→plan→render")
    s.add_argument("script")
    s.add_argument("--project", default="demo")
    s.add_argument("--materials", default=None)
    s.set_defaults(func=cmd_build)
    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
