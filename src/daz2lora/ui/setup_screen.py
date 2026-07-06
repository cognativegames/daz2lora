from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from daz2lora import VERSION
from daz2lora.utils.updater import UpdateCheckResult, check_for_updates, apply_update


class SetupScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._build_ui()
        self._load_config()
        self.main_window.config_changed.connect(self._load_config)

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Setup & Configuration")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self._build_daz_group(layout)
        self._build_workspace_group(layout)
        self._build_training_group(layout)
        self._build_render_group(layout)
        self._build_update_group(layout)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Save & Continue")
        save_btn.setObjectName("actionBtn")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; color: white; font-weight: bold; padding: 8px 24px; font-size: 14px; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        save_btn.clicked.connect(self._save_and_continue)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        scroll.setWidget(scroll_content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _make_help_button(self, text: str) -> QPushButton:
        btn = QPushButton("?")
        btn.setFixedSize(22, 22)
        btn.setToolTip("Click for help")
        btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #0d7377; color: white; border-radius: 11px;"
            "  font-weight: bold; font-size: 11px; border: none;"
            "}"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        btn.clicked.connect(lambda checked, t=text: QMessageBox.information(self, "Help", t))
        return btn

    def _build_daz_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("DAZ Studio Configuration")
        form = QFormLayout(group)

        self.daz_path = QLineEdit()
        browse_daz = QPushButton("Browse...")
        browse_daz.clicked.connect(lambda: self._browse_file(self.daz_path, "Select DAZ Studio Executable", False))
        row = QHBoxLayout()
        row.addWidget(self.daz_path)
        row.addWidget(browse_daz)
        form.addRow("Executable Path:", row)

        form.addRow(QLabel("Content Library Roots:"))
        lib_layout = QVBoxLayout()
        self.lib_list = QListWidget()
        lib_btn_row = QHBoxLayout()
        add_btn = QPushButton("Add...")
        add_btn.clicked.connect(self._add_library_root)
        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self._remove_library_root)
        lib_btn_row.addWidget(add_btn)
        lib_btn_row.addWidget(rem_btn)
        lib_btn_row.addStretch()
        lib_layout.addWidget(self.lib_list)
        lib_layout.addLayout(lib_btn_row)
        form.addRow(lib_layout)

        self.renders_per_session = QSpinBox()
        self.renders_per_session.setRange(1, 500)
        form.addRow("Renders per Session:", self.renders_per_session)

        help_row = QHBoxLayout()
        help_row.addStretch()
        help_row.addWidget(self._make_help_button(
            "DAZ Studio must be installed on this PC.\n\n"
            "• Executable Path: Full path to DAZStudio.exe "
            "(usually C:\\Program Files\\DAZ 3D\\DAZStudio4\\DAZStudio.exe)\n"
            "• Content Library Roots: Directories where your DAZ content "
            "(characters, outfits, props) live. The app scans these to "
            "find your assets.\n"
            "• Renders per Session: Maximum renders before the app pauses.\n\n"
            "See the project README for DAZ Studio setup instructions."
        ))
        form.addRow(help_row)

        layout.addWidget(group)

    def _build_workspace_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Workspace")
        form = QFormLayout(group)
        self.workspace_root = QLineEdit()
        browse_ws = QPushButton("Browse...")
        browse_ws.clicked.connect(lambda: self._browse_file(self.workspace_root, "Select Workspace Directory", True))
        row = QHBoxLayout()
        row.addWidget(self.workspace_root)
        row.addWidget(browse_ws)
        form.addRow("Workspace Root:", row)

        help_row = QHBoxLayout()
        help_row.addStretch()
        help_row.addWidget(self._make_help_button(
            "All project files, renders, captions, and trained LoRAs are "
            "stored here.\n\n"
            "Pick a folder with plenty of free space — SDXL datasets and "
            "renders add up fast.\n\n"
            "Each character project gets its own subfolder under "
            "./projects/."
        ))
        form.addRow(help_row)

        layout.addWidget(group)

    def _build_training_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Training Configuration")
        form = QFormLayout(group)

        self.kohya_path = QLineEdit()
        browse_k = QPushButton("Browse...")
        browse_k.clicked.connect(lambda: self._browse_file(self.kohya_path, "Select kohya_ss Install Directory", True))
        row = QHBoxLayout()
        row.addWidget(self.kohya_path)
        row.addWidget(browse_k)
        form.addRow("kohya_ss Path:", row)

        self.sdxl_path = QLineEdit()
        browse_s = QPushButton("Browse...")
        browse_s.clicked.connect(lambda: self._browse_file(self.sdxl_path, "Select SDXL Checkpoint", False))
        row = QHBoxLayout()
        row.addWidget(self.sdxl_path)
        row.addWidget(browse_s)
        form.addRow("SDXL Checkpoint:", row)

        self.comfy_path = QLineEdit()
        browse_c = QPushButton("Browse...")
        browse_c.clicked.connect(lambda: self._browse_file(self.comfy_path, "Select ComfyUI LoRAs Folder", True))
        row = QHBoxLayout()
        row.addWidget(self.comfy_path)
        row.addWidget(browse_c)
        form.addRow("ComfyUI LoRAs:", row)

        help_row = QHBoxLayout()
        help_row.addStretch()
        help_row.addWidget(self._make_help_button(
            "Paths for model training.\n\n"
            "• kohya_ss Path: Your kohya_ss or sd-scripts installation "
            "(the folder containing sdxl_train_network.py).\n"
            "• SDXL Checkpoint: A .safetensors base model. Download from "
            "CivitAI or HuggingFace.\n"
            "• ComfyUI LoRAs (optional): Finished LoRAs are copied here "
            "automatically.\n\n"
            "See the project README for recommended checkpoints and "
            "kohya_ss setup."
        ))
        form.addRow(help_row)

        layout.addWidget(group)

    def _build_render_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Render Settings")
        form = QFormLayout(group)

        self.render_width = QSpinBox()
        self.render_width.setRange(1024, 2048)
        self.render_width.setSingleStep(64)
        form.addRow("Width:", self.render_width)

        self.render_height = QSpinBox()
        self.render_height.setRange(1024, 2048)
        self.render_height.setSingleStep(64)
        form.addRow("Height:", self.render_height)

        self.render_samples = QSpinBox()
        self.render_samples.setRange(8, 512)
        self.render_samples.setSingleStep(8)
        form.addRow("Samples:", self.render_samples)

        help_row = QHBoxLayout()
        help_row.addStretch()
        help_row.addWidget(self._make_help_button(
            "DAZ Studio render output settings.\n\n"
            "• Width / Height: Output resolution. 1024x1024 is standard "
            "for SDXL training.\n"
            "• Samples: Render quality. Higher = better but slower. "
            "32-64 is a good starting point.\n\n"
            "These map directly to DAZ Studio's render settings."
        ))
        form.addRow(help_row)

        layout.addWidget(group)

    def _build_update_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Updates")
        form = QFormLayout(group)

        ver_label = QLabel(f"v{VERSION}")
        ver_label.setStyleSheet("font-weight: bold; color: #0d7377;")
        form.addRow("Current Version:", ver_label)

        self.update_channel = QComboBox()
        self.update_channel.addItems(["stable", "latest"])
        form.addRow("Channel:", self.update_channel)

        self.github_repo_input = QLineEdit()
        form.addRow("GitHub Repo:", self.github_repo_input)

        btn_row = QHBoxLayout()
        self.check_btn = QPushButton("Check for Updates")
        self.check_btn.clicked.connect(self._on_check_updates)
        self.apply_btn = QPushButton("Apply Update")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply_update)
        btn_row.addWidget(self.check_btn)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch()
        form.addRow(btn_row)

        self.update_status = QLabel("")
        self.update_status.setWordWrap(True)
        form.addRow(self.update_status)

        help_row = QHBoxLayout()
        help_row.addStretch()
        help_row.addWidget(self._make_help_button(
            "Check for new versions of the app.\n\n"
            "• Channel: 'stable' for tagged releases, 'latest' for "
            "auto-builds from the master branch.\n"
            "• Check for Updates: Queries GitHub for available versions.\n"
            "• Apply Update: Downloads and replaces app files, then "
            "restarts."
        ))
        form.addRow(help_row)

        self._update_result: Optional[UpdateCheckResult] = None
        layout.addWidget(group)

    def _update_buttons(self, checking: bool = False) -> None:
        self.check_btn.setEnabled(not checking)
        self.apply_btn.setEnabled(self._update_result is not None and not checking)

    def _on_check_updates(self) -> None:
        self._update_buttons(checking=True)
        self.update_status.setText("Checking...")
        QApplication.processEvents()

        channel = self.update_channel.currentText()
        result = check_for_updates(channel)
        self._update_result = result if result.available else None

        if not result.available:
            self.update_status.setText(
                f"No update available (v{VERSION} is current)."
                if channel == "stable"
                else "No latest build found. The GH Action hasn't run yet."
            )
            self._update_buttons()
            return

        self.update_status.setText(
            f"v{result.latest_version} available\n\n{result.changelog[:500]}"
        )
        self._update_buttons()

    def _on_apply_update(self) -> None:
        if not self._update_result:
            return
        self._update_buttons(checking=True)
        self.update_status.setText("Applying update...")
        QApplication.processEvents()

        ok = apply_update(self._update_result)
        if ok:
            self.update_status.setText("Update applied. Restarting...")
            self._update_result = None
        else:
            self.update_status.setText("Update failed. Check the log.")
        self._update_buttons()

    def _load_config(self) -> None:
        cfg = self.main_window.config
        self.daz_path.setText(cfg.daz_studio_path)
        self.workspace_root.setText(cfg.workspace_root)
        self.kohya_path.setText(cfg.kohya_ss_path)
        self.sdxl_path.setText(cfg.sdxl_checkpoint_path)
        self.comfy_path.setText(cfg.comfyui_loras_path)
        self.renders_per_session.setValue(cfg.renders_per_session)
        self.render_width.setValue(cfg.render_width)
        self.render_height.setValue(cfg.render_height)
        self.render_samples.setValue(cfg.render_samples)
        idx = self.update_channel.findText(cfg.update_channel)
        if idx >= 0:
            self.update_channel.setCurrentIndex(idx)
        self.github_repo_input.setText(cfg.github_repo)
        self._populate_lib_list()

    def _populate_lib_list(self) -> None:
        self.lib_list.clear()
        for root in self.main_window.config.content_library_roots:
            self.lib_list.addItem(root)

    def _browse_file(self, line_edit: QLineEdit, title: str, is_dir: bool) -> None:
        start = line_edit.text() or str(Path.home())
        if is_dir:
            path = QFileDialog.getExistingDirectory(self, title, start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, title, start)
        if path:
            line_edit.setText(path)

    def _add_library_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Content Library Directory", str(Path.home())
        )
        if not path:
            return
        existing = {self.lib_list.item(i).text() for i in range(self.lib_list.count())}
        if path not in existing:
            self.lib_list.addItem(path)

    def _remove_library_root(self) -> None:
        current = self.lib_list.currentItem()
        if current:
            self.lib_list.takeItem(self.lib_list.row(current))

    def _save_and_continue(self) -> None:
        config = self.main_window.config
        config.daz_studio_path = self.daz_path.text().strip()
        config.content_library_roots = [
            self.lib_list.item(i).text() for i in range(self.lib_list.count())
        ]
        config.workspace_root = self.workspace_root.text().strip()
        config.kohya_ss_path = self.kohya_path.text().strip()
        config.sdxl_checkpoint_path = self.sdxl_path.text().strip()
        config.comfyui_loras_path = self.comfy_path.text().strip()
        config.renders_per_session = self.renders_per_session.value()
        config.render_width = self.render_width.value()
        config.render_height = self.render_height.value()
        config.render_samples = self.render_samples.value()
        config.update_channel = self.update_channel.currentText()
        config.github_repo = self.github_repo_input.text().strip() or config.github_repo

        if not config.workspace_root:
            QMessageBox.warning(self, "Validation Error", "Workspace root is required.")
            return

        self.main_window.set_config(config)
        self.main_window.navigate_next()
