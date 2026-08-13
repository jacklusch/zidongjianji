"""导出视觉分析描述为人类可读的 Markdown 校验文件。"""
import json
from pathlib import Path
from app.index.database import Database


def _fmt_time(seconds) -> str:
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "-"
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


def _fmt_num(value, ndigits: int = 2) -> str:
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return "-"


def _as_list(v) -> list:
    if isinstance(v, str):
        try:
            v = json.loads(v) if v else []
        except json.JSONDecodeError:
            return []
    return v if isinstance(v, list) else []


def _cell(text) -> str:
    """转义 Markdown 表格单元格内的管道符与换行。"""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def export_visual_review(settings) -> Path:
    """从 SQLite 读取镜头与视觉分析，生成 data/footage/visual_review.md。"""
    out_dir = Path(settings.footage_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "visual_review.md"
    db = Database(settings.footage_db)
    lines = [
        "# 视频画面描述校验报告",
        "",
        f"生成时间：{Path(out).parent.name}（数据源：{db.path.name}）",
        "",
        "## 镜头视觉描述",
        "",
        "| 素材 | 镜头 | 时间码 | 时长 | 描述 | 对象 | 动作 | 环境 | 场景类型 | 机位 | 人数 | 质量 | 缩略图 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    thumb_dir = Path(settings.thumbnails_dir)
    for sh in db.get_all_shots():
        va = db.get_visual(sh["shot_id"])
        thumb = thumb_dir / f"{sh['shot_id']}_00.jpg"
        thumb_cell = f"`{thumb.name}`" if thumb.exists() else "-"
        lines.append(
            "| {source} | {shot} | {start} | {dur}s | {desc} | {objs} | {acts} | {env} | {stype} | {cam} | {people} | {q} | {thumb} |".format(
                source=_cell(sh.get("source", "")),
                shot=_cell(sh["shot_id"]),
                start=_fmt_time(sh.get("start")),
                dur=_fmt_num(sh.get("duration", 0)),
                desc=_cell((va or {}).get("description", "-")),
                objs=_cell(", ".join(_as_list((va or {}).get("objects"))) or "-"),
                acts=_cell(", ".join(_as_list((va or {}).get("actions"))) or "-"),
                env=_cell((va or {}).get("environment", "-") or "-"),
                stype=_cell((va or {}).get("shot_type", "-") or "-"),
                cam=_cell((va or {}).get("camera_motion", "-") or "-"),
                people=_cell((va or {}).get("people_count", "-")),
                q=_fmt_num((va or {}).get("visual_quality", "-")),
                thumb=thumb_cell,
            )
        )
    db.close()
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
