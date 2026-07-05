from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import Look


class LooksEditorScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._current_look_index: int = -1
        self._suppress_sync: bool = False
        self._build_ui()
        self.main_window.project_changed.connect(self._on_project_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.header_label = QLabel()
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(self.header_label)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)

        left_layout.addWidget(QLabel("Looks"))

        self.look_list = QListWidget()
        self.look_list.currentRowChanged.connect(self._on_look_selected)
        left_layout.addWidget(self.look_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Look")
        add_btn.clicked.connect(self._add_look)
        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._duplicate_look)
        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self._remove_look)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(dup_btn)
        btn_row.addWidget(rem_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        self.details_stack = QStackedWidget()

        self.empty_page = QWidget()
        empty_lo = QVBoxLayout(self.empty_page)
        el = QLabel("Select a Look to edit its details")
        el.setAlignment(Qt.AlignCenter)
        el.setStyleSheet("color: #888; font-size: 14px;")
        empty_lo.addWidget(el)
        self.details_stack.addWidget(self.empty_page)

        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_page = QWidget()
        self.form_layout = QVBoxLayout(self.form_page)
        self.form_scroll.setWidget(self.form_page)
        self.details_stack.addWidget(self.form_scroll)

        right_layout.addWidget(self.details_stack)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        save_btn = QPushButton("Save Looks")
        save_btn.setObjectName("actionBtn")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; color: white; font-weight: bold; padding: 8px 20px; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        save_btn.clicked.connect(self._save_looks)
        continue_btn = QPushButton("Continue to Pose Groups \u2192")
        continue_btn.setObjectName("actionBtn")
        continue_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; color: white; font-weight: bold; padding: 8px 20px; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        continue_btn.clicked.connect(self._continue_forward)
        bottom_row.addWidget(save_btn)
        bottom_row.addWidget(continue_btn)
        layout.addLayout(bottom_row)

    def on_enter(self) -> None:
        self._refresh()

    def _on_project_changed(self, project) -> None:
        self._refresh()

    def _refresh(self) -> None:
        project = self.main_window.current_project
        if project is None:
            self.header_label.setText("No project loaded")
            self.look_list.clear()
            self.details_stack.setCurrentIndex(0)
            return

        char = project.character
        self.header_label.setText(
            f"Character: {char.character_id}  ({char.mode.value})"
        )

        self.look_list.blockSignals(True)
        self._current_look_index = -1
        self.look_list.clear()

        if not project.looks:
            item = QListWidgetItem("Add your first Look")
            item.setFlags(Qt.NoItemFlags)
            item.setData(Qt.UserRole, "__empty__")
            self.look_list.addItem(item)
        else:
            for look in project.looks:
                self._add_list_item(look)

        self.look_list.blockSignals(False)
        self.details_stack.setCurrentIndex(0)

    def _add_list_item(self, look: Look) -> None:
        pg_count = len(look.pose_group_ids or [])
        text = (
            f"{look.trigger_phrase}  "
            f"({len(look.wardrobe_asset_paths)} wardrobe, {pg_count} poses)"
        )
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, look.trigger_phrase)
        self.look_list.addItem(item)

    def _on_look_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self.look_list.item(row)
        if item is None or item.data(Qt.UserRole) == "__empty__":
            self.details_stack.setCurrentIndex(0)
            return

        self._current_look_index = row
        self._build_detail_form(row)

    def _build_detail_form(self, row: int) -> None:
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        project = self.main_window.current_project
        if project is None or row >= len(project.looks):
            self.details_stack.setCurrentIndex(0)
            return

        look = project.looks[row]
        self.details_stack.setCurrentIndex(1)

        trigger_label = QLabel("Trigger Phrase")
        self.form_layout.addWidget(trigger_label)
        trigger_edit = QLineEdit(look.trigger_phrase)
        trigger_edit.textChanged.connect(
            lambda t: self._on_field_changed("trigger", t)
        )
        self.form_layout.addWidget(trigger_edit)

        hair_label = QLabel("Hair Override (optional)")
        self.form_layout.addWidget(hair_label)
        hair_row = QHBoxLayout()
        hair_edit = QLineEdit(look.hair_override_path or "")
        hair_edit.textChanged.connect(
            lambda t: self._on_field_changed("hair", t)
        )
        hair_btn = QPushButton("Browse...")
        hair_btn.clicked.connect(lambda: self._browse_hair(hair_edit))
        hair_row.addWidget(hair_edit)
        hair_row.addWidget(hair_btn)
        self.form_layout.addLayout(hair_row)

        include_cb = QCheckBox("Include in Dataset")
        include_cb.setChecked(look.include_in_dataset)
        include_cb.toggled.connect(
            lambda v: self._on_field_changed("include", v)
        )
        self.form_layout.addWidget(include_cb)

        self.form_layout.addWidget(QLabel("Wardrobe Assets"))
        self._wardrobe_list = QListWidget()
        for w in (look.wardrobe_asset_paths or []):
            self._wardrobe_list.addItem(w)
        self.form_layout.addWidget(self._wardrobe_list)

        w_btn_row = QHBoxLayout()
        add_w_btn = QPushButton("Add...")
        add_w_btn.clicked.connect(self._add_wardrobe)
        rem_w_btn = QPushButton("Remove")
        rem_w_btn.clicked.connect(self._remove_wardrobe)
        w_btn_row.addWidget(add_w_btn)
        w_btn_row.addWidget(rem_w_btn)
        w_btn_row.addStretch()
        self.form_layout.addLayout(w_btn_row)

        self.form_layout.addWidget(QLabel("Assigned Pose Groups"))
        assigned = set(look.pose_group_ids or [])
        pose_groups = project.pose_groups if project else []

        if not pose_groups:
            pg_empty = QLabel(
                "No pose groups defined yet.\n"
                "Add pose groups in the Pose Groups Editor."
            )
            pg_empty.setStyleSheet("color: #888; font-style: italic;")
            pg_empty.setWordWrap(True)
            self.form_layout.addWidget(pg_empty)
        else:
            for pg in pose_groups:
                cb = QCheckBox(pg.display_name or pg.pose_group_id)
                cb.setChecked(pg.pose_group_id in assigned)
                cb.toggled.connect(
                    lambda v, pid=pg.pose_group_id: self._on_pose_group_toggled(pid, v)
                )
                self.form_layout.addWidget(cb)

        self.form_layout.addStretch()

    def _on_field_changed(self, field: str, value) -> None:
        project = self.main_window.current_project
        if project is None or self._current_look_index < 0:
            return
        if self._current_look_index >= len(project.looks):
            return
        look = project.looks[self._current_look_index]
        if field == "trigger":
            look.trigger_phrase = value
            self._sync_list_item()
        elif field == "hair":
            look.hair_override_path = value if value else None
        elif field == "include":
            look.include_in_dataset = bool(value)

    def _on_pose_group_toggled(self, pg_id: str, checked: bool) -> None:
        project = self.main_window.current_project
        if project is None or self._current_look_index < 0:
            return
        if self._current_look_index >= len(project.looks):
            return
        look = project.looks[self._current_look_index]
        if look.pose_group_ids is None:
            look.pose_group_ids = []
        if checked and pg_id not in look.pose_group_ids:
            look.pose_group_ids.append(pg_id)
        elif not checked and pg_id in look.pose_group_ids:
            look.pose_group_ids.remove(pg_id)
        self._sync_list_item()

    def _add_wardrobe(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Wardrobe Assets", str(Path.home()),
            "DAZ Files (*.duf);;All Files (*)"
        )
        if not paths:
            return
        existing = {self._wardrobe_list.item(i).text()
                     for i in range(self._wardrobe_list.count())}
        for p in paths:
            if p not in existing:
                self._wardrobe_list.addItem(p)
        self._sync_wardrobe()

    def _remove_wardrobe(self) -> None:
        current = self._wardrobe_list.currentItem()
        if current:
            self._wardrobe_list.takeItem(self._wardrobe_list.row(current))
            self._sync_wardrobe()

    def _sync_wardrobe(self) -> None:
        project = self.main_window.current_project
        if project is None or self._current_look_index < 0:
            return
        if self._current_look_index >= len(project.looks):
            return
        look = project.looks[self._current_look_index]
        look.wardrobe_asset_paths = [
            self._wardrobe_list.item(i).text()
            for i in range(self._wardrobe_list.count())
        ]
        self._sync_list_item()

    def _sync_list_item(self) -> None:
        project = self.main_window.current_project
        if project is None or self._current_look_index < 0:
            return
        if self._current_look_index >= len(project.looks):
            return
        look = project.looks[self._current_look_index]
        item = self.look_list.item(self._current_look_index)
        if item:
            pg_count = len(look.pose_group_ids or [])
            item.setText(
                f"{look.trigger_phrase}  "
                f"({len(look.wardrobe_asset_paths)} wardrobe, {pg_count} poses)"
            )

    def _browse_hair(self, line_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Hair Asset", str(Path.home()),
            "DAZ Files (*.duf);;All Files (*)"
        )
        if path:
            line_edit.setText(path)

    def _add_look(self) -> None:
        project = self.main_window.current_project
        if project is None:
            QMessageBox.warning(self, "No Project", "No project is currently loaded.")
            return

        base = "new look"
        trigger = base
        counter = 1
        while any(l.trigger_phrase == trigger for l in project.looks):
            counter += 1
            trigger = f"{base} {counter}"

        look = Look(trigger_phrase=trigger)
        project.looks.append(look)

        self.look_list.blockSignals(True)
        self._add_list_item(look)
        self.look_list.blockSignals(False)
        self.look_list.setCurrentRow(self.look_list.count() - 1)
        self.details_stack.setCurrentIndex(0)
        self._build_detail_form(self.look_list.count() - 1)
        self.details_stack.setCurrentIndex(1)

    def _duplicate_look(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return
        row = self.look_list.currentRow()
        if row < 0:
            return
        if row >= len(project.looks):
            return

        source = project.looks[row]
        new_look = copy.deepcopy(source)

        base = source.trigger_phrase
        counter = 1
        while any(l.trigger_phrase == new_look.trigger_phrase for l in project.looks):
            counter += 1
            new_look.trigger_phrase = f"{base} (copy {counter})"

        project.looks.append(new_look)
        self.look_list.blockSignals(True)
        self._add_list_item(new_look)
        self.look_list.blockSignals(False)
        self.look_list.setCurrentRow(self.look_list.count() - 1)

    def _remove_look(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return
        row = self.look_list.currentRow()
        if row < 0 or row >= len(project.looks):
            return

        look = project.looks[row]
        reply = QMessageBox.question(
            self, "Remove Look",
            f"Remove Look '{look.trigger_phrase}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        del project.looks[row]
        self.look_list.blockSignals(True)
        self.look_list.takeItem(row)
        self.look_list.blockSignals(False)

        self._current_look_index = -1
        if not project.looks:
            item = QListWidgetItem("Add your first Look")
            item.setFlags(Qt.NoItemFlags)
            item.setData(Qt.UserRole, "__empty__")
            self.look_list.addItem(item)

        self.details_stack.setCurrentIndex(0)

    def _save_looks(self) -> None:
        project = self.main_window.current_project
        if project is None:
            QMessageBox.warning(self, "No Project", "No project is currently loaded.")
            return

        ws = Path(self.main_window.config.workspace_root)
        proj_file = ws / "projects" / project.project_id / "project.json"
        project.save(proj_file)
        QMessageBox.information(self, "Saved", f"Looks saved to project file.")

    def _continue_forward(self) -> None:
        self._save_looks()
        self.main_window.navigate_to(4)
