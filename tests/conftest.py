import shutil
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def subprocess_run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

@pytest.fixture(scope="session")
def ffmpeg() -> str:
    p = ROOT / "bin" / "ffmpeg" / "ffmpeg.exe"
    if p.exists():
        return str(p)
    exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("ffmpeg not available")
    return exe

@pytest.fixture(scope="session")
def ffprobe() -> str:
    p = ROOT / "bin" / "ffmpeg" / "ffprobe.exe"
    if p.exists():
        return str(p)
    exe = shutil.which("ffprobe")
    if not exe:
        pytest.skip("ffprobe not available")
    return exe

@pytest.fixture(scope="session")
def sample_video(tmp_path_factory, ffmpeg):
    out = tmp_path_factory.mktemp("media") / "factory01.mp4"
    cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc2=duration=6:size=640x360:rate=30",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)]
    subprocess_run(cmd)
    return out