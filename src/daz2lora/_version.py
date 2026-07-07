from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _git_describe() -> str | None:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _read_version_file() -> str | None:
    try:
        base = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
        )
        ver_file = base / "VERSION"
        if ver_file.exists():
            return ver_file.read_text().strip()
    except Exception:
        pass
    return None


def _git_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def resolve_version() -> str:
    env_ver = os.environ.get("DAZ2LORA_VERSION")
    if env_ver:
        return env_ver

    git_ver = _git_describe()
    if git_ver:
        return git_ver.lstrip("v")

    bundled = _read_version_file()
    if bundled:
        return bundled

    githash = _git_hash()
    if githash:
        return f"0.0.0+{githash}"

    return "0.0.0"


VERSION = resolve_version()
