import json
from pathlib import Path
from app.utils.process import run


def _normalize_timeline(plan: dict, outdir: Path, ffmpeg: str, width: int, height: int, fps: int,
                        assets_root: Path | None = None) -> list[Path]:
    parts = []
    for item in plan.get("timeline", []):
        src = Path(item["source"])
        if not src.is_absolute() and assets_root is not None:
            src = Path(assets_root) / src
        seg_dur = item.get("out", 0.0) - item.get("in", 0.0)
        if seg_dur <= 0:
            continue
        part = outdir / f"part_{item['script_id']:02d}.mp4"
        try:
            _render_clip(src, item.get("in", 0.0), seg_dur, part, ffmpeg, width, height, fps)
        except Exception:
            # 单片段失败不崩溃整个项目：跳过并在 stdout 提示（规格 22 节）
            print(f"[render] 片段渲染失败已跳过: {src}")
            continue
        parts.append(part)
    return parts


def _render_clip(src: Path, start: float, dur: float, out: Path, ffmpeg: str,
                 width: int, height: int, fps: int):
    ext = src.suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(src), "-t", f"{dur:.3f}",
               "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out)]
    else:
        cmd = [ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
               "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)]
    run(cmd, timeout=600)


def _concat(parts: list[Path], out: Path, ffmpeg: str) -> Path:
    if not parts:
        raise RuntimeError("时间线为空，无法渲染")
    if len(parts) == 1:
        out.write_bytes(parts[0].read_bytes())
        return out
    list_file = out.parent / "concat.txt"
    lines = "".join(f"file '{p.as_posix()}'\n" for p in parts)
    list_file.write_text(lines, encoding="utf-8")
    run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)], timeout=600)
    return out


def render_plan(plan: dict, out: Path, ffmpeg: str = "ffmpeg", width: int = 1920,
                height: int = 1080, fps: int = 30, assets_root: Path | None = None) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.parent / "render_tmp"
    temp.mkdir(parents=True, exist_ok=True)
    parts = _normalize_timeline(plan, temp, ffmpeg, width, height, fps, assets_root)
    _concat(parts, out, ffmpeg)
    return out
