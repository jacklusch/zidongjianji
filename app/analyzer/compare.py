"""本地 VLM 与线上 VLM 的画面对比（供人工校验本地描述）。"""
from pathlib import Path
from app.models.vlm import VLM
from app.analyzer.scene import detect_shots, is_image
from app.analyzer.describe import _subdivide, _shot_frames, _fmt_range
from app.analyzer.visual import fallback_visual_analysis, _VLM_PROMPT

_COMPARE_PROMPT = (
    "这是一张视频画面。以下是另一个模型对它的描述：\n"
    '"{local_desc}"\n\n'
    "请判断该描述是否与画面内容一致（对象、动作、场景是否准确）。"
    "只输出 JSON：{{\"consistent\": true或false, \"diff\": \"不一致时的差异说明或空\"}}"
)


def _judge_consistency(online_vlm, frames, local_desc) -> dict:
    """让线上 VLM 同时看图 + 本地描述，输出一致性判断。

    consistent 为三态：True / False / "unknown"（线上裁判失败）。
    """
    prompt = _COMPARE_PROMPT.format(local_desc=local_desc)
    try:
        data = online_vlm.describe(frames, prompt)
        raw = data.get("consistent")
        consistent = raw in (True, "true", "True", 1, "1")
        diff = str(data.get("diff", "") or "")
    except Exception:
        consistent = "unknown"
        diff = "线上裁判失败（限流或解析错误）"
    return {"consistent": consistent, "diff": diff, "prompt_used": prompt}


def _build_report(video_name: str, rows: list[dict], n_consistent: int, n_total: int) -> str:
    lines = [
        f"# VLM 画面对比：{video_name}",
        "",
        f"一致镜头：{n_consistent}/{n_total}",
        "",
        "| 时间码 | 本地描述 | 线上描述 | 一致性 | 差异 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        c = {"unknown": "❔", True: "✅", False: "❌"}.get(r["consistent"], "❔")
        lines.append(
            f"| {_fmt_range(r['start'], r['end'])} | {r['local']} | {r['online']} | {c} | {r['diff']} |"
        )
    return "\n".join(lines) + "\n"


def compare_video(settings, video_path, log=None, window: float = 5.0) -> Path:
    """对比单个视频的本地/线上 VLM 描述，输出 data/descriptions/<name>_compare.md。"""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"文件不存在: {video_path}")
    if is_image(video_path):
        raise ValueError(f"compare 需要视频文件: {video_path}")
    out_dir = Path(settings.data_dir) / "descriptions"
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = out_dir / "tmp_thumb"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    local_vlm = VLM(settings.vlm.provider, settings.vlm.model, settings.vlm.device,
                    settings.vlm.base_url, settings.vlm.api_key)
    compare_cfg = settings.vlm_compare
    online_vlm = VLM(compare_cfg.provider, compare_cfg.model, compare_cfg.device,
                     compare_cfg.base_url, compare_cfg.api_key)

    shots = _subdivide(detect_shots(str(video_path), settings.scene_threshold,
                                    settings.min_shot_duration, settings.ffmpeg),
                       window=window)
    rows = []
    n_consistent = 0
    for shot in shots:
        try:
            frames = _shot_frames(video_path, shot, settings, thumb_dir, shot.shot_id)
        except Exception as e:
            if log:
                log.warning(f"  [compare] {shot.shot_id} 抽帧失败: {e}")
            continue
        local_desc = "-"
        online_desc = "-"
        try:
            ld = local_vlm.describe(frames, _VLM_PROMPT)
            local_desc = str(ld.get("description", "") or "")
        except Exception as e:
            if log:
                log.warning(f"  [compare] {shot.shot_id} 本地 VLM 失败: {e}")
            try:
                local_desc = fallback_visual_analysis(frames).description + "（本地降级）"
            except Exception:
                local_desc = "-"
        try:
            od = online_vlm.describe(frames, _VLM_PROMPT)
            online_desc = str(od.get("description", "") or "")
        except Exception as e:
            if log:
                log.warning(f"  [compare] {shot.shot_id} 线上 VLM 失败: {e}")
            online_desc = "（线上失败）"
        verdict = {"consistent": "unknown", "diff": "裁判未执行（描述失败）"}
        if local_desc != "-" and online_desc != "（线上失败）":
            verdict = _judge_consistency(online_vlm, frames, local_desc)
            if verdict["consistent"] is True:
                n_consistent += 1
        rows.append({"shot": shot.shot_id, "start": shot.start, "end": shot.end,
                     "local": local_desc, "online": online_desc,
                     "consistent": verdict["consistent"], "diff": verdict["diff"]})

    md = _build_report(video_path.name, rows, n_consistent, len(rows))
    out = out_dir / f"{video_path.stem}_compare.md"
    out.write_text(md, encoding="utf-8")
    return out
