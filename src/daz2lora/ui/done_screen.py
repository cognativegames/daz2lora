from __future__ import annotations

import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QHeaderView, QLabel,
    QMessageBox, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import CharacterProject


def _format_size(bytes_val: int) -> str:
    if bytes_val >= 1_000_000_000:
        return f"{bytes_val / 1_000_000_000:.2f} GB"
    if bytes_val >= 1_000_000:
        return f"{bytes_val / 1_000_000:.2f} MB"
    if bytes_val >= 1_000:
        return f"{bytes_val / 1_000:.2f} KB"
    return f"{bytes_val} B"


class DoneScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        self._build_header(layout)
        self._build_lora_details_section(layout)
        self._build_summary_section(layout)
        self._build_actions_section(layout)

        layout.addStretch()
        scroll.setWidget(scroll_content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QLabel("\u2705 Training Complete!")
        header.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #4ec9b0; padding-bottom: 4px;"
        )
        layout.addWidget(header)

    def _build_lora_details_section(self, layout: QVBoxLayout) -> None:
        self.lora_group = QGroupBox("LoRA Model")
        self.lora_group.setVisible(False)
        lora_layout = QVBoxLayout(self.lora_group)

        form = QFormLayout()
        self.character_id_label = QLabel("")
        form.addRow("Character ID:", self.character_id_label)

        self.trigger_label = QLabel("")
        form.addRow("Trigger Word:", self.trigger_label)

        self.version_label = QLabel("")
        form.addRow("Version:", self.version_label)

        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        form.addRow("Output Path:", self.path_label)

        self.size_label = QLabel("")
        form.addRow("File Size:", self.size_label)

        self.date_label = QLabel("")
        form.addRow("Created:", self.date_label)

        lora_layout.addLayout(form)

        lora_layout.addWidget(QLabel("Training History:"))
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(
            ["Version", "Looks Included", "Date", "Path"]
        )
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        lora_layout.addWidget(self.history_table)

        layout.addWidget(self.lora_group)

    def _build_summary_section(self, layout: QVBoxLayout) -> None:
        self.summary_group = QGroupBox("Training Summary")
        self.summary_group.setVisible(False)
        summary_layout = QFormLayout(self.summary_group)

        self.images_label = QLabel("")
        summary_layout.addRow("Total Images:", self.images_label)

        self.looks_label = QLabel("")
        summary_layout.addRow("Looks Used:", self.looks_label)

        layout.addWidget(self.summary_group)

    def _build_actions_section(self, layout: QVBoxLayout) -> None:
        self.actions_group = QGroupBox("Actions")
        self.actions_group.setVisible(False)
        actions_layout = QVBoxLayout(self.actions_group)

        self.open_folder_btn = QPushButton("Open Containing Folder")
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        actions_layout.addWidget(self.open_folder_btn)

        self.copy_comfy_btn = QPushButton("Copy to ComfyUI")
        self.copy_comfy_btn.clicked.connect(self._on_copy_to_comfyui)
        actions_layout.addWidget(self.copy_comfy_btn)

        self.new_training_btn = QPushButton("Start New Training Run")
        self.new_training_btn.clicked.connect(
            lambda: self.main_window.navigate_to(6)
        )
        actions_layout.addWidget(self.new_training_btn)

        self.new_project_btn = QPushButton("New Character Project")
        self.new_project_btn.clicked.connect(
            lambda: self.main_window.navigate_to(1)
        )
        actions_layout.addWidget(self.new_project_btn)

        layout.addWidget(self.actions_group)

    def on_enter(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        project = self.main_window.current_project
        config = self.main_window.config

        if project is None or not project.training_history:
            self.lora_group.setVisible(False)
            self.summary_group.setVisible(False)
            self.actions_group.setVisible(False)
            return

        self._populate_lora_details(project)
        self._populate_summary(project)
        self.lora_group.setVisible(True)
        self.summary_group.setVisible(True)
        self.actions_group.setVisible(True)

    def _populate_lora_details(self, project: CharacterProject) -> None:
        self.character_id_label.setText(project.character.character_id)
        self.trigger_label.setText(project.character.base_trigger_word)

        latest = max(project.training_history, key=lambda e: e.version)
        self.version_label.setText(str(latest.version))

        lora_path = Path(latest.path) if latest.path else None
        if lora_path and lora_path.exists():
            self.path_label.setText(str(lora_path.resolve()))
            try:
                st = lora_path.stat()
                self.size_label.setText(_format_size(st.st_size))
                dt = datetime.datetime.fromtimestamp(st.st_mtime)
                self.date_label.setText(dt.strftime("%Y-%m-%d %H:%M:%S"))
            except OSError:
                self.size_label.setText("N/A")
                self.date_label.setText("N/A")
        else:
            self.path_label.setText(latest.path or "N/A")
            self.size_label.setText("N/A")
            self.date_label.setText("N/A")

        self._populate_history_table(project, latest.version)

    def _populate_history_table(
        self, project: CharacterProject, latest_version: int
    ) -> None:
        sorted_entries = sorted(
            project.training_history, key=lambda e: e.version, reverse=True
        )
        self.history_table.setRowCount(len(sorted_entries))

        highlight_bg = "#2d5016"
        normal_bg = ""

        for i, entry in enumerate(sorted_entries):
            is_latest = entry.version == latest_version
            bg = highlight_bg if is_latest else normal_bg

            version_item = QTableWidgetItem(str(entry.version))
            version_item.setTextAlignment(Qt.AlignCenter)
            if is_latest:
                version_item.setBackground(Qt.darkGreen)
                version_item.setForeground(Qt.white)
            else:
                version_item.setBackground(Qt.darkGray)
                version_item.setForeground(Qt.lightGray)
            self.history_table.setItem(i, 0, version_item)

            looks_text = ", ".join(entry.looks_included) if entry.looks_included else "All"
            looks_item = QTableWidgetItem(looks_text)
            if is_latest:
                looks_item.setBackground(Qt.darkGreen)
                looks_item.setForeground(Qt.white)
            self.history_table.setItem(i, 1, looks_item)

            entry_path = Path(entry.path) if entry.path else None
            if entry_path and entry_path.exists():
                try:
                    dt = datetime.datetime.fromtimestamp(entry_path.stat().st_mtime)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except OSError:
                    date_str = "N/A"
            else:
                date_str = "N/A"
            date_item = QTableWidgetItem(date_str)
            if is_latest:
                date_item.setBackground(Qt.darkGreen)
                date_item.setForeground(Qt.white)
            else:
                date_item.setBackground(Qt.darkGray)
                date_item.setForeground(Qt.lightGray)
            self.history_table.setItem(i, 2, date_item)

            path_item = QTableWidgetItem(entry.path or "N/A")
            if is_latest:
                path_item.setBackground(Qt.darkGreen)
                path_item.setForeground(Qt.white)
            self.history_table.setItem(i, 3, path_item)

        self.history_table.resizeRowsToContents()

    def _populate_summary(self, project: CharacterProject) -> None:
        dataset_root = project.dataset_root_path
        total_images = 0
        if dataset_root.exists():
            image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
            total_images = sum(
                1 for f in dataset_root.rglob("*") if f.suffix.lower() in image_exts
            )
        self.images_label.setText(str(total_images))

        num_looks = len(project.looks) if project.looks else 0
        self.looks_label.setText(str(num_looks))

    def _on_open_folder(self) -> None:
        project = self.main_window.current_project
        if project is None or not project.trained_lora_path:
            return
        path = Path(project.trained_lora_path).parent
        if path.exists():
            QDesktopServices.openUrl(path.as_uri())

    def _on_copy_to_comfyui(self) -> None:
        project = self.main_window.current_project
        config = self.main_window.config
        if project is None or not project.trained_lora_path:
            return

        dest_dir = Path(config.comfyui_loras_path) if config.comfyui_loras_path else None
        if not dest_dir:
            QMessageBox.warning(
                self,
                "ComfyUI Not Configured",
                "ComfyUI path not configured. Go to Setup to set it.",
            )
            return

        src = Path(project.trained_lora_path)
        if not src.exists():
            QMessageBox.critical(
                self, "File Not Found", f"LoRA file not found:\n{src}"
            )
            return

        if not dest_dir.exists():
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(
                    self, "Error", f"Could not create destination:\n{e}"
                )
                return

        dest = dest_dir / src.name
        try:
            import shutil
            shutil.copy2(str(src), str(dest))
            QMessageBox.information(
                self,
                "Copied!",
                f"LoRA copied to:\n{dest}",
            )
        except OSError as e:
            QMessageBox.critical(self, "Copy Error", str(e))
