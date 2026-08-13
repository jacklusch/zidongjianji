import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

class RunError(RuntimeError):
    pass

def run(cmd: Iterable[str], cwd=None, timeout: int = 300, env=None) -> subprocess.CompletedProcess:
    """shell=False 执行外部命令，失败抛 RunError（含 stdout/stderr）。"""
    proc = subprocess.run(
        list(cmd), cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, shell=False,
        env=os.environ if env is None else {**os.environ, **env},
    )
    if proc.returncode != 0:
        raise RunError(f"命令失败 ({proc.returncode}): {cmd}\n{proc.stdout[-2000:]} {proc.stderr[-4000:]}")
    return proc

def find_ffmpeg(settings) -> tuple[str, str]:
    """返回 (ffmpeg, ffprobe)；优先 bin/ffmpeg，其次 PATH，都没有则抛 RunError 提示安装。"""
    p = settings.bin_dir / "ffmpeg"
    for cand in (p / "bin", p):
        if (cand / "ffmpeg.exe").exists():
            return str(cand / "ffmpeg.exe"), str(cand / "ffprobe.exe")
    ff = shutil.which("ffmpeg")
    if ff:
        base = Path(ff).parent
        return ff, str(base / ("ffprobe.exe" if os.name == "nt" else "ffprobe"))
    raise RunError("FFmpeg 未找到。请运行 scripts\\install.ps1 或安装 FFmpeg 并加入 PATH")