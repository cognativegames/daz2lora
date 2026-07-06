from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable

LogFn = Callable[[str], None]

COMMON_PATHS: list[Path] = [
    Path.home() / "Documents" / "daz2lora" / "tools" / "kohya_ss",
    Path.home() / "Documents" / "kohya_ss",
    Path.home() / "kohya_ss",
    Path("C:/kohya_ss"),
    Path("C:/sd-scripts"),
    Path.home() / "sd-scripts",
]


def find_kohya_ss() -> Path | None:
    for p in COMMON_PATHS:
        if verify_kohya_ss(p):
            return p.resolve()
    return None


def verify_kohya_ss(path: Path | str) -> bool:
    p = Path(path) if isinstance(path, str) else path
    if not p.is_dir():
        return False
    if not (p / "sdxl_train_network.py").is_file():
        return False
    return True


def suggest_destination(workspace_root: str | None = None) -> Path:
    if workspace_root:
        return Path(workspace_root) / "tools" / "kohya_ss"
    return Path.home() / "Documents" / "daz2lora" / "tools" / "kohya_ss"


def find_venv_python(kohya_dir: Path) -> Path | None:
    is_win = platform.system() == "Windows"
    for venv_name in (".venv", "venv"):
        if is_win:
            py = kohya_dir / venv_name / "Scripts" / "python.exe"
        else:
            py = kohya_dir / venv_name / "bin" / "python3"
        if py.is_file():
            return py.resolve()
    return None


def check_prerequisites(log: LogFn) -> bool:
    git_ok = shutil.which("git") is not None
    log(
        f"{'✓' if git_ok else '✗'} Git"
        f" {'found' if git_ok else 'not found'}"
    )

    uv_ok = shutil.which("uv") is not None
    log(
        f"{'✓' if uv_ok else '✗'} uv"
        f" {'found' if uv_ok else 'not found'}"
    )

    has_nvidia = _check_nvidia_smi()
    log(f"{'✓' if has_nvidia else '⚠'} NVIDIA GPU{' detected' if has_nvidia else ' — training requires CUDA'}")

    return git_ok and uv_ok


def _check_nvidia_smi() -> bool:
    try:
        r = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def install_kohya_ss(destination: str, log: LogFn) -> bool:
    dest = Path(destination)

    if not dest.is_dir():
        log("Cloning kohya_ss repository...")
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [
                "git", "clone", "--recursive",
                "https://github.com/bmaltais/kohya_ss.git",
                str(dest),
            ],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            log(f"Clone failed: {r.stderr.strip()[:300]}")
            return False
        log("Repository cloned")
    else:
        log("Directory already exists — skipping clone")

    log("Installing Python dependencies with uv (5–15 min)...")
    uv = shutil.which("uv")
    if not uv:
        log("uv not found. Run: pip install uv")
        return False

    r = subprocess.run(
        [uv, "sync", "--frozen"],
        cwd=str(dest),
        capture_output=True, text=True,
        timeout=3600,
    )
    if r.returncode != 0:
        log(f"Dependency install failed:\n{r.stderr.strip()[:500]}")
        return False

    if find_venv_python(dest) is None:
        log("Warning: Python venv not found after setup")
        return False

    log("kohya_ss ready")
    return True
