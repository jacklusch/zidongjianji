import json
import shutil
from pathlib import Path
from app.editors.renderer import render_plan


def run_render(settings, plan_path: Path, log=None) -> tuple[Path, Path]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    proj_dir = plan_path.parent
    final = proj_dir / "final.mp4"
    preview = proj_dir / "preview.mp4"
    temp_out = settings.output_dir / f"{plan.get('project', 'demo')}_preview.mp4"
    render_plan(plan, temp_out, ffmpeg=settings.ffmpeg,
                width=settings.width, height=settings.height, fps=settings.fps)
    shutil.copyfile(temp_out, preview)
    shutil.copyfile(temp_out, final)
    if log:
        log.info(f"渲染完成: preview={preview} final={final}")
    return preview, final
