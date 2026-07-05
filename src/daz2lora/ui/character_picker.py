from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import Character, CharacterMode, CharacterProject


class CharacterPickerScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("New Character")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self._build_identity_group(layout)
        self._build_mode_group(layout)
        self._build_assets_group(layout)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.create_btn = QPushButton("Create Project")
        self.create_btn.setObjectName("actionBtn")
        self.create_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; color: white; font-weight: bold; padding: 8px 24px; font-size: 14px; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        self.create_btn.clicked.connect(self._create_project)
        btn_layout.addWidget(self.create_btn)
        layout.addLayout(btn_layout)

    def _build_identity_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Character Identity")
        form = QFormLayout(group)

        self.char_id = QLineEdit()
        self.char_id.setPlaceholderText("e.g. kelly")
        form.addRow("Character ID:", self.char_id)

        self.trigger_word = QLineEdit()
        self.trigger_word.setPlaceholderText("e.g. kelly")
        form.addRow("Base Trigger Word:", self.trigger_word)

        self.static_tags = QLineEdit()
        self.static_tags.setPlaceholderText("e.g. female, human, realistic")
        form.addRow("Static Tags:", self.static_tags)

        layout.addWidget(group)

    def _build_mode_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(group)

        self.modular_radio = QRadioButton("Modular")
        self.modular_radio.setChecked(True)
        mode_layout.addWidget(self.modular_radio)

        mod_desc = QLabel(
            "Character loads nude. Looks define outfits. Recommended for most use cases."
        )
        mod_desc.setStyleSheet("color: #888; font-size: 12px; margin-left: 20px;")
        mod_desc.setWordWrap(True)
        mode_layout.addWidget(mod_desc)

        self.fixed_radio = QRadioButton("Fixed")
        mode_layout.addWidget(self.fixed_radio)

        fix_desc = QLabel("Character is already fully dressed as authored. Skip Looks editor.")
        fix_desc.setStyleSheet("color: #888; font-size: 12px; margin-left: 20px;")
        fix_desc.setWordWrap(True)
        mode_layout.addWidget(fix_desc)

        layout.addWidget(group)

    def _build_assets_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Figure Assets")
        form = QFormLayout(group)

        self.figure_path = self._make_browse_row(form, "Figure Asset:", "Select .duf Figure File", False)
        self.shape_path = self._make_browse_row(form, "Shape Preset:", "Select .duf Shape Preset", False)
        self.skin_path = self._make_browse_row(form, "Skin Material:", "Select .duf Skin Material", False)
        self.hair_path = self._make_browse_row(form, "Default Hair:", "Select .duf Hair File", False)

        layout.addWidget(group)

    def _make_browse_row(
        self, form: QFormLayout, label: str, dialog_title: str, is_dir: bool
    ) -> QLineEdit:
        line_edit = QLineEdit()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_duf(line_edit, dialog_title))
        row = QHBoxLayout()
        row.addWidget(line_edit)
        row.addWidget(browse_btn)
        form.addRow(label, row)
        return line_edit

    def _browse_duf(self, line_edit: QLineEdit, title: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, title, str(Path.home()), "DAZ Files (*.duf);;All Files (*)"
        )
        if path:
            line_edit.setText(path)

    def _create_project(self) -> None:
        char_id = self.char_id.text().strip()
        trigger = self.trigger_word.text().strip().lower()
        tags_text = self.static_tags.text().strip()
        figure = self.figure_path.text().strip()
        shape = self.shape_path.text().strip()
        skin = self.skin_path.text().strip()
        hair = self.hair_path.text().strip()

        if not char_id:
            QMessageBox.warning(self, "Validation Error", "Character ID is required.")
            self.char_id.setFocus()
            return
        if not re.match(r"^[a-zA-Z0-9_]+$", char_id):
            QMessageBox.warning(
                self, "Validation Error", "Character ID must be alphanumeric + underscores only."
            )
            self.char_id.setFocus()
            return
        if not trigger:
            QMessageBox.warning(self, "Validation Error", "Base trigger word is required.")
            self.trigger_word.setFocus()
            return
        if not re.match(r"^[a-z]+$", trigger):
            QMessageBox.warning(
                self, "Validation Error", "Trigger word must be a single lowercase word."
            )
            self.trigger_word.setFocus()
            return
        if not figure:
            QMessageBox.warning(self, "Validation Error", "Figure asset path is required.")
            return
        if not shape:
            QMessageBox.warning(self, "Validation Error", "Shape preset path is required.")
            return
        if not skin:
            QMessageBox.warning(self, "Validation Error", "Skin material path is required.")
            return

        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []
        mode = CharacterMode.FIXED if self.fixed_radio.isChecked() else CharacterMode.MODULAR

        character = Character(
            character_id=char_id,
            base_trigger_word=trigger,
            figure_asset_path=figure,
            shape_preset_path=shape,
            skin_material_path=skin,
            default_hair_asset_path=hair,
            mode=mode,
            static_tags=tags,
        )

        project = CharacterProject(
            project_id=char_id,
            character=character,
        )

        ws = Path(self.main_window.config.workspace_root)
        proj_dir = ws / "projects" / char_id
        proj_dir.mkdir(parents=True, exist_ok=True)
        project.save(proj_dir / "project.json")

        self.main_window.set_project(project)

        if mode == CharacterMode.MODULAR:
            self.main_window.navigate_to(3)
        else:
            self.main_window.navigate_to(4)

    def on_enter(self) -> None:
        self.char_id.clear()
        self.trigger_word.clear()
        self.static_tags.clear()
        self.figure_path.clear()
        self.shape_path.clear()
        self.skin_path.clear()
        self.hair_path.clear()
        self.modular_radio.setChecked(True)
