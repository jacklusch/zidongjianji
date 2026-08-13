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
    settings = load_settings()
    settings.materials_dir = Path(args.directory)
    settings.ffmpeg, settings.ffprobe = find_ffmpeg(settings)
    log = setup_logging(settings.logs_dir, "analyze")
    rep = run_index(settings, analyze=True, force_analyze=True, log=log)
    log.info(f"analyze 完成: {rep}")
    print(json.dumps(rep, ensure_ascii=False, indent=2))

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
