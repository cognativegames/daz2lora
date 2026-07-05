from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import DEFAULT_CAMERA_PROFILES
from daz2lora.utils.daz_orchestrator import (
    _build_daz_command, _get_args_dir, _get_script_path, tail_progress,
)
from daz2lora.utils.render_math import (
    compute_render_counts, estimate_render_time, validate_render_counts,
)

GREEN = QColor(70, 180, 70)
RED = QColor(220, 60, 60)


class RenderWorker(QObject):
    progress_signal = Signal(dict)
    finished_signal = Signal(int)

    def __init__(self, job_config, config):
        super().__init__()
        self._job_config = job_config
        self._config = config
        self._cancel_event = threading.Event()
        self._process = None

    def run(self):
        try:
            result = self._run_job()
            self.finished_signal.emit(result)
        except Exception as e:
            self.finished_signal.emit(-1)

    def cancel(self):
        self._cancel_event.set()
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                pass
            if self._process and self._process.poll() is None:
                try:
                    self._process.kill()
                except Exception:
                    pass

    def _run_job(self) -> int:
        total = self._count_renders()
        per_session = self._config.renders_per_session
        if total > per_session:
            return self._run_split_sessions()
        return self._run_single_session(self._job_config)

    def _run_single_session(self, job_config: dict) -> int:
        script_path = _get_script_path("master_render.dsa")
        args_dir = _get_args_dir(self._config)
        session_id = str(int(time.time()))

        job_config["session_id"] = session_id
        job_config["progress_log"] = str(args_dir / f"progress_{session_id}.log")
        job_path = args_dir / f"job_{session_id}.json"
        job_path.write_text(json.dumps(job_config, indent=2))

        cmd = _build_daz_command(
            self._config.daz_studio_path, str(script_path), str(job_path)
        )

        tail_thread = threading.Thread(
            target=tail_progress,
            args=(
                job_config["progress_log"],
                lambda d: self.progress_signal.emit(d),
                self._cancel_event,
            ),
            daemon=True,
        )
        tail_thread.start()

        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = self._process.communicate()
            return self._process.returncode
        finally:
            self._cancel_event.set()
            tail_thread.join(timeout=2)

    def _run_split_sessions(self) -> int:
        looks = self._job_config.get("looks", [])
        per_session = self._config.renders_per_session
        current_look_list: list[dict] = []
        current_count = 0
        session_num = 0
        overall_exit = 0

        for look in looks:
            look_count = self._count_renders_for_look(look)
            if current_count + look_count > per_session and current_look_list:
                session_num += 1
                session_job = dict(self._job_config)
                session_job["looks"] = current_look_list
                session_job["session_num"] = session_num
                ec = self._run_single_session(session_job)
                if ec != 0:
                    overall_exit = ec
                current_look_list = []
                current_count = 0

            current_look_list.append(look)
            current_count += look_count

        if current_look_list:
            session_num += 1
            session_job = dict(self._job_config)
            session_job["looks"] = current_look_list
            session_job["session_num"] = session_num
            ec = self._run_single_session(session_job)
            if ec != 0:
                overall_exit = ec

        return overall_exit

    def _count_renders(self) -> int:
        total = 0
        for look in self._job_config.get("looks", []):
            total += self._count_renders_for_look(look)
        return total

    def _count_renders_for_look(self, look: dict) -> int:
        pose_groups = {
            pg["pose_group_id"]: pg
            for pg in self._job_config.get("pose_groups", [])
        }
        camera_profiles = self._job_config.get("camera_profiles", {})
        total = 0
        for pg_id in look.get("pose_group_ids", []):
            pg = pose_groups.get(pg_id)
            if pg is None:
                continue
            cameras = pg.get("camera_overrides")
            if not cameras:
                profile = camera_profiles.get(
                    pg.get("assigned_camera_profile", "full_coverage"), {}
                )
                cameras = profile.get("cameras", [])
            lighting = pg.get("lighting_overrides")
            if not lighting:
                profile = camera_profiles.get(
                    pg.get("assigned_camera_profile", "full_coverage"), {}
                )
                lighting = profile.get("lighting", [])
            total += (
                len(pg.get("pose_asset_paths", []))
                * len(cameras)
                * len(lighting)
            )
        return total


class RenderScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._render_rows: list[dict] = []
        self._total_render_count: int = 0
        self._completed_count: int = 0
        self._failed_count: int = 0
        self._start_time: float | None = None
        self._thread: QThread | None = None
        self._worker: RenderWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.header_label = QLabel()
        self.header_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; margin-bottom: 4px;"
        )
        layout.addWidget(self.header_label)

        self.sub_header = QLabel()
        self.sub_header.setStyleSheet(
            "font-size: 13px; color: #999; margin-bottom: 12px;"
        )
        layout.addWidget(self.sub_header)

        summary_box = QGroupBox("Render Summary")
        summary_layout = QVBoxLayout(summary_box)

        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(6)
        self.summary_table.setHorizontalHeaderLabels(
            ["Look", "Pose Groups", "Poses", "Cameras", "Lighting", "Total Images"]
        )
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.summary_table.setSelectionMode(QTableWidget.NoSelection)
        summary_layout.addWidget(self.summary_table)

        totals_row = QHBoxLayout()
        self.total_label = QLabel("Total: 0 images")
        self.total_label.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #ccc; padding: 4px 0;"
        )
        totals_row.addWidget(self.total_label)
        totals_row.addStretch()
        self.est_time_label = QLabel("Estimated time: --")
        self.est_time_label.setStyleSheet(
            "font-size: 13px; color: #999; padding: 4px 0;"
        )
        totals_row.addWidget(self.est_time_label)
        summary_layout.addLayout(totals_row)

        layout.addWidget(summary_box)

        self.validation_box = QGroupBox("Validation")
        self.validation_layout = QVBoxLayout(self.validation_box)
        self.validation_label = QLabel()
        self.validation_layout.addWidget(self.validation_label)
        layout.addWidget(self.validation_box)

        preview_box = QGroupBox("Render Job Config Preview")
        preview_box.setCheckable(True)
        preview_box.setChecked(False)
        preview_box.toggled.connect(
            lambda checked: self._job_preview_area.setVisible(checked)
        )
        preview_layout = QVBoxLayout(preview_box)
        self._job_preview_area = QPlainTextEdit()
        self._job_preview_area.setReadOnly(True)
        self._job_preview_area.setMaximumHeight(300)
        self._job_preview_area.setStyleSheet(
            "background-color: #1a1a1a; color: #b8b8b8; font-family: monospace; font-size: 11px;"
        )
        preview_layout.addWidget(self._job_preview_area)
        layout.addWidget(preview_box)

        controls_box = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_box)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Render")
        self.start_btn.setObjectName("startRenderBtn")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #2a8a2a; border-color: #2a8a2a; "
            "color: white; font-weight: bold; padding: 10px 30px; font-size: 15px; }"
            "QPushButton:hover { background-color: #33a033; }"
            "QPushButton:disabled { background-color: #1a4a1a; color: #666; border-color: #333; }"
        )
        self.start_btn.clicked.connect(self._start_render)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_render)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        controls_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_label = QLabel("0 / 0 renders")
        self.progress_label.setStyleSheet("font-size: 13px; color: #aaa;")
        controls_layout.addWidget(self.progress_bar)
        controls_layout.addWidget(self.progress_label)

        layout.addWidget(controls_box)

        progress_box = QGroupBox("Live Progress")
        progress_layout = QVBoxLayout(progress_box)

        self.progress_table = QTableWidget()
        self.progress_table.setColumnCount(6)
        self.progress_table.setHorizontalHeaderLabels(
            ["#", "Look", "Pose", "Camera", "Lighting", "Status"]
        )
        self.progress_table.horizontalHeader().setStretchLastSection(True)
        self.progress_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.progress_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.progress_table.setSelectionMode(QTableWidget.NoSelection)
        progress_layout.addWidget(self.progress_table)

        layout.addWidget(progress_box)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(
            "font-size: 13px; color: #999; padding: 4px 0;"
        )
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        self.elapsed_label = QLabel("Elapsed: --")
        self.elapsed_label.setStyleSheet("font-size: 13px; color: #999;")
        status_row.addWidget(self.elapsed_label)
        status_row.addSpacing(16)
        self.remaining_label = QLabel("Remaining: --")
        self.remaining_label.setStyleSheet("font-size: 13px; color: #999;")
        status_row.addWidget(self.remaining_label)
        layout.addLayout(status_row)

        continue_row = QHBoxLayout()
        continue_row.addStretch()
        self.continue_btn = QPushButton("Continue to Dataset & Training \u2192")
        self.continue_btn.setObjectName("actionBtn")
        self.continue_btn.setEnabled(False)
        self.continue_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; "
            "color: white; font-weight: bold; padding: 8px 20px; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
            "QPushButton:disabled { background-color: #1a4a4a; color: #666; border-color: #333; }"
        )
        self.continue_btn.clicked.connect(self._continue_forward)
        continue_row.addWidget(self.continue_btn)
        layout.addLayout(continue_row)

    def on_enter(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._cleanup_render()
        project = self.main_window.current_project
        if project is None:
            self.header_label.setText("Review & Render")
            self.sub_header.setText("No project loaded")
            return

        self.header_label.setText("Review & Render")
        self.sub_header.setText(f"Project: {project.character.character_id}")

        self._populate_summary()
        self._populate_validation()
        self._populate_job_preview()
        self._populate_progress_table()

        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.continue_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("0 / 0 renders")
        self.status_label.setText("Ready")
        self.elapsed_label.setText("Elapsed: --")
        self.remaining_label.setText("Remaining: --")
        self._completed_count = 0
        self._failed_count = 0
        self._start_time = None

    def _populate_summary(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return

        counts = compute_render_counts(project)
        self._total_render_count = counts["total"]

        per_look = counts["per_look"]
        self.summary_table.setRowCount(len(per_look))

        for row, (trigger, count) in enumerate(per_look.items()):
            look = None
            for lk in project.looks:
                if lk.trigger_phrase == trigger:
                    look = lk
                    break
            pg_names = ", ".join(look.pose_group_ids) if look else ""
            total_poses = 0
            total_cameras = 0
            total_lighting = 0
            if look:
                for pg_id in (look.pose_group_ids or []):
                    for pg in project.pose_groups:
                        if pg.pose_group_id == pg_id:
                            resolved_cams = self._resolve_cameras(pg, project)
                            resolved_lights = self._resolve_lighting(pg, project)
                            total_poses += len(pg.pose_asset_paths)
                            total_cameras = max(total_cameras, len(resolved_cams))
                            total_lighting = max(total_lighting, len(resolved_lights))

            self.summary_table.setItem(row, 0, QTableWidgetItem(trigger))
            self.summary_table.setItem(row, 1, QTableWidgetItem(pg_names))
            self.summary_table.setItem(row, 2, QTableWidgetItem(str(total_poses)))
            self.summary_table.setItem(row, 3, QTableWidgetItem(str(total_cameras)))
            self.summary_table.setItem(row, 4, QTableWidgetItem(str(total_lighting)))
            self.summary_table.setItem(row, 5, QTableWidgetItem(str(count)))

        self.total_label.setText(f"Total: {counts['total']} images")
        est_seconds = self._total_render_count * 30
        self.est_time_label.setText(
            f"Estimated time: {self._format_time(est_seconds)}"
        )

    def _populate_validation(self) -> None:
        project = self.main_window.current_project
        if project is None:
            self.validation_box.setVisible(False)
            return

        warnings = validate_render_counts(project)
        while self.validation_layout.count():
            w = self.validation_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        if not warnings:
            self.validation_box.setStyleSheet(
                "QGroupBox { border: 1px solid #444444; border-radius: 6px; "
                "margin-top: 16px; padding: 20px 12px 12px 12px; font-weight: bold; }"
            )
            label = QLabel("Looks healthy!")
            label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #5a5; padding: 8px;"
            )
            self.validation_layout.addWidget(label)
        else:
            self.validation_box.setStyleSheet(
                "QGroupBox { border: 1px solid #887a30; border-radius: 6px; "
                "margin-top: 16px; padding: 20px 12px 12px 12px; font-weight: bold; }"
            )
            for w in warnings:
                label = QLabel(w)
                label.setStyleSheet(
                    "font-size: 13px; color: #d4c84a; padding: 2px 0;"
                )
                self.validation_layout.addWidget(label)

        self.validation_box.setVisible(True)

    def _populate_job_preview(self) -> None:
        project = self.main_window.current_project
        if project is None:
            self._job_preview_area.setPlainText("")
            return
        job = self._build_job_config()
        self._job_preview_area.setPlainText(
            json.dumps(job, indent=2, default=str)
        )

    def _populate_progress_table(self) -> None:
        project = self.main_window.current_project
        if project is None:
            self.progress_table.setRowCount(0)
            self._render_rows = []
            return

        rows = self._build_render_rows(project)
        self._render_rows = rows
        self.progress_table.setRowCount(len(rows))

        for i, row_data in enumerate(rows):
            self.progress_table.setItem(i, 0, QTableWidgetItem(str(row_data["index"])))
            self.progress_table.setItem(i, 1, QTableWidgetItem(row_data["trigger"]))
            self.progress_table.setItem(i, 2, QTableWidgetItem(row_data["pose"]))
            self.progress_table.setItem(i, 3, QTableWidgetItem(row_data["camera"]))
            self.progress_table.setItem(i, 4, QTableWidgetItem(row_data["lighting"]))
            status_item = QTableWidgetItem("pending")
            status_item.setForeground(QColor("#888"))
            self.progress_table.setItem(i, 5, status_item)

        self.progress_table.scrollToTop()

    def _build_render_rows(self, project) -> list[dict]:
        rows: list[dict] = []
        idx = 0
        for look in project.looks:
            for pg_id in (look.pose_group_ids or []):
                pg = None
                for p in project.pose_groups:
                    if p.pose_group_id == pg_id:
                        pg = p
                        break
                if pg is None:
                    continue
                cameras = self._resolve_cameras(pg, project)
                lighting = self._resolve_lighting(pg, project)
                for pose_path in pg.pose_asset_paths:
                    for cam in cameras:
                        for light in lighting:
                            rows.append({
                                "index": idx,
                                "trigger": look.trigger_phrase,
                                "pose": Path(pose_path).name,
                                "camera": cam,
                                "lighting": light,
                                "status": "pending",
                            })
                            idx += 1
        return rows

    def _resolve_camera_profile(self, project, profile_id: str):
        if project:
            for cp in project.camera_profiles:
                if cp.camera_profile_id == profile_id:
                    return cp
        for cp in DEFAULT_CAMERA_PROFILES:
            if cp.camera_profile_id == profile_id:
                return cp
        return None

    def _resolve_cameras(self, pg, project) -> list[str]:
        if pg.camera_overrides:
            return pg.camera_overrides
        cp = self._resolve_camera_profile(project, pg.assigned_camera_profile)
        return cp.cameras if cp else []

    def _resolve_lighting(self, pg, project) -> list[str]:
        if pg.lighting_overrides:
            return pg.lighting_overrides
        cp = self._resolve_camera_profile(project, pg.assigned_camera_profile)
        return cp.lighting if cp else []

    def _build_job_config(self) -> dict:
        project = self.main_window.current_project
        config = self.main_window.config
        ws_root = Path(config.workspace_root)
        char = project.character

        cams: dict[str, dict] = {}
        for cp in DEFAULT_CAMERA_PROFILES:
            cams[cp.camera_profile_id] = {
                "cameras": cp.cameras,
                "lighting": cp.lighting,
            }
        for cp in project.camera_profiles:
            cams[cp.camera_profile_id] = {
                "cameras": cp.cameras,
                "lighting": cp.lighting,
            }

        return {
            "character": {
                "figure_asset_path": char.figure_asset_path,
                "shape_preset_path": char.shape_preset_path,
                "skin_material_path": char.skin_material_path,
                "default_hair_asset_path": char.default_hair_asset_path,
            },
            "looks": [l.to_dict() for l in project.looks],
            "pose_groups": [pg.to_dict() for pg in project.pose_groups],
            "camera_profiles": cams,
            "output_dir": str(
                ws_root / "projects" / project.project_id / "renders"
            ),
            "render_settings": {
                "width": config.render_width,
                "height": config.render_height,
                "samples": config.render_samples,
            },
        }

    def _start_render(self) -> None:
        project = self.main_window.current_project
        if project is None:
            QMessageBox.warning(self, "No Project", "No project loaded.")
            return

        if self._total_render_count == 0:
            QMessageBox.warning(
                self, "Nothing to Render",
                "No renders configured. Add looks and pose groups first.",
            )
            return

        warnings = validate_render_counts(project)
        if warnings:
            reply = QMessageBox.question(
                self, "Render Warnings",
                "Some looks have render count warnings:\n\n"
                + "\n".join(warnings)
                + "\n\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        job = self._build_job_config()

        self._completed_count = 0
        self._failed_count = 0
        self._start_time = time.time()

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.continue_btn.setEnabled(False)
        self.status_label.setText("Starting render...")
        self.progress_bar.setMaximum(self._total_render_count)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"0 / {self._total_render_count} renders")

        for row in self._render_rows:
            row["status"] = "pending"

        self._thread = QThread()
        self._worker = RenderWorker(job, self.main_window.config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_render_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _cancel_render(self) -> None:
        if self._worker:
            self._worker.cancel()
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelling...")
        self.start_btn.setEnabled(True)
        self.continue_btn.setEnabled(True)

    def _on_progress(self, data: dict) -> None:
        ptype = data.get("type")

        if ptype == "rendered":
            idx = data.get("index", 0)
            trigger = data.get("trigger", "")
            pose = data.get("pose", "")
            camera = data.get("camera", "")
            lighting = data.get("lighting", "")

            self._completed_count += 1
            row_idx = self._find_row(idx, trigger, pose, camera, lighting)
            if row_idx >= 0:
                self._render_rows[row_idx]["status"] = "rendered"
                self.progress_table.item(row_idx, 5).setText("rendered")
                self.progress_table.item(row_idx, 5).setForeground(GREEN)
                self.progress_table.scrollToItem(
                    self.progress_table.item(row_idx, 0)
                )

            self.progress_bar.setValue(self._completed_count)
            self.progress_label.setText(
                f"{self._completed_count} / {self._total_render_count} renders"
            )
            self.status_label.setText(
                f"Rendered: {trigger} / {pose} ({camera}, {lighting})"
            )

        elif ptype == "failed":
            idx = data.get("index", 0)
            trigger = data.get("trigger", "")
            pose = data.get("pose", "")
            camera = data.get("camera", "")
            lighting = data.get("lighting", "")
            error = data.get("error", "Unknown error")

            self._failed_count += 1
            self._completed_count += 1
            row_idx = self._find_row(idx, trigger, pose, camera, lighting)
            if row_idx >= 0:
                self._render_rows[row_idx]["status"] = "failed"
                item = self.progress_table.item(row_idx, 5)
                item.setText("failed")
                item.setForeground(RED)
                item.setToolTip(error)
                self.progress_table.scrollToItem(
                    self.progress_table.item(row_idx, 0)
                )

            self.progress_bar.setValue(self._completed_count)
            self.progress_label.setText(
                f"{self._completed_count} / {self._total_render_count} renders"
            )
            self.status_label.setText(
                f"Failed: {trigger} / {pose} ({camera}, {lighting}) - {error}"
            )

        elif ptype == "complete":
            self.status_label.setText("Render session complete.")
            self.cancel_btn.setEnabled(False)
            self.start_btn.setEnabled(True)

        elif ptype == "fatal":
            error = data.get("error", "Fatal error during render")
            self.status_label.setText(f"Fatal error: {error}")
            self.cancel_btn.setEnabled(False)
            self.start_btn.setEnabled(True)
            QMessageBox.critical(self, "Render Error", error)

        self._update_time_estimates()

    def _on_render_finished(self, returncode: int) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None

        self.cancel_btn.setEnabled(False)
        self.start_btn.setEnabled(True)

        if returncode != 0:
            self.status_label.setText(
                f"Render process exited with code {returncode}"
            )
            self.continue_btn.setEnabled(True)
            return

        elapsed = 0
        if self._start_time:
            elapsed = time.time() - self._start_time

        summary = (
            f"Render complete.\n\n"
            f"Total: {self._total_render_count}\n"
            f"Rendered: {self._completed_count - self._failed_count}\n"
            f"Failed: {self._failed_count}\n"
            f"Elapsed: {self._format_time(elapsed)}"
        )
        QMessageBox.information(self, "Render Complete", summary)
        self.status_label.setText("Render complete.")
        self.continue_btn.setEnabled(True)

    def _find_row(self, idx: int, trigger: str, pose: str, camera: str, lighting: str) -> int:
        for i, row in enumerate(self._render_rows):
            if (
                row["index"] == idx
                and row["trigger"] == trigger
                and row["pose"] == pose
                and row["camera"] == camera
                and row["lighting"] == lighting
            ):
                return i
        return -1

    def _update_time_estimates(self) -> None:
        if self._start_time is None:
            return

        elapsed = time.time() - self._start_time
        self.elapsed_label.setText(f"Elapsed: {self._format_time(elapsed)}")

        if self._completed_count > 0:
            remaining = estimate_render_time(
                self._total_render_count,
                self._completed_count,
                elapsed,
            )
        else:
            remaining = (self._total_render_count - self._completed_count) * 30

        self.remaining_label.setText(
            f"Remaining: {self._format_time(remaining)}"
        )

    def _cleanup_render(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker = None
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3)
            self._thread = None

    def _format_time(self, seconds: float) -> str:
        if seconds <= 0:
            return "--"
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}h {mins}m {secs}s"
        if mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    def _continue_forward(self) -> None:
        self.main_window.navigate_to(6)
