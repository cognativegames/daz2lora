from __future__ import annotations

import copy
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import (
    HARDCODED_CAMERAS, HARDCODED_LIGHTING, DEFAULT_CAMERA_PROFILES,
    CameraProfile, PoseGroup,
)


class PoseGroupsEditorScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._current_pg_index: int = -1
        self._build_ui()
        self.main_window.project_changed.connect(self._on_project_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.header_label = QLabel()
        self.header_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin-bottom: 8px;"
        )
        layout.addWidget(self.header_label)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.addWidget(QLabel("Pose Groups"))

        self.pg_list = QListWidget()
        self.pg_list.currentRowChanged.connect(self._on_pg_selected)
        left_layout.addWidget(self.pg_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Group")
        add_btn.clicked.connect(self._add_pg)
        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._duplicate_pg)
        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self._remove_pg)
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
        el = QLabel("Select a Pose Group to edit its details")
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
        save_btn = QPushButton("Save Pose Groups")
        save_btn.setObjectName("actionBtn")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; color: white; font-weight: bold; padding: 8px 20px; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        save_btn.clicked.connect(self._save_pgs)
        continue_btn = QPushButton("Continue to Review & Render \u2192")
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
            self.pg_list.clear()
            self.details_stack.setCurrentIndex(0)
            return

        self.header_label.setText("Pose Groups Editor")

        self.pg_list.blockSignals(True)
        self._current_pg_index = -1
        self.pg_list.clear()

        if not project.pose_groups:
            item = QListWidgetItem("Add your first Pose Group")
            item.setFlags(Qt.NoItemFlags)
            item.setData(Qt.UserRole, "__empty__")
            self.pg_list.addItem(item)
        else:
            for pg in project.pose_groups:
                self._add_list_item(pg)

        self.pg_list.blockSignals(False)
        self.details_stack.setCurrentIndex(0)

    def _add_list_item(self, pg: PoseGroup) -> None:
        camera_name = self._camera_profile_display(pg.assigned_camera_profile)
        text = (
            f"{pg.display_name or pg.pose_group_id}  "
            f"({len(pg.pose_asset_paths)} poses, {camera_name})"
        )
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, pg.pose_group_id)
        self.pg_list.addItem(item)

    def _camera_profile_display(self, profile_id: str) -> str:
        project = self.main_window.current_project
        if project:
            for cp in project.camera_profiles:
                if cp.camera_profile_id == profile_id:
                    return cp.camera_profile_id
        for cp in DEFAULT_CAMERA_PROFILES:
            if cp.camera_profile_id == profile_id:
                return cp.camera_profile_id
        return profile_id

    def _on_pg_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self.pg_list.item(row)
        if item is None or item.data(Qt.UserRole) == "__empty__":
            self.details_stack.setCurrentIndex(0)
            return

        self._current_pg_index = row
        self._build_detail_form(row)

    def _build_detail_form(self, row: int) -> None:
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        project = self.main_window.current_project
        if project is None or row >= len(project.pose_groups):
            self.details_stack.setCurrentIndex(0)
            return

        pg = project.pose_groups[row]
        self.details_stack.setCurrentIndex(1)

        self._id_edit = QLineEdit(pg.pose_group_id)
        self._id_edit.textChanged.connect(lambda t: self._on_id_changed(t, row))
        self.form_layout.addWidget(QLabel("Pose Group ID"))
        self.form_layout.addWidget(self._id_edit)

        self._name_edit = QLineEdit(pg.display_name)
        self._name_edit.textChanged.connect(lambda t: self._on_name_changed(t, row))
        self.form_layout.addWidget(QLabel("Display Name"))
        self.form_layout.addWidget(self._name_edit)

        self.form_layout.addWidget(QLabel("Pose Assets"))
        self._pose_asset_list = QListWidget()
        for pa in (pg.pose_asset_paths or []):
            item = QListWidgetItem(Path(pa).name)
            item.setToolTip(pa)
            self._pose_asset_list.addItem(item)
        self.form_layout.addWidget(self._pose_asset_list)

        pa_btn_row = QHBoxLayout()
        add_pa_btn = QPushButton("Add...")
        add_pa_btn.clicked.connect(self._add_pose_asset)
        rem_pa_btn = QPushButton("Remove")
        rem_pa_btn.clicked.connect(self._remove_pose_asset)
        pa_btn_row.addWidget(add_pa_btn)
        pa_btn_row.addWidget(rem_pa_btn)
        pa_btn_row.addStretch()
        self.form_layout.addLayout(pa_btn_row)

        self.form_layout.addWidget(QLabel("Camera Profile"))
        self._cp_combo = QComboBox()
        self._populate_camera_profiles(pg, row)
        self._cp_combo.currentIndexChanged.connect(
            lambda idx: self._on_cp_changed(idx, row)
        )
        self.form_layout.addWidget(self._cp_combo)

        self._override_toggle = QPushButton(
            "Advanced Override \u25BC" if (pg.camera_overrides or pg.lighting_overrides)
            else "Advanced Override \u25B6"
        )
        self._override_toggle.setCheckable(True)
        self._override_toggle.setChecked(
            bool(pg.camera_overrides) or bool(pg.lighting_overrides)
        )
        self._override_toggle.toggled.connect(self._toggle_override)
        self.form_layout.addWidget(self._override_toggle)

        self._override_section = QWidget()
        self._override_section.setVisible(self._override_toggle.isChecked())
        ov_layout = QVBoxLayout(self._override_section)
        ov_layout.setContentsMargins(0, 0, 0, 0)

        ov_layout.addWidget(QLabel("Camera Overrides"))
        self._cam_checkboxes = {}
        for cam in HARDCODED_CAMERAS:
            cb = QCheckBox(f"{cam.id}  ({cam.description})")
            cb.setChecked(
                pg.camera_overrides is not None and cam.id in pg.camera_overrides
            )
            cb.toggled.connect(
                lambda v, cid=cam.id: self._on_override_cam_toggled(cid, v, row)
            )
            ov_layout.addWidget(cb)
            self._cam_checkboxes[cam.id] = cb

        ov_layout.addWidget(QLabel("Lighting Overrides"))
        self._light_checkboxes = {}
        for light in HARDCODED_LIGHTING:
            cb = QCheckBox(f"{light.id}  ({light.description})")
            cb.setChecked(
                pg.lighting_overrides is not None and light.id in pg.lighting_overrides
            )
            cb.toggled.connect(
                lambda v, lid=light.id: self._on_override_light_toggled(lid, v, row)
            )
            ov_layout.addWidget(cb)
            self._light_checkboxes[light.id] = cb

        ov_layout.addStretch()
        self.form_layout.addWidget(self._override_section)
        self.form_layout.addStretch()

    def _populate_camera_profiles(self, pg: PoseGroup, row: int) -> None:
        self._cp_combo.blockSignals(True)
        self._cp_combo.clear()

        project = self.main_window.current_project
        all_profiles: list[CameraProfile] = []
        seen_ids: set[str] = set()

        if project:
            for cp in project.camera_profiles:
                if cp.camera_profile_id not in seen_ids:
                    all_profiles.append(cp)
                    seen_ids.add(cp.camera_profile_id)

        for cp in DEFAULT_CAMERA_PROFILES:
            if cp.camera_profile_id not in seen_ids:
                all_profiles.append(cp)
                seen_ids.add(cp.camera_profile_id)

        has_overrides = bool(pg.camera_overrides) or bool(pg.lighting_overrides)

        if has_overrides:
            self._cp_combo.addItem("Custom (overrides active)", "__custom_override__")

        for cp in all_profiles:
            self._cp_combo.addItem(cp.camera_profile_id, cp.camera_profile_id)

        if has_overrides:
            self._cp_combo.setCurrentIndex(0)
        else:
            idx = self._cp_combo.findData(pg.assigned_camera_profile)
            if idx >= 0:
                self._cp_combo.setCurrentIndex(idx)
            elif self._cp_combo.count() > (1 if has_overrides else 0):
                self._cp_combo.setCurrentIndex(1 if has_overrides else 0)

        self._cp_combo.blockSignals(False)

    def _toggle_override(self, checked: bool) -> None:
        self._override_section.setVisible(checked)
        self._override_toggle.setText(
            "Advanced Override \u25BC" if checked else "Advanced Override \u25B6"
        )
        row = self._current_pg_index
        project = self.main_window.current_project
        if row < 0 or project is None or row >= len(project.pose_groups):
            return
        pg = project.pose_groups[row]
        if not checked:
            pg.camera_overrides = None
            pg.lighting_overrides = None
            self._populate_camera_profiles(pg, row)
            self._sync_list_item(row)

    def _on_override_cam_toggled(self, cam_id: str, checked: bool, row: int) -> None:
        project = self.main_window.current_project
        if row < 0 or project is None or row >= len(project.pose_groups):
            return
        pg = project.pose_groups[row]
        overrides = set(pg.camera_overrides or [])
        if checked:
            overrides.add(cam_id)
        else:
            overrides.discard(cam_id)
        pg.camera_overrides = sorted(overrides) if overrides else None
        if pg.camera_overrides or pg.lighting_overrides:
            self._populate_camera_profiles(pg, row)
        else:
            pg.camera_overrides = None
            pg.lighting_overrides = None
            self._populate_camera_profiles(pg, row)
        self._sync_list_item(row)

    def _on_override_light_toggled(self, light_id: str, checked: bool, row: int) -> None:
        project = self.main_window.current_project
        if row < 0 or project is None or row >= len(project.pose_groups):
            return
        pg = project.pose_groups[row]
        overrides = set(pg.lighting_overrides or [])
        if checked:
            overrides.add(light_id)
        else:
            overrides.discard(light_id)
        pg.lighting_overrides = sorted(overrides) if overrides else None
        if pg.camera_overrides or pg.lighting_overrides:
            self._populate_camera_profiles(pg, row)
        else:
            pg.camera_overrides = None
            pg.lighting_overrides = None
            self._populate_camera_profiles(pg, row)
        self._sync_list_item(row)

    def _on_cp_changed(self, idx: int, row: int) -> None:
        project = self.main_window.current_project
        if row < 0 or project is None or row >= len(project.pose_groups):
            return
        pg = project.pose_groups[row]
        profile_id = self._cp_combo.itemData(idx)
        if profile_id == "__custom_override__":
            return
        pg.assigned_camera_profile = profile_id
        pg.camera_overrides = None
        pg.lighting_overrides = None
        self._override_toggle.setChecked(False)
        self._override_section.setVisible(False)
        self._override_toggle.setText("Advanced Override \u25B6")
        self._sync_list_item(row)

    def _on_id_changed(self, text: str, row: int) -> None:
        project = self.main_window.current_project
        if project is None or row < 0 or row >= len(project.pose_groups):
            return
        project.pose_groups[row].pose_group_id = text
        self._sync_list_item(row)

    def _on_name_changed(self, text: str, row: int) -> None:
        project = self.main_window.current_project
        if project is None or row < 0 or row >= len(project.pose_groups):
            return
        pg = project.pose_groups[row]
        pg.display_name = text
        auto_id = self._generate_id(text, pg.pose_group_id)
        pg.pose_group_id = auto_id
        self._id_edit.blockSignals(True)
        self._id_edit.setText(auto_id)
        self._id_edit.blockSignals(False)
        self._sync_list_item(row)

    def _generate_id(self, display_name: str, current_id: str = "") -> str:
        s = display_name.lower().strip()
        s = re.sub(r"[^a-z0-9_]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        if not s:
            s = "pose_group"
        project = self.main_window.current_project
        existing = set()
        if project:
            for pg in project.pose_groups:
                if pg.pose_group_id != current_id:
                    existing.add(pg.pose_group_id)
        base = s
        counter = 1
        while s in existing:
            s = f"{base}_{counter}"
            counter += 1
        return s

    def _add_pose_asset(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Pose Assets", str(Path.home()),
            "DAZ Files (*.duf);;All Files (*)"
        )
        if not paths:
            return
        existing = {
            self._pose_asset_list.item(i).toolTip()
            for i in range(self._pose_asset_list.count())
        }
        for p in paths:
            if p not in existing:
                item = QListWidgetItem(Path(p).name)
                item.setToolTip(p)
                self._pose_asset_list.addItem(item)
        self._sync_pose_assets()

    def _remove_pose_asset(self) -> None:
        current = self._pose_asset_list.currentItem()
        if current:
            self._pose_asset_list.takeItem(self._pose_asset_list.row(current))
            self._sync_pose_assets()

    def _sync_pose_assets(self) -> None:
        project = self.main_window.current_project
        if project is None or self._current_pg_index < 0:
            return
        if self._current_pg_index >= len(project.pose_groups):
            return
        pg = project.pose_groups[self._current_pg_index]
        pg.pose_asset_paths = [
            self._pose_asset_list.item(i).toolTip()
            for i in range(self._pose_asset_list.count())
        ]
        self._sync_list_item(self._current_pg_index)

    def _sync_list_item(self, row: int) -> None:
        project = self.main_window.current_project
        if project is None or row < 0 or row >= len(project.pose_groups):
            return
        pg = project.pose_groups[row]
        item = self.pg_list.item(row)
        if item:
            camera_name = self._camera_profile_display(pg.assigned_camera_profile)
            item.setText(
                f"{pg.display_name or pg.pose_group_id}  "
                f"({len(pg.pose_asset_paths)} poses, {camera_name})"
            )

    def _add_pg(self) -> None:
        project = self.main_window.current_project
        if project is None:
            QMessageBox.warning(self, "No Project", "No project is currently loaded.")
            return

        pg = PoseGroup(
            pose_group_id="new_pose_group",
            display_name="New Pose Group",
        )
        project.pose_groups.append(pg)

        self.pg_list.blockSignals(True)
        self._add_list_item(pg)
        self.pg_list.blockSignals(False)
        self.pg_list.setCurrentRow(self.pg_list.count() - 1)
        self.details_stack.setCurrentIndex(0)
        self._build_detail_form(self.pg_list.count() - 1)
        self.details_stack.setCurrentIndex(1)

    def _duplicate_pg(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return
        row = self.pg_list.currentRow()
        if row < 0 or row >= len(project.pose_groups):
            return

        source = project.pose_groups[row]
        new_pg = copy.deepcopy(source)

        base_id = source.pose_group_id
        counter = 1
        while any(pg.pose_group_id == new_pg.pose_group_id for pg in project.pose_groups):
            counter += 1
            new_pg.pose_group_id = f"{base_id}_{counter}"
            new_pg.display_name = f"{source.display_name} (Copy {counter})"

        project.pose_groups.append(new_pg)
        self.pg_list.blockSignals(True)
        self._add_list_item(new_pg)
        self.pg_list.blockSignals(False)
        self.pg_list.setCurrentRow(self.pg_list.count() - 1)

    def _remove_pg(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return
        row = self.pg_list.currentRow()
        if row < 0 or row >= len(project.pose_groups):
            return

        pg = project.pose_groups[row]
        reply = QMessageBox.question(
            self, "Remove Pose Group",
            f"Remove pose group '{pg.display_name or pg.pose_group_id}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        del project.pose_groups[row]
        self.pg_list.blockSignals(True)
        self.pg_list.takeItem(row)
        self.pg_list.blockSignals(False)

        self._current_pg_index = -1
        if not project.pose_groups:
            item = QListWidgetItem("Add your first Pose Group")
            item.setFlags(Qt.NoItemFlags)
            item.setData(Qt.UserRole, "__empty__")
            self.pg_list.addItem(item)

        self.details_stack.setCurrentIndex(0)

    def _save_pgs(self) -> None:
        project = self.main_window.current_project
        if project is None:
            QMessageBox.warning(self, "No Project", "No project is currently loaded.")
            return

        ws = Path(self.main_window.config.workspace_root)
        proj_file = ws / "projects" / project.project_id / "project.json"
        project.save(proj_file)
        QMessageBox.information(self, "Saved", "Pose groups saved to project file.")

    def _continue_forward(self) -> None:
        self._save_pgs()
        self.main_window.navigate_to(5)
