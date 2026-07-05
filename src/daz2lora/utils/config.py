from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_FILE = "daz2lora_config.json"


@dataclass
class AppConfig:
    daz_studio_path: str = ""
    content_library_roots: list[str] = field(
        default_factory=lambda: ["C:/Users/Public/Documents/DAZ 3D/Studio/My Library"]
    )
    workspace_root: str = ""
    kohya_ss_path: str = ""
    sdxl_checkpoint_path: str = ""
    comfyui_loras_path: str = ""
    renders_per_session: int = 50
    render_width: int = 1536
    render_height: int = 1536
    render_samples: int = 32
    update_channel: str = "stable"  # "stable" or "latest"
    github_repo: str = "cognativegames/daz2lora"

    def save(self) -> None:
        Path(CONFIG_FILE).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> AppConfig:
        try:
            data = json.loads(Path(CONFIG_FILE).read_text())
            return cls(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            cfg = cls()
            cfg.save()
            return cfg
