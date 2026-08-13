from app.index.database import Database
from app.index.footage_index import discover, needs_reindex, index_one
from app.analyzer.scene import is_image
from app.analyzer.frames import sample_times, extract_frame
from app.analyzer.visual import fallback_visual_analysis
from app.analyzer.audio import transcribe

def run_index(settings, analyze=True, force_analyze=False, log=None) -> dict:
    """扫描 → 入库 →（可选）切分帧分析 + Whisper 转写。返回报告。"""
    if log is None:
        import logging
        log = logging.getLogger("index")
    abs_root = settings.materials_dir
    if not abs_root.exists():
        raise FileNotFoundError(f"素材目录不存在: {abs_root}")
    db = Database(settings.footage_db)
    report = {"media": 0, "shots": 0, "new": 0, "changed": 0, "skipped": 0}
    known = {m["rel_path"] for m in db.get_all_media()}
    found = set()
    for rel, info in discover(settings):
        found.add(rel)
        mtime = info.path.stat().st_mtime
        state = needs_reindex(db, rel, info, mtime)
        if state == "":
            report["skipped"] += 1
            if force_analyze:
                try:
                    _analyze_shot(settings, db, rel, info, log, report)
                except Exception as e:
                    log.warning(f"  [index] {rel} 分析失败，跳过: {e}")
                    report["failed"] = report.get("failed", 0) + 1
                    continue
                report["reanalyzed"] = report.get("reanalyzed", 0) + 1
            continue
        db.delete_media(rel)
        try:
            r = index_one(settings, db, rel, info, mtime, log)
        except Exception as e:
            log.warning(f"  [index] {rel} 索引失败，跳过: {e}")
            report["failed"] = report.get("failed", 0) + 1
            continue
        report["media"] += 1
        report["shots"] += r["shots_idx"]
        report["new" if state == "new" else "changed"] += 1
        if analyze:
            try:
                _analyze_shot(settings, db, rel, info, log, report)
            except Exception as e:
                log.warning(f"  [index] {rel} 分析失败，跳过: {e}")
                report["failed"] = report.get("failed", 0) + 1
    for rel in known - found:
        db.delete_media(rel)
        log.info(f"  [index] 移除已删除素材: {rel}")
    db.close()
    return report

def _analyze_shot(settings, db, rel, info, log, report):
    m = db.get_media_by_path(rel)
    if m is None:
        return
    if is_image(info.path):
        return
    shots = db.get_shots_by_media(m["id"])
    thumb = settings.thumbnails_dir
    thumb.mkdir(parents=True, exist_ok=True)
    for sh in shots:
        frames = []
        times = sample_times(sh["start"], sh["end"], settings.frames_min, settings.frames_max)
        for i, t in enumerate(times):
            f = extract_frame(str(info.path), t, settings.ffmpeg, thumb / f"{sh['shot_id']}_{i:02d}.jpg")
            if f is not None:
                frames.append(f)
        va = fallback_visual_analysis(frames)
        db.upsert_visual(sh["shot_id"], va.description, va.objects, va.actions,
                         va.environment, va.shot_type, va.camera_motion,
                         va.people_count, va.visual_quality, "{}")
        tr = transcribe(settings, str(info.path), sh["start"], sh["end"])
        for i, seg in enumerate(tr):
            db.upsert_transcript(sh["shot_id"], i, seg["start"], seg["end"], seg["text"])
        report["visual"] = report.get("visual", 0) + 1