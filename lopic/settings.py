"""persistent settings stored under %APPDATA%/Lopic"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "Lopic"


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def default_config() -> dict[str, Any]:
    return {
        "install_root": str(Path.home() / "LopicEngines"),
        "window": {"width": 1280, "height": 840},
        "installed": {},
    }


def load_config() -> dict[str, Any]:
    cfg = default_config()
    path = config_path()
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cfg
        if isinstance(stored, dict):
            cfg.update(stored)
    return cfg


def save_config(cfg: dict[str, Any]) -> Path:
    path = config_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path