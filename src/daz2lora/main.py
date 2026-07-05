from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def _bootstrap() -> bool:
    """Ensure .venv exists and re-exec through it if running from source."""
    if getattr(sys, "frozen", False):
        return True  # PyInstaller bundle — deps baked in, nothing to do

    root = Path(__file__).resolve().parent.parent.parent  # project root

    venv_python = (
        root / ".venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else root / ".venv" / "bin" / "python"
    )

    # Already inside the project venv → safe to import deps
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

    # Re-exec through venv so all deps are available
    os.execv(str(venv_python), [str(venv_python), "-m", "daz2lora.main", *sys.argv[1:]])
    return False  # never reached


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from daz2lora.ui.main_window import MainWindow
    from daz2lora.utils.config import AppConfig

    app = QApplication(sys.argv)
    app.setApplicationName("DAZ to LoRA")
    app.setOrganizationName("daz2lora")

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if _bootstrap():
        main()
