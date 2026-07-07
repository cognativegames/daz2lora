from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from daz2lora.utils.kohya_setup import install_kohya_ss


class _InstallWorker(QObject):
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, destination: str) -> None:
        super().__init__()
        self.destination = destination

    def run(self) -> None:
        def log(msg: str) -> None:
            self.log.emit(msg)

        ok = install_kohya_ss(self.destination, log)
        self.finished.emit(ok, self.destination)


class KohyaInstallDialog(QDialog):
    install_completed = Signal(bool, str)

    def __init__(self, destination: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Install kohya_ss")
        self.setModal(True)
        self.resize(640, 420)
        self.setMinimumSize(480, 300)

        layout = QVBoxLayout(self)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 12px; background: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self.log_output)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self._result: bool | None = None
        self._worker = _InstallWorker(destination)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)

        thread = threading.Thread(target=self._worker.run, daemon=True)
        thread.start()

    def _on_log(self, msg: str) -> None:
        self.log_output.appendPlainText(msg)

    def _on_finished(self, success: bool, path: str) -> None:
        self._result = success
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        self.close_btn.setEnabled(True)
        self.install_completed.emit(success, path)

        if success:
            self.log_output.appendPlainText(f"\n✓ kohya_ss installed at:\n  {path}")
        else:
            self.log_output.appendPlainText(
                "\n✗ Installation failed. See above for details."
            )

    def _on_close(self) -> None:
        self.accept()

    def install_result(self) -> bool | None:
        return self._result
