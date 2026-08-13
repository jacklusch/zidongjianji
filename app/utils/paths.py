from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def ensure_dirs(dirs) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)