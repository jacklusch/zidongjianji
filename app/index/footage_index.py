from app.analyzer.media import probe_media, MediaInfo, SUPPORTED
from app.analyzer.scene import detect_shots
from app.utils.hashing import sha256_file

ANALYSIS_VERSION = "v1"

def build_rel(root, p) -> str:
    return p.resolve().relative_to(root.resolve()).as_posix()

def discover(settings) -> list[tuple[str, MediaInfo]]:
    """返回 [(rel_path, MediaInfo)] 所有素材。"""
    out = []
    for p in settings.materials_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            try:
                info = probe_media(p, settings.ffprobe)
            except Exception:
                continue
            out.append((build_rel(settings.materials_dir, p), info))
    return out

def needs_reindex(db, rel: str, info: MediaInfo, mtime: float) -> str:
    """返回 ''（无需）或 'new'|'changed'"""
    row = db.get_media_by_path(rel)
    h = sha256_file(info.path)
    if row is None:
        return "new"
    if row["hash"] != h or abs((row.get("mtime") or 0.0) - mtime) > 1e-6:
        return "changed"
    return ""

def index_one(settings, db, rel: str, info: MediaInfo, mtime: float, log) -> dict:
    h = sha256_file(info.path)
    mid = db.upsert_media(info.filename, rel, info.duration, info.width, info.height,
                          info.fps, info.codec, info.audio, info.size, h, mtime)
    db.delete_shots_for_media(mid)
    try:
        shots = detect_shots(str(info.path), settings.scene_threshold,
                             settings.min_shot_duration, settings.ffmpeg)
    except Exception as e:
        db.delete_media(rel)
        raise RuntimeError(f"{rel} 场景切分失败: {e}") from e
    n = 0
    for sh in shots:
        db.upsert_shot(sh.shot_id, mid, sh.start, sh.end, sh.duration,
                       ANALYSIS_VERSION, "scenedetect")
        n += 1
    log.info(f"  [index] {rel} -> {n} shots")
    return {"changed": 1, "shots_idx": n}