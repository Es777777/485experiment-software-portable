from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_config_runtime_base(config_path: Path) -> Path:
    resolved = config_path.resolve()
    base_dir = resolved.parent
    if base_dir.name.lower() == "config":
        return base_dir.parent
    return base_dir


def ensure_runtime_directories(root: Path | None = None) -> Path:
    app_root = get_app_root() if root is None else root
    for folder_name in ("config", "logs", "output", "videos"):
        (app_root / folder_name).mkdir(parents=True, exist_ok=True)
    return app_root
