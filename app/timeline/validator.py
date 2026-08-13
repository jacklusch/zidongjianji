import json
from pathlib import Path

def validate_edit_plan(plan: dict, assets_root: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for item in plan.get("timeline", []):
        src = Path(item["source"])
        if assets_root is not None:
            exists = src.exists() if src.is_absolute() else (assets_root / src).exists()
            if not exists:
                errors.append(f"素材不存在: {item['source']}")
        out, inn = item.get("out", 0.0), item.get("in", 0.0)
        if inn < 0 or out <= inn:
            errors.append(f"非法时间码: in={inn} out={out}")
        if out - inn > item.get("duration", 0) * 2:
            warnings.append(f"时长偏差过大: {item['source']}")
    return errors, warnings
