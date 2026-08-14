from dataclasses import dataclass, field
from pathlib import Path
import yaml
from app.utils.paths import project_root

_DEFAULTS = {
    "models": {"vlm": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
               "vlm_reranker": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
               "vlm_compare": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
               "embedding": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
               "asr": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""},
               "llm": {"provider": "none", "model": "", "device": "auto", "base_url": "", "api_key": ""}},
    "video": {"scene_threshold": 0.35, "min_shot_duration": 1.0},
    "matching": {"top_k": 20, "rerank_k": 5},
    "index": {"frames_min": 3, "frames_max": 8},
    "render": {"resolution": "1920x1080", "fps": 30, "format": "mp4"},
    "gpu": {"enabled": "auto", "memory_fraction": 0.7},
}

@dataclass
class ModelConfig:
    provider: str = "none"
    model: str = ""
    device: str = "auto"
    base_url: str = ""
    api_key: str = ""

@dataclass
class Settings:
    root: Path
    models_dir: Path
    materials_dir: Path
    data_dir: Path
    output_dir: Path
    logs_dir: Path
    projects_dir: Path
    footage_dir: Path
    bin_dir: Path
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    vlm: ModelConfig = field(default_factory=ModelConfig)
    vlm_reranker: ModelConfig = field(default_factory=ModelConfig)
    vlm_compare: ModelConfig = field(default_factory=ModelConfig)
    embedding: ModelConfig = field(default_factory=ModelConfig)
    asr: ModelConfig = field(default_factory=ModelConfig)
    llm: ModelConfig = field(default_factory=ModelConfig)
    scene_threshold: float = 0.35
    min_shot_duration: float = 1.0
    top_k: int = 20
    rerank_k: int = 5
    frames_min: int = 3
    frames_max: int = 8
    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_format: str = "mp4"
    gpu_enabled: str = "auto"
    gpu_memory_fraction: float = 0.7

    @property
    def footage_db(self) -> Path:
        return self.footage_dir / "index.db"

    @property
    def thumbnails_dir(self) -> Path:
        return self.footage_dir / "thumbnails"

    @property
    def embeddings_dir(self) -> Path:
        return self.footage_dir / "embeddings"

    @property
    def transcripts_dir(self) -> Path:
        return self.footage_dir / "transcripts"

    @property
    def resolution(self) -> tuple[int, int]:
        return self.width, self.height

def load_settings(config_path: Path | None = None) -> Settings:
    root = project_root()
    cfg_path = config_path or root / "config.yaml"
    raw: dict = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    merge = _DEFAULTS.copy()
    deep = {k: {**_DEFAULTS[k], **(raw.get(k) or {})} for k in _DEFAULTS}
    merge.update(deep)
    render = merge["render"]
    w, h = (str(render["resolution"]).split("x"))
    s = Settings(
        root=root,
        models_dir=root / "models",
        materials_dir=root / "materials",
        data_dir=root / "data",
        output_dir=root / "output",
        logs_dir=root / "data" / "logs",
        projects_dir=root / "data" / "projects",
        footage_dir=root / "data" / "footage",
        bin_dir=root / "bin",
        vlm=ModelConfig(**merge["models"]["vlm"]),
        vlm_reranker=ModelConfig(**merge["models"]["vlm_reranker"]),
        vlm_compare=ModelConfig(**merge["models"]["vlm_compare"]),
        embedding=ModelConfig(**merge["models"]["embedding"]),
        asr=ModelConfig(**merge["models"]["asr"]),
        llm=ModelConfig(**merge["models"]["llm"]),
        scene_threshold=float(merge["video"]["scene_threshold"]),
        min_shot_duration=float(merge["video"]["min_shot_duration"]),
        top_k=int(merge["matching"]["top_k"]),
        rerank_k=int(merge["matching"]["rerank_k"]),
        frames_min=int(merge["index"]["frames_min"]),
        frames_max=int(merge["index"]["frames_max"]),
        fps=int(merge["render"]["fps"]),
        video_format=merge["render"]["format"],
        gpu_enabled=merge["gpu"]["enabled"],
        gpu_memory_fraction=float(merge["gpu"]["memory_fraction"]),
        width=int(w), height=int(h),
    )
    if (root / "bin" / "ffmpeg" / "bin" / "ffmpeg.exe").exists():
        s.ffmpeg = str(root / "bin" / "ffmpeg" / "bin" / "ffmpeg.exe")
        s.ffprobe = str(root / "bin" / "ffmpeg" / "bin" / "ffprobe.exe")
    elif (root / "bin" / "ffmpeg" / "ffmpeg.exe").exists():
        s.ffmpeg = str(root / "bin" / "ffmpeg" / "ffmpeg.exe")
        s.ffprobe = str(root / "bin" / "ffmpeg" / "ffprobe.exe")
    return s