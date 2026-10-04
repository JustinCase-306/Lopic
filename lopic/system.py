"""local hardware detection: gpu, vram, disk space, python interpreters"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout or ""


def gpu_info() -> dict:
    """query nvidia-smi for the primary gpu. falls back to wmic on older setups."""
    out = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[1].isdigit():
            return {
                "vendor": "nvidia",
                "name": parts[0],
                "vram_mb": int(parts[1]),
                "vram_gb": round(int(parts[1]) / 1024, 1),
                "driver": parts[2],
                "cuda": True,
            }
    return {
        "vendor": "unknown",
        "name": "keine NVIDIA-GPU erkannt",
        "vram_mb": 0,
        "vram_gb": 0.0,
        "driver": "",
        "cuda": False,
    }


def disk_free_gb(path: str | Path) -> float:
    target = Path(path)
    while not target.exists() and target != target.parent:
        target = target.parent
    try:
        usage = shutil.disk_usage(target)
    except OSError:
        return 0.0
    return round(usage.free / (1024**3), 1)


def git_available() -> bool:
    return shutil.which("git") is not None


def tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {}

    git = _run(["git", "--version"])
    versions["git"] = git.strip() if git else "fehlt"

    uv = _run(["uv", "--version"])
    versions["uv"] = uv.strip() if uv else "fehlt"

    versions["python"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return versions


def system_report() -> dict:
    gpu = gpu_info()
    root = Path.home() / "LopicEngines"
    return {
        "gpu": gpu,
        "disk_free_gb": disk_free_gb(root),
        "disk_path": str(root),
        "tools": tool_versions(),
        "install_root": str(root),
    }