from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import CharacterProject
from daz2lora.utils.config import AppConfig
from daz2lora.utils.dataset_assembler import (
    assemble_dataset,
    find_replace_captions,
    get_dataset_stats,
    load_captions,
    save_captions,
)
from daz2lora.utils.training_launcher import TrainingLauncher


class DatasetScreen(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self._launcher = TrainingLauncher(self)
        self._stats: dict = {}
        self._captions: dict[str, str] = {}
        self._current_filter: str = ""
        self._retrain_mode: bool = False
        self._start_time = None
        self._elapsed_timer: QTimer = QTimer(self)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Dataset & Training")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self._build_overview_section(layout)
        self._build_captions_section(layout)
        self._build_training_config_section(layout)
        self._build_training_progress_section(layout)

        layout.addStretch()
        scroll.setWidget(scroll_content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _build_overview_section(self, layout: QVBoxLayout) -> None:
        self.overview_group = QGroupBox("Dataset Overview")
        overview_layout = QVBoxLayout(self.overview_group)

        self.overview_label = QLabel("No dataset assembled yet.")
        self.overview_label.setWordWrap(True)
        overview_layout.addWidget(self.overview_label)

        btn_row = QHBoxLayout()
        self.reassemble_btn = QPushButton("Reassemble Dataset")
        self.reassemble_btn.clicked.connect(self._on_reassemble)
        self.open_folder_btn = QPushButton("Open Dataset Folder")
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        self.open_folder_btn.setEnabled(False)
        btn_row.addWidget(self.reassemble_btn)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        overview_layout.addLayout(btn_row)

        layout.addWidget(self.overview_group)

    def _build_captions_section(self, layout: QVBoxLayout) -> None:
        self.captions_group = QGroupBox("Auto-Generated Captions")
        captions_layout = QVBoxLayout(self.captions_group)

        self.caption_table = QTableWidget(0, 3)
        self.caption_table.setHorizontalHeaderLabels(["Image File", "Look", "Caption"])
        self.caption_table.horizontalHeader().setStretchLastSection(True)
        self.caption_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.caption_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.caption_table.setAlternatingRowColors(True)
        self.caption_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed
        )
        captions_layout.addWidget(self.caption_table)

        tool_row = QHBoxLayout()
        tool_row.addWidget(QLabel("Find:"))
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Search text...")
        tool_row.addWidget(self.find_edit)

        tool_row.addWidget(QLabel("Replace:"))
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with...")
        tool_row.addWidget(self.replace_edit)

        self.replace_all_btn = QPushButton("Replace All")
        self.replace_all_btn.clicked.connect(self._on_replace_all)
        tool_row.addWidget(self.replace_all_btn)

        self.save_captions_btn = QPushButton("Save All Captions")
        self.save_captions_btn.clicked.connect(self._on_save_captions)
        self.save_captions_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; color: white; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        tool_row.addWidget(self.save_captions_btn)

        tool_row.addStretch()
        self.caption_count_label = QLabel("Showing 0 of 0")
        tool_row.addWidget(self.caption_count_label)

        captions_layout.addLayout(tool_row)
        layout.addWidget(self.captions_group)

    def _build_training_config_section(self, layout: QVBoxLayout) -> None:
        self.training_group = QGroupBox("Training Hyperparameters")
        training_layout = QVBoxLayout(self.training_group)
        form = QFormLayout()

        self.lr_spin = QDoubleSpinBox()
        self.lr_spin.setRange(1e-7, 1e-4)
        self.lr_spin.setDecimals(7)
        self.lr_spin.setSingleStep(1e-7)
        self.lr_spin.setValue(1e-4)
        self.lr_spin.setKeyboardTracking(False)
        form.addRow("Learning Rate:", self.lr_spin)

        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(100, 50000)
        self.steps_spin.setSingleStep(100)
        form.addRow("Training Steps:", self.steps_spin)

        self.dim_spin = QSpinBox()
        self.dim_spin.setRange(1, 256)
        self.dim_spin.setValue(32)
        form.addRow("Network Rank (dim):", self.dim_spin)

        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(1, 256)
        self.alpha_spin.setValue(16)
        form.addRow("Network Alpha:", self.alpha_spin)

        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 16)
        self.batch_spin.setValue(4)
        form.addRow("Batch Size:", self.batch_spin)

        self.resolution_spin = QSpinBox()
        self.resolution_spin.setRange(512, 2048)
        self.resolution_spin.setSingleStep(64)
        self.resolution_spin.setValue(1024)
        form.addRow("Resolution:", self.resolution_spin)

        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 50)
        self.epochs_spin.setValue(10)
        form.addRow("Number of Epochs:", self.epochs_spin)

        self.save_every_spin = QSpinBox()
        self.save_every_spin.setRange(1, 10)
        self.save_every_spin.setValue(5)
        form.addRow("Save Every N Epochs:", self.save_every_spin)

        self.optimizer_combo = QComboBox()
        self.optimizer_combo.addItems(["AdamW", "AdamW8bit", "Lion", "Prodigy"])
        form.addRow("Optimizer:", self.optimizer_combo)

        self.mixed_precision_combo = QComboBox()
        self.mixed_precision_combo.addItems(["fp16", "bf16", "no"])
        form.addRow("Mixed Precision:", self.mixed_precision_combo)

        training_layout.addLayout(form)

        self.mode_group = QGroupBox("Training Mode")
        mode_layout = QVBoxLayout(self.mode_group)

        self.mode_label = QLabel("No prior LoRA found. Fresh training run on the full dataset.")
        self.mode_label.setWordWrap(True)
        mode_layout.addWidget(self.mode_label)

        self.retrain_btn = QPushButton("Retrain from Scratch")
        self.retrain_btn.setStyleSheet(
            "QPushButton { color: #e06c75; border-color: #e06c75; }"
            "QPushButton:hover { background-color: #3a1a1e; }"
        )
        self.retrain_btn.clicked.connect(self._on_retrain)
        self.retrain_btn.setVisible(False)
        mode_layout.addWidget(self.retrain_btn)

        training_layout.addWidget(self.mode_group)

        self.train_btn = QPushButton("Train LoRA")
        self.train_btn.setStyleSheet(
            "QPushButton { background-color: #3c8733; border-color: #3c8733; color: white; "
            "font-weight: bold; padding: 10px 32px; font-size: 15px; }"
            "QPushButton:hover { background-color: #4a9e3f; }"
            "QPushButton:disabled { background-color: #2a5a25; color: #888; }"
        )
        self.train_btn.clicked.connect(self._on_train)
        training_layout.addWidget(self.train_btn)

        self.view_lora_btn = QPushButton("View LoRA \u2192")
        self.view_lora_btn.setStyleSheet(
            "QPushButton { background-color: #0d7377; border-color: #0d7377; color: white; "
            "font-weight: bold; padding: 8px 24px; font-size: 14px; }"
            "QPushButton:hover { background-color: #0f8a8e; }"
        )
        self.view_lora_btn.clicked.connect(lambda: self.main_window.navigate_to(7))
        self.view_lora_btn.setVisible(False)
        training_layout.addWidget(self.view_lora_btn)

        layout.addWidget(self.training_group)

    def _build_training_progress_section(self, layout: QVBoxLayout) -> None:
        self.progress_group = QGroupBox("Training Progress")
        self.progress_group.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_group)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(10000)
        self.log_output.setStyleSheet(
            "QPlainTextEdit { background-color: #1a1a1a; color: #d4d4d4; "
            "font-family: 'Menlo', 'Consolas', monospace; font-size: 12px; }"
        )
        progress_layout.addWidget(self.log_output)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        time_row = QHBoxLayout()
        self.elapsed_label = QLabel("Elapsed: --")
        self.remaining_label = QLabel("Remaining: --")
        time_row.addWidget(self.elapsed_label)
        time_row.addStretch()
        time_row.addWidget(self.remaining_label)
        progress_layout.addLayout(time_row)

        self.cancel_btn = QPushButton("Cancel Training")
        self.cancel_btn.setStyleSheet(
            "QPushButton { background-color: #c43e3e; border-color: #c43e3e; color: white; }"
            "QPushButton:hover { background-color: #d94f4f; }"
        )
        self.cancel_btn.clicked.connect(self._on_cancel_training)
        progress_layout.addWidget(self.cancel_btn)

        layout.addWidget(self.progress_group)

    def _connect_signals(self) -> None:
        self._launcher.log_line.connect(self._on_log_line)
        self._launcher.progress.connect(self._on_progress)
        self._launcher.completed.connect(self._on_training_completed)
        self.main_window.project_changed.connect(self._on_project_changed)

    def on_enter(self) -> None:
        self._refresh()

    def _on_project_changed(self, project) -> None:
        self._refresh()

    def _refresh(self) -> None:
        project = self.main_window.current_project
        config = self.main_window.config

        if project is None:
            self.overview_label.setText("No project loaded.")
            self.train_btn.setEnabled(False)
            return

        self.train_btn.setEnabled(True)
        self._update_overview(project, config)

    def _update_overview(self, project: CharacterProject, config: AppConfig) -> None:
        dataset_root = project.dataset_root_path
        if not dataset_root.exists():
            self.overview_label.setText(
                f"Project: {project.project_id}\n"
                "Dataset not yet assembled. Click 'Reassemble Dataset' below."
            )
            self.open_folder_btn.setEnabled(False)
            self.caption_table.setRowCount(0)
            self.caption_count_label.setText("Showing 0 of 0")
            return

        self.open_folder_btn.setEnabled(True)
        self._stats = get_dataset_stats(dataset_root)

        lines = [
            f"Project: {project.project_id}",
            f"Total Images: {self._stats['total_images']}",
            f"Total Captions: {self._stats['total_captions']}",
        ]
        if self._stats["per_look_counts"]:
            lines.append("")
            lines.append("Per-Look Breakdown:")
            for folder, count in self._stats["per_look_counts"].items():
                lines.append(f"  {folder}: {count} images")
        if self._stats.get("image_dimensions_sample"):
            w, h = self._stats["image_dimensions_sample"]
            lines.append(f"Sample Image Dimensions: {w}x{h}")
        self.overview_label.setText("\n".join(lines))

        self._load_captions_into_table(dataset_root)

        self._update_steps_default()

        if project.trained_lora_path:
            path = project.trained_lora_path
            self.mode_label.setText(
                f"Prior LoRA found at:\n{path}\n\n"
                "Training will continue from this checkpoint with all accumulated data."
            )
            self.retrain_btn.setVisible(True)
            self.view_lora_btn.setVisible(True)
        else:
            self.mode_label.setText(
                "No prior LoRA found. Fresh training run on the full dataset."
            )
            self.retrain_btn.setVisible(False)
            self.view_lora_btn.setVisible(False)

    def _load_captions_into_table(self, dataset_root: Path) -> None:
        self._captions = load_captions(dataset_root)
        self._apply_caption_filter()

    def _apply_caption_filter(self) -> None:
        self.caption_table.setRowCount(0)
        filter_text = self._current_filter.lower()
        rows = []

        for rel_path, caption in self._captions.items():
            if filter_text and filter_text not in rel_path.lower() and filter_text not in caption.lower():
                continue
            rows.append((rel_path, caption))

        self.caption_table.setRowCount(len(rows))
        for i, (rel_path, caption) in enumerate(rows):
            path_item = QTableWidgetItem(rel_path)
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.caption_table.setItem(i, 0, path_item)

            folder = Path(rel_path).parent.name
            look_item = QTableWidgetItem(folder)
            look_item.setFlags(look_item.flags() & ~Qt.ItemIsEditable)
            self.caption_table.setItem(i, 1, look_item)

            cap_item = QTableWidgetItem(caption)
            self.caption_table.setItem(i, 2, cap_item)

        self.caption_count_label.setText(
            f"Showing {len(rows)} of {len(self._captions)}"
        )

    def _update_steps_default(self) -> None:
        total = self._stats.get("total_images", 0)
        num_looks = max(len(self._stats.get("per_look_counts", {})), 1)
        if total > 0:
            suggested = int(100 * total / num_looks)
            self.steps_spin.setValue(suggested)

    def _on_reassemble(self) -> None:
        project = self.main_window.current_project
        config = self.main_window.config
        if project is None:
            return

        if not config.workspace_root:
            QMessageBox.warning(self, "Error", "Workspace root not configured.")
            return

        render_dir = (
            Path(config.workspace_root)
            / "projects"
            / project.character.character_id
            / "renders"
        )
        if not render_dir.exists():
            QMessageBox.warning(
                self,
                "No Renders Found",
                f"Render directory does not exist:\n{render_dir}\n\n"
                "Run renders from the Review & Render screen first.",
            )
            return

        try:
            dataset_root = assemble_dataset(project, config, render_dir, overwrite=False)
            QMessageBox.information(
                self,
                "Dataset Assembled",
                f"Dataset assembled at:\n{dataset_root}",
            )
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "Assembly Error", str(e))

    def _on_open_folder(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return
        path = project.dataset_root_path
        if path.exists():
            QDesktopServices.openUrl(path.as_uri())

    def _on_replace_all(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return
        find_text = self.find_edit.text().strip()
        replace_text = self.replace_edit.text()
        if not find_text:
            return

        reply = QMessageBox.question(
            self,
            "Replace All",
            f"Replace all occurrences of '{find_text}' with '{replace_text}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            count = find_replace_captions(project.dataset_root_path, find_text, replace_text)
            QMessageBox.information(self, "Replace Complete", f"{count} replacement(s) made.")
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_save_captions(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return

        updates: dict[str, str] = {}
        for row in range(self.caption_table.rowCount()):
            rel_path = self.caption_table.item(row, 0).text()
            caption = self.caption_table.item(row, 2).text()
            updates[rel_path] = caption

        try:
            save_captions(project.dataset_root_path, updates)
            self._captions = load_captions(project.dataset_root_path)
            QMessageBox.information(self, "Saved", "All captions saved.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_train(self) -> None:
        project = self.main_window.current_project
        config = self.main_window.config
        if project is None:
            return

        if not project.dataset_root_path.exists():
            QMessageBox.warning(
                self, "No Dataset", "Assemble the dataset before training."
            )
            return

        if not config.kohya_ss_path:
            QMessageBox.warning(
                self, "Not Configured",
                "kohya_ss path is not configured. Go to Setup first."
            )
            return

        if not config.sdxl_checkpoint_path:
            QMessageBox.warning(
                self, "Not Configured",
                "SDXL checkpoint path is not configured. Go to Setup first."
            )
            return

        params = {
            "lr": self.lr_spin.value(),
            "steps": self.steps_spin.value(),
            "dim": self.dim_spin.value(),
            "alpha": self.alpha_spin.value(),
            "batch_size": self.batch_spin.value(),
            "resolution": self.resolution_spin.value(),
            "epochs": self.epochs_spin.value(),
            "save_every": self.save_every_spin.value(),
            "optimizer": self.optimizer_combo.currentText(),
            "mixed_precision": self.mixed_precision_combo.currentText(),
            "continue_from_prior": project.trained_lora_path is not None,
            "retrain_from_scratch": self._retrain_mode,
        }

        self.progress_group.setVisible(True)
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.elapsed_label.setText("Elapsed: 0:00:00")
        self.remaining_label.setText("Remaining: --")
        self._start_time = None
        self._elapsed_timer.timeout.connect(self._update_elapsed, Qt.UniqueConnection)
        self._elapsed_timer.start(1000)

        self.train_btn.setEnabled(False)
        self._launcher.launch(project, config, params, project.dataset_root_path)

    def _on_cancel_training(self) -> None:
        self._launcher.cancel()
        self.log_output.appendPlainText("\n--- Training cancelled ---")

    def _on_retrain(self) -> None:
        project = self.main_window.current_project
        if project is None:
            return
        reply = QMessageBox.warning(
            self,
            "Retrain from Scratch",
            "This will discard the existing LoRA and train from scratch.\n\n"
            "The prior checkpoint will NOT be used as a starting point.\n"
            "Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._retrain_mode = True
            self._on_train()

    def _on_log_line(self, line: str) -> None:
        self.log_output.appendPlainText(line)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_progress(self, current: int, total: int) -> None:
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{current} / {total}  (%p%)")

    def _on_training_completed(self, success: bool, message: str) -> None:
        if self._elapsed_timer:
            self._elapsed_timer.stop()

        self._retrain_mode = False
        self.train_btn.setEnabled(True)
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.log_output.appendPlainText(f"\n--- Training completed successfully ---")
            self.log_output.appendPlainText(f"Output: {message}")

            self.view_lora_btn.setVisible(True)

            reply = QMessageBox.question(
                self,
                "Training Complete",
                f"LoRA model saved to:\n{message}\n\n"
                "View results?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self.main_window.navigate_to(7)
        else:
            self.log_output.appendPlainText(f"\n--- Training failed: {message} ---")
            QMessageBox.critical(self, "Training Failed", message)

        self._refresh()

    def _update_elapsed(self) -> None:
        import datetime
        if self._start_time is None:
            self._start_time = datetime.datetime.now()
        elapsed = datetime.datetime.now() - self._start_time
        self.elapsed_label.setText(f"Elapsed: {str(elapsed).split('.')[0]}")
