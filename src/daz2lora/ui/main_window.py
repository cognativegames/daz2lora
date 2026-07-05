from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from daz2lora.models.datamodels import CharacterProject
from daz2lora.utils.config import AppConfig

from daz2lora.ui.setup_screen import SetupScreen
from daz2lora.ui.project_selector import ProjectSelectorScreen
from daz2lora.ui.character_picker import CharacterPickerScreen
from daz2lora.ui.looks_editor import LooksEditorScreen
from daz2lora.ui.pose_groups_editor import PoseGroupsEditorScreen
from daz2lora.ui.render_screen import RenderScreen
from daz2lora.ui.dataset_screen import DatasetScreen
from daz2lora.ui.done_screen import DoneScreen


class MainWindow(QMainWindow):
    project_changed = Signal(object)
    config_changed = Signal(object)

    SCREEN_NAMES = [
        "Setup",
        "Project Selector",
        "Character Picker",
        "Looks Editor",
        "Pose Groups Editor",
        "Review & Render",
        "Dataset & Training",
        "Done",
    ]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.current_project: Optional[CharacterProject] = None
        self.visited_screens: set[int] = set()
        self.screens: list[QWidget] = []
        self.sidebar_btns: list[QPushButton] = []
        self.sidebar_btn_group = QButtonGroup(self)

        self.setWindowTitle("DAZ to LoRA")
        self.resize(1200, 800)
        self._build_ui()
        self._connect_nav()

        if not self.config.workspace_root:
            self._silent_navigate(0)
        else:
            self.visited_screens.add(0)
            self._silent_navigate(1)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_sidebar(main_layout)
        self._build_content(main_layout)
        self._refresh_sidebar()
        self._apply_style()

    def _build_sidebar(self, parent_layout: QHBoxLayout) -> None:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("DAZ to LoRA")
        title.setObjectName("sidebarTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        for i, name in enumerate(self.SCREEN_NAMES):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setObjectName("sidebarBtn")
            btn.clicked.connect(lambda checked, idx=i: self._on_sidebar_click(idx))
            self.sidebar_btns.append(btn)
            self.sidebar_btn_group.addButton(btn, i)
            layout.addWidget(btn)

        layout.addStretch()
        parent_layout.addWidget(sidebar)

    def _build_content(self, parent_layout: QHBoxLayout) -> None:
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.screens = [
            SetupScreen(self),
            ProjectSelectorScreen(self),
            CharacterPickerScreen(self),
            LooksEditorScreen(self),
            PoseGroupsEditorScreen(self),
            RenderScreen(self),
            DatasetScreen(self),
            DoneScreen(self),
        ]
        for s in self.screens:
            self.stack.addWidget(s)

        content_layout.addWidget(self.stack)

        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(12, 8, 12, 8)

        self.back_btn = QPushButton("\u2190 Back")
        self.back_btn.setObjectName("navBtn")
        self.back_btn.setFixedWidth(100)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()

        self.next_btn = QPushButton("Next \u2192")
        self.next_btn.setObjectName("navBtn")
        self.next_btn.setFixedWidth(100)
        nav_layout.addWidget(self.next_btn)

        content_layout.addWidget(nav_bar)
        parent_layout.addWidget(content_wrapper, 1)

    def _connect_nav(self) -> None:
        self.back_btn.clicked.connect(self.navigate_back)
        self.next_btn.clicked.connect(self.navigate_next)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-size: 13px;
            }
            #sidebar {
                background-color: #252526;
                border-right: 1px solid #3c3c3c;
            }
            #sidebarTitle {
                font-size: 14px;
                font-weight: bold;
                padding: 16px 8px;
                color: #cccccc;
                background-color: #252526;
            }
            #sidebarBtn {
                background-color: transparent;
                border: none;
                border-radius: 0;
                padding: 10px 16px;
                text-align: left;
                color: #999999;
                font-size: 13px;
            }
            #sidebarBtn:hover {
                background-color: #2a2d2e;
                color: #d4d4d4;
            }
            #sidebarBtn:checked {
                background-color: #094771;
                color: white;
                font-weight: bold;
            }
            QPushButton {
                background-color: #333333;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 16px;
                color: #d4d4d4;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #252525;
                color: #555555;
                border-color: #3a3a3a;
            }
            #navBtn {
                background-color: #333333;
                border: 1px solid #555555;
                min-width: 80px;
            }
            #navBar {
                background-color: #252526;
                border-top: 1px solid #3c3c3c;
            }
            QLineEdit, QSpinBox {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 8px;
                color: #d4d4d4;
            }
            QGroupBox {
                border: 1px solid #444444;
                border-radius: 6px;
                margin-top: 16px;
                padding: 20px 12px 12px 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 4px;
                color: #d4d4d4;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: white;
            }
            QRadioButton, QCheckBox {
                color: #d4d4d4;
                spacing: 6px;
            }
            QLabel {
                color: #d4d4d4;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollArea {
                border: none;
            }
            QSplitter::handle {
                background-color: #3c3c3c;
                width: 1px;
            }
        """)

    def _on_sidebar_click(self, index: int) -> None:
        if index in self.visited_screens:
            self.navigate_to(index)

    def _refresh_sidebar(self) -> None:
        current = self.stack.currentIndex()
        for i, btn in enumerate(self.sidebar_btns):
            btn.setEnabled(i in self.visited_screens)
            if i == current:
                btn.setText(f"\u25b6 {self.SCREEN_NAMES[i]}")
                btn.setChecked(True)
            elif i in self.visited_screens:
                btn.setText(f"\u2713 {self.SCREEN_NAMES[i]}")
                btn.setChecked(False)
            else:
                btn.setText(f"  {self.SCREEN_NAMES[i]}")
                btn.setChecked(False)

    def navigate_to(self, index: int) -> None:
        if index < 0 or index >= len(self.screens):
            return

        self.visited_screens.add(index)
        self.stack.setCurrentIndex(index)
        self._refresh_sidebar()

        btn = self.sidebar_btn_group.button(index)
        if btn:
            btn.setChecked(True)

        has_prev = index > 0
        has_next = index < len(self.screens) - 1
        self.back_btn.setEnabled(has_prev)
        self.next_btn.setEnabled(has_next)

        screen = self.screens[index]
        if hasattr(screen, "on_enter"):
            screen.on_enter()

    def _silent_navigate(self, index: int) -> None:
        self.visited_screens.add(index)
        self.stack.setCurrentIndex(index)
        self._refresh_sidebar()
        btn = self.sidebar_btn_group.button(index)
        if btn:
            btn.setChecked(True)
        has_prev = index > 0
        has_next = index < len(self.screens) - 1
        self.back_btn.setEnabled(has_prev)
        self.next_btn.setEnabled(has_next)
        screen = self.screens[index]
        if hasattr(screen, "on_enter"):
            screen.on_enter()

    def navigate_next(self) -> None:
        idx = self.stack.currentIndex()
        if idx < len(self.screens) - 1:
            self.navigate_to(idx + 1)

    def navigate_back(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.navigate_to(idx - 1)

    def set_project(self, project: Optional[CharacterProject]) -> None:
        self.current_project = project
        self.project_changed.emit(project)

    def set_config(self, config: AppConfig) -> None:
        self.config = config
        config.save()
        self.config_changed.emit(config)
