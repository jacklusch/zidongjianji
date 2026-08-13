#!/usr/bin/env python
"""从 HuggingFace / ModelScope 下载本地模型。

用法：
    python scripts/download_models.py --list
    python scripts/download_models.py --source ms
    python scripts/download_models.py --source hf --model embedding
    python scripts/download_models.py --source ms --write-config
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODELS = {
    "vlm": {
        "hf": "Qwen/Qwen3-VL-2B-Instruct-GGUF",
        "ms": "Qwen/Qwen3-VL-2B-Instruct-GGUF",
        "note": "VLM 描述 + reranker（GGUF）",
    },
    "asr": {
        "hf": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "ms": "iic/speech_paraformer_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "note": "FunASR 中文转写（paraformer-zh）",
    },
    "embedding": {
        "hf": "BAAI/bge-small-zh-v1.5",
        "ms": "AI-ModelScope/bge-small-zh-v1.5",
        "note": "Embedding（bge-small-zh）",
    },
}

def source_id(role: str, source: str) -> str:
    if role not in MODELS:
        raise ValueError(f"未知模型: {role}（可选 {sorted(MODELS)}）")
    if source not in ("hf", "ms"):
        raise ValueError("source 必须是 hf 或 ms")
    return MODELS[role][source]

def resolve_target(root: Path, role: str, repo_id: str) -> Path:
    return root / "models" / role

def snapshot_hf(repo_id: str, local_dir: Path):
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo_id, local_dir=str(local_dir))

def snapshot_ms(repo_id: str, local_dir: Path):
    from modelscope import snapshot_download
    snapshot_download(repo_id, local_dir=str(local_dir))

def download_all(root: Path, sources: str = "hf", models: list[str] | None = None,
                 install: bool = True) -> dict:
    roles = models or list(MODELS)
    if install:
        _ensure_deps()
    report: dict = {}
    for role in roles:
        rid = source_id(role, sources)
        target = resolve_target(root, role, rid)
        target.mkdir(parents=True, exist_ok=True)
        try:
            if sources == "hf":
                snapshot_hf(rid, target)
            else:
                snapshot_ms(rid, target)
            report[role] = True
        except Exception as e:
            print(f"[download] {role} 失败（{sources}）: {e}", file=sys.stderr)
            print(f"           提示：国内网络可尝试 --source ms", file=sys.stderr)
            report[role] = False
    return report

def _ensure_deps():
    req = ROOT / "requirements-models.txt"
    if not req.exists():
        return
    py = ROOT / "venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = sys.executable
    import subprocess
    subprocess.run([str(py), "-m", "pip", "install", "-r", str(req)], check=False)

def write_config(root: Path, report: dict):
    """把成功下载的模型本地路径写回 config.yaml 的 model 字段。"""
    cfg_path = root / "config.yaml"
    if not cfg_path.exists():
        print("[config] config.yaml 不存在，跳过 --write-config", file=sys.stderr)
        return
    import yaml
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    models = raw.setdefault("models", {})
    for role, ok in report.items():
        if ok:
            target = root / "models" / role
            cfg_entry = models.setdefault(role, {})
            if role == "vlm":
                # model 写为目录即可：get_gguf_llm 会 glob 主模型与 mmproj
                cfg_entry["provider"] = "local"
                cfg_entry["model"] = str(target)
            elif role == "asr":
                cfg_entry["provider"] = "local"
                cfg_entry["model"] = str(target)
            elif role == "embedding":
                cfg_entry["provider"] = "local"
                cfg_entry["model"] = str(target)
    cfg_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("[config] 已更新 config.yaml 的 model 路径")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="download_models", description="下载本地模型（HF/ModelScope）")
    ap.add_argument("--source", choices=["hf", "ms"], default="hf", help="下载源：hf=HuggingFace, ms=ModelScope")
    ap.add_argument("--model", choices=sorted(MODELS), action="append", help="只下载指定模型（可多次）")
    ap.add_argument("--list", action="store_true", help="打印模型清单")
    ap.add_argument("--write-config", action="store_true", help="下载后把本地路径写回 config.yaml")
    ap.add_argument("--skip-install", action="store_true", help="跳过 pip 依赖安装")
    args = ap.parse_args(argv)
    if args.list:
        for role, m in MODELS.items():
            print(f"{role:12s} hf={m['hf']}\n{'':12s} ms={m['ms']}\n{'':12s} {m['note']}")
        return 0
    report = download_all(ROOT, sources=args.source, models=args.model,
                          install=not args.skip_install)
    if args.write_config:
        write_config(ROOT, report)
    ok = sum(1 for v in report.values() if v)
    print(f"下载完成：{ok}/{len(report)} 成功")
    return 0 if ok == len(report) else 1

if __name__ == "__main__":
    raise SystemExit(main())
