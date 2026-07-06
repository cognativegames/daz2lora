from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from daz2lora.utils.config import AppConfig

_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

AUTO_CONFIG_NAME = "_daz2lora_auto.json"


def _bootstrap() -> bool:
    if getattr(sys, "frozen", False):
        return True

    root = Path(__file__).resolve().parent.parent.parent

    venv_python = (
        root / ".venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else root / ".venv" / "bin" / "python"
    )

    if sys.executable and sys.executable.startswith(str(venv_python.parent)):
        return True

    if not venv_python.exists():
        print("Bootstrapping daz2lora — one-time setup...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(root / ".venv")],
            check=True,
        )
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-e", str(root)],
            check=True,
        )
        print("Bootstrap complete. Launching app...")

    os.execv(str(venv_python), [str(venv_python), "-m", "daz2lora.main", *sys.argv[1:]])
    return False


def _find_auto_config() -> Path | None:
    candidates = []

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / AUTO_CONFIG_NAME)

    candidates.append(Path.cwd() / AUTO_CONFIG_NAME)
    candidates.append(Path.home() / ".daz2lora" / "auto_config.json")

    seen: set[Path] = set()
    for p in candidates:
        resolved = p.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
    return None


def _apply_auto_config(config: AppConfig) -> bool:
    auto_path = _find_auto_config()
    if auto_path is None:
        return False

    try:
        data = json.loads(auto_path.read_text())
        if data.get("source") != "daz_script":
            return False

        if data.get("daz_studio_path"):
            config.daz_studio_path = data["daz_studio_path"]

        if data.get("content_library_roots"):
            config.content_library_roots = data["content_library_roots"]

        if data.get("workspace_root"):
            config.workspace_root = data["workspace_root"]

        auto_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from daz2lora.ui.main_window import MainWindow
    from daz2lora.utils.config import AppConfig

    app = QApplication(sys.argv)
    app.setApplicationName("DAZ to LoRA")
    app.setOrganizationName("daz2lora")

    config = AppConfig.load()
    auto_applied = _apply_auto_config(config)

    if auto_applied and not config.workspace_root:
        config.workspace_root = str(Path.home() / "Documents" / "daz2lora")

    config.save()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if _bootstrap():
        main()
