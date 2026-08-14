"""对单个视频生成完整内容描述（分镜头时间线 + 概述 + 汇总）。"""
import json
from pathlib import Path
from app.analyzer.scene import detect_shots, is_image
from app.analyzer.frames import sample_times, extract_frame
from app.analyzer.visual import fallback_visual_analysis, vlm_visual_analysis


def _fmt_range(start: float, end: float) -> str:
    def fmt(s):
        m, sec = divmod(int(s), 60)
        return f"{m:02d}:{sec:02d}"
    return f"{fmt(start)}-{fmt(end)}"


def _subdivide(shots, window: float = 5.0):
    """把超过 window 秒的镜头按固定窗口切分为子段（长镜头/无切点视频用）。"""
    parts = []
    for i, shot in enumerate(shots):
        if shot.duration <= window:
            parts.append(shot)
            continue
        t = shot.start
        idx = 1
        while t < shot.end - 1e-6:
            end = min(t + window, shot.end)
            from types import SimpleNamespace
            parts.append(SimpleNamespace(
                shot_id=f"{shot.shot_id}_{idx:03d}",
                start=t, end=end, duration=end - t))
            t = end
            idx += 1
    return parts


def _shot_frames(video_path, shot, settings, thumb_dir, shot_id) -> list:
    frames = []
    times = sample_times(shot.start, shot.end, settings.frames_min, settings.frames_max)
    for i, t in enumerate(times):
        f = extract_frame(str(video_path), t, settings.ffmpeg,
                          thumb_dir / f"{shot_id}_{i:02d}.jpg")
        if f is not None:
            frames.append(f)
    return frames


def _build_timeline(shots, analyses) -> list[str]:
    lines = []
    for shot, va in zip(shots, analyses):
        objects = ", ".join(va.objects) or "-"
        actions = ", ".join(va.actions) or "-"
        lines.append(
            f"- **{_fmt_range(shot.start, shot.end)}**（{shot.duration:.1f}s）: {va.description}"
            f"  \n  对象: {objects} | 动作: {actions} | 环境: {va.environment or '-'}"
        )
    return lines


def _summarize(shots, analyses) -> dict:
    objects, actions, environments = [], [], []
    people = 0
    total = 0.0
    for shot, va in zip(shots, analyses):
        total += shot.duration
        people = max(people, va.people_count)
        for o in va.objects:
            if o not in objects:
                objects.append(o)
        for a in va.actions:
            if a not in actions:
                actions.append(a)
        if va.environment and va.environment not in environments:
            environments.append(va.environment)
    return {
        "duration": f"{total:.1f}s",
        "shots": len(shots),
        "objects": objects,
        "actions": actions,
        "environments": environments,
        "people": people,
    }


def describe_video(settings, video_path, log=None, window: float = 5.0) -> Path:
    """分析单个视频，输出 data/descriptions/<文件名>.md。

    window: 镜头细分窗口（秒）。长镜头/无切点视频会按此窗口切分为多个时间段。
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"文件不存在: {video_path}")
    out_dir = Path(settings.data_dir) / "descriptions"
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = out_dir / "tmp_thumb"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    from app.models.vlm import VLM
    cfg = settings.vlm
    device = "cpu" if settings.gpu_enabled == "off" else cfg.device
    vlm = VLM(cfg.provider, cfg.model, device, cfg.base_url, cfg.api_key) if cfg.provider in ("local", "openai") else None

    shots = detect_shots(str(video_path), settings.scene_threshold,
                         settings.min_shot_duration, settings.ffmpeg)
    shots = _subdivide(shots, window=window)
    analyses = []
    for shot in shots:
        frames = _shot_frames(video_path, shot, settings, thumb_dir, shot.shot_id)
        if vlm is not None:
            try:
                analyses.append(vlm_visual_analysis(frames, vlm))
            except Exception as e:
                if log:
                    log.warning(f"  [describe] {shot.shot_id} VLM 失败降级: {e}")
                analyses.append(fallback_visual_analysis(frames))
        else:
            analyses.append(fallback_visual_analysis(frames))

    summary = _summarize(shots, analyses)
    timeline = _build_timeline(shots, analyses)
    overview = _overview_text(summary, timeline)

    out = out_dir / f"{video_path.stem}.md"
    content = (
        f"# 视频内容描述：{video_path.name}\n\n"
        f"- 路径：`{video_path}`\n"
        f"- 总时长：{summary['duration']}，共 {summary['shots']} 个镜头\n\n"
        f"## 整体概述\n\n{overview}\n\n"
        f"## 分镜头时间线\n\n" + "\n".join(timeline) + "\n\n"
        f"## 内容汇总\n\n"
        f"- **对象**：{', '.join(summary['objects']) or '-'}\n"
        f"- **动作**：{', '.join(summary['actions']) or '-'}\n"
        f"- **环境**：{', '.join(summary['environments']) or '-'}\n"
        f"- **最大人数**：{summary['people']}\n"
    )
    out.write_text(content, encoding="utf-8")
    return out


def _overview_text(summary, timeline) -> str:
    """由时间线描述生成整体概述：VLM 不可用时用规则拼接。"""
    parts = [f"该视频共 {summary['shots']} 个镜头，总时长 {summary['duration']}。"]
    if summary["environments"]:
        parts.append(f"主要场景：{', '.join(summary['environments'])}。")
    if summary["objects"]:
        parts.append(f"出现的主要物体：{', '.join(summary['objects'])}。")
    if summary["actions"]:
        parts.append(f"主要动作：{', '.join(summary['actions'])}。")
    return " ".join(parts)
