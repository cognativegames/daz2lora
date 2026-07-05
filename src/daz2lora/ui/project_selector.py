from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import CharacterMode, CharacterProject


class ProjectSelectorScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._project_items: list[tuple[QListWidgetItem, CharacterProject]] = []
        self._build_ui()
        self.main_window.config_changed.connect(self._on_config_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Character Projects")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self.empty_label = QLabel(
            "No projects found.\nCreate a new character project to get started."
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 14px; color: #888; padding: 60px;")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.project_list = QListWidget()
        self.project_list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self.project_list)

        btn_layout = QHBoxLayout()

        self.new_btn = QPushButton("New Character Project")
        self.new_btn.clicked.connect(self._on_new_project)
        btn_layout.addWidget(self.new_btn)

        self.open_btn = QPushButton("Open Selected Project")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._on_open_project)
        btn_layout.addWidget(self.open_btn)

        self.delete_btn = QPushButton("Delete Project")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_project)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def on_enter(self) -> None:
        self._scan_projects()

    def _on_config_changed(self, config) -> None:
        self._scan_projects()

    def _scan_projects(self) -> None:
        self.project_list.clear()
        self._project_items.clear()

        ws = Path(self.main_window.config.workspace_root)
        projects_dir = ws / "projects"

        if not projects_dir.exists():
            self.empty_label.setVisible(True)
            self.project_list.setVisible(False)
            self.open_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return

        found = False
        for proj_dir in sorted(projects_dir.iterdir()):
            if not proj_dir.is_dir():
                continue
            proj_file = proj_dir / "project.json"
            if not proj_file.exists():
                continue
            try:
                project = CharacterProject.load(proj_file)
                self._add_list_item(project)
                found = True
            except Exception as e:
                print(f"Failed to load project {proj_file}: {e}")

        has_projects = found
        self.empty_label.setVisible(not has_projects)
        self.project_list.setVisible(has_projects)
        self.open_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

    def _add_list_item(self, project: CharacterProject) -> None:
        char = project.character
        mode = "Modular" if char.mode == CharacterMode.MODULAR else "Fixed"
        lora_status = "Yes" if project.trained_lora_path else "No"
        text = (
            f"{char.character_id}  |  {mode}  |  "
            f"{len(project.looks)} Look{'s' if len(project.looks) != 1 else ''}  |  "
            f"LoRA: {lora_status}"
        )
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, project.project_id)
        self.project_list.addItem(item)
        self._project_items.append((item, project))

    def _on_selection_changed(self, row: int) -> None:
        has_selection = row >= 0 and row < len(self._project_items)
        self.open_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _on_new_project(self) -> None:
        self.main_window.navigate_to(2)

    def _on_open_project(self) -> None:
        row = self.project_list.currentRow()
        if row < 0 or row >= len(self._project_items):
            return
        _, project = self._project_items[row]
        self.main_window.set_project(project)

        if project.character.mode == CharacterMode.MODULAR:
            self.main_window.navigate_to(3)
        else:
            self.main_window.navigate_to(4)

    def _on_delete_project(self) -> None:
        row = self.project_list.currentRow()
        if row < 0 or row >= len(self._project_items):
            return
        _, project = self._project_items[row]

        reply = QMessageBox.question(
            self,
            "Delete Project",
            f"Delete '{project.character.character_id}'?\n\n"
            f"All project files will be permanently removed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        proj_dir = Path(self.main_window.config.workspace_root) / "projects" / project.project_id
        try:
            shutil.rmtree(proj_dir)
            self._scan_projects()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete project: {e}")

    @property
    def project_items(self) -> list[tuple[QListWidgetItem, CharacterProject]]:
        return self._project_items
