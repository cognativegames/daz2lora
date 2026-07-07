from __future__ import annotations

import datetime
import io
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

LogFn = Callable[[str], None]

REPO_URL = "https://github.com/bmaltais/kohya_ss/archive/refs/heads/master.zip"
SD_SCRIPTS_URL = "https://github.com/bmaltais/sd-scripts/archive/refs/heads/master.zip"

_LOG_DIR = Path.home() / ".daz2lora" / "logs"

_COMMON_PYTHON_PATHS: list[Path] = [
    Path("/usr/local/bin/python3"),
    Path("/usr/bin/python3"),
    Path("/opt/homebrew/bin/python3"),
    Path("/opt/homebrew/bin/python3.11"),
    Path("/opt/homebrew/bin/python3.12"),
    Path("/opt/homebrew/bin/python3.13"),
    Path("/usr/local/bin/python3.11"),
    Path("/usr/local/bin/python3.12"),
    Path("/usr/local/bin/python3.13"),
    Path("C:\\Python313\\python.exe"),
    Path("C:\\Python312\\python.exe"),
    Path("C:\\Python311\\python.exe"),
    Path("C:\\Program Files\\Python313\\python.exe"),
    Path("C:\\Program Files\\Python312\\python.exe"),
    Path("C:\\Program Files\\Python311\\python.exe"),
]

COMMON_PATHS: list[Path] = [
    Path.home() / "Documents" / "daz2lora" / "tools" / "kohya_ss",
    Path.home() / "Documents" / "kohya_ss",
    Path.home() / "kohya_ss",
    Path("C:/kohya_ss"),
    Path("C:/sd-scripts"),
    Path.home() / "sd-scripts",
]


_log_path: Path | None = None


def _log_file() -> Path:
    global _log_path
    if _log_path is None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _log_path = _LOG_DIR / "kohya_install.log"
    return _log_path


def _append_crash_log(msg: str) -> None:
    try:
        with open(_log_file(), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


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


def _get_python() -> str | None:
    candidates: list[str] = []
    if getattr(sys, "frozen", False):
        py = shutil.which("python") or shutil.which("python3")
        if py:
            candidates.append(py)
        for p in _COMMON_PYTHON_PATHS:
            if p.is_file():
                candidates.append(str(p.resolve()))
    else:
        candidates.append(sys.executable)

    for candidate in candidates:
        try:
            r = subprocess.run(
                [candidate, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and "Python" in r.stdout:
                return candidate
        except Exception:
            continue
    return None


def check_prerequisites(log: LogFn) -> bool:
    python = _get_python()
    if python is None:
        log("✗ Python: not found")
        if getattr(sys, "frozen", False):
            log("")
            log("This app bundles its own Python, but kohya_ss needs a")
            log("system Python to create its virtual environment.")
            log("Install Python 3.10+ from python.org, then restart the installer.")
        else:
            log("Install Python 3.10+ from python.org, then retry.")
        return False

    r = subprocess.run(
        [python, "--version"], capture_output=True, text=True, timeout=10
    )
    ok = r.returncode == 0
    log(f"{'✓' if ok else '✗'} Python: {r.stdout.strip() if ok else 'not found'}")
    if not ok:
        stderr = r.stderr.strip()[:300]
        if "Microsoft Store" in stderr or "App execution aliases" in stderr:
            log("")
            log("The 'python' command opens the Microsoft Store instead of real Python.")
            log("Disable Store app execution aliases in Settings, or install from python.org.")
        return False

    has_nvidia = _check_nvidia_smi()
    log(
        f"{'✓' if has_nvidia else '⚠'} NVIDIA GPU"
        f"{' detected' if has_nvidia else ' — training requires CUDA'}"
    )

    return True


def _check_nvidia_smi() -> bool:
    try:
        r = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def _extract_zip(data: io.BytesIO, dest: Path, log: LogFn) -> bool:
    with zipfile.ZipFile(data) as zf:
        entries = zf.namelist()
        root = None
        for e in entries:
            if e.count("/") == 1 and e.endswith("/"):
                root = e.rstrip("/")
                break
        if root is None:
            log("Could not determine zip root directory")
            return False

        prefix = root + "/"
        for member in entries:
            if not member.startswith(prefix):
                continue
            rel = member[len(prefix):]
            if not rel:
                continue
            target = dest / rel
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
    return True


def _download_zip(dest: Path, log: LogFn) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    log("Downloading kohya_ss from GitHub...")
    try:
        req = urllib.request.urlopen(REPO_URL, timeout=120)
        data = io.BytesIO(req.read())
    except Exception as e:
        log(f"Download failed: {e}")
        return False

    log("Extracting...")
    return _extract_zip(data, dest, log)


def _ensure_sd_scripts(dest: Path, log: LogFn) -> bool:
    target = dest / "sd-scripts"
    if target.is_dir() and (target / "setup.py").is_file():
        return True

    req_path = dest / "requirements.txt"
    if not req_path.is_file():
        log("No requirements.txt found — sd-scripts not needed")
        return True

    if "sd-scripts" not in req_path.read_text(encoding="utf-8"):
        log("requirements.txt does not reference sd-scripts")
        return True

    if target.is_dir():
        log("sd-scripts directory exists but is incomplete — re-downloading")
        shutil.rmtree(target)

    log("Downloading sd-scripts (required by kohya_ss)...")
    try:
        req = urllib.request.urlopen(SD_SCRIPTS_URL, timeout=120)
        data = io.BytesIO(req.read())
    except Exception as e:
        log(f"Failed to download sd-scripts:\n{e}")
        return False

    log("Extracting sd-scripts...")
    return _extract_zip(data, target, log)


def install_kohya_ss(destination: str, log: LogFn) -> bool:
    dest = Path(destination)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append_crash_log(f"=== kohya_ss install at {timestamp} ===")

    def dual_log(msg: str) -> None:
        _append_crash_log(msg)
        log(msg)

    python = _get_python()
    if python is None:
        dual_log("Python not found. Install Python 3.10+ from python.org then retry.")
        return False

    if dest.is_dir():
        dual_log("Directory already exists — skipping download")
    else:
        if not _download_zip(dest, dual_log):
            return False

    dual_log("Creating Python virtual environment...")
    r = subprocess.run(
        [python, "-m", "venv", str(dest / "venv")],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        stderr = r.stderr.strip()[:300]
        dual_log(f"Venv creation failed:\n{stderr}")
        if "Microsoft Store" in stderr or "App execution aliases" in stderr:
            dual_log("")
            dual_log("The 'python' command on this system opens the Microsoft Store instead")
            dual_log("of running actual Python. Disable the Store app execution alias in")
            dual_log("Settings → Apps → Advanced app settings → App execution aliases,")
            dual_log("or install Python from python.org and add it to your PATH.")
        return False

    if not _ensure_sd_scripts(dest, dual_log):
        return False

    dual_log("Installing dependencies (5–15 min)...")
    pip = str(dest / "venv" / "Scripts" / "pip.exe")
    if not os.path.exists(pip):
        pip = str(dest / "venv" / "Scripts" / "pip")
    if not os.path.exists(pip):
        pip = str(dest / "venv" / "bin" / "pip")
    if not os.path.exists(pip):
        dual_log("pip not found in venv")
        return False

    req = str(dest / "requirements.txt")
    if not os.path.exists(req):
        dual_log(f"requirements.txt not found at {req}")
        return False

    r = subprocess.run(
        [pip, "install", "-r", req],
        capture_output=True, text=True, timeout=3600,
    )
    if r.returncode != 0:
        stderr = r.stderr.strip()[:500]
        dual_log(f"Dependency install failed:\n{stderr}")
        return False

    venv_py = find_venv_python(dest)
    if venv_py is None:
        dual_log("Warning: venv Python not found after install")
        return False

    dual_log("kohya_ss ready")
    return True
