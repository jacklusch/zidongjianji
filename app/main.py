import argparse
import sys
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

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="app.main", description="本地 AI 视频剪辑系统")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan", help="扫描素材目录")
    s.add_argument("directory")
    s.set_defaults(func=cmd_scan)
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
