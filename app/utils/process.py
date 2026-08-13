import os
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