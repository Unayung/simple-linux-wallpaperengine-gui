#!/usr/bin/env python3

import sys
import os
import glob
import json
import subprocess
import shutil
import re
import pathlib
import urllib.request
import logging
import argparse

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QCheckBox, QSlider, QComboBox,
                             QStackedWidget, QListWidget, QListWidgetItem, QSystemTrayIcon,
                             QMenu, QFrame, QSizePolicy, QGraphicsDropShadowEffect,
                             QStyledItemDelegate, QStyle, QStyleOptionSlider, QFileDialog,
                             QScrollArea, QGridLayout, QSplitter, QTabBar, QToolButton,
                             QSpacerItem)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject, QTimer, QRect, QPropertyAnimation, QEasingCurve, QVariant, QUrl
from PyQt6.QtGui import QFont, QIcon, QPixmap, QImage, QAction, QColor, QPainter, QDesktopServices
from process_manager import WallpaperProcessManager
from steamcmd_service import SteamCmdService, DownloadStatus
from dependency_resolver import resolve_wallpaper, get_dependency_id, read_project_json, find_workshop_item
from workshop_api import (WorkshopItem, SortOrder,
                          CONTENT_RATING_TAGS, TYPE_TAGS, GENRE_TAGS,
                          search_items, NoAPIKeyError, InvalidAPIKeyError, WorkshopAPIError)

CONFIG_FILE = pathlib.Path(os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "linux-wallpaperengine-gui" / "wpe_gui_config.json"
LOCALE_DIR = (pathlib.Path(__file__).parent / "locales").absolute()

# ── Stylesheet ──────────────────────────────────────────────────────────────
STYLESHEET = """
* { font-family: "Inter", "SF Pro Display", "Segoe UI", "Helvetica Neue", sans-serif; }

QMainWindow { background-color: #1a1a1a; }

/* ── Top Tab Bar ───────────────────────────────────── */
QWidget#TopBar { background-color: #1a1a1a; border-bottom: 2px solid #0A84FF; }
QPushButton#TabBtn {
    background: transparent; border: 2px solid #0A84FF; border-bottom: none;
    color: #888; font-size: 14px; font-weight: 600; padding: 8px 20px; min-width: 100px;
}
QPushButton#TabBtn:hover { color: #ddd; background: rgba(10,132,255,0.08); }
QPushButton#TabBtnActive {
    background: #0A84FF; border: 2px solid #0A84FF; border-bottom: none;
    color: #fff; font-size: 14px; font-weight: 600; padding: 8px 20px; min-width: 100px;
}
QPushButton#BarButton {
    background: transparent; border: 1px solid #3A3A3A;
    color: #aaa; font-size: 12px; padding: 5px 12px; border-radius: 4px;
}
QPushButton#BarButton:hover { background: #2a2a2a; color: #fff; }

/* ── Explorer Top Bar ──────────────────────────────── */
QWidget#ExplorerBar { background-color: #1f1f1f; }
QLineEdit#SearchField {
    background-color: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 6px;
    padding: 5px 10px; color: #fff; min-height: 26px; font-size: 13px;
}
QLineEdit#SearchField:focus { border-color: #0A84FF; }

/* ── Splitter & Panels ─────────────────────────────── */
QSplitter::handle { background-color: #2a2a2a; width: 1px; }
QWidget#LeftPanel { background-color: #1a1a1a; }
QWidget#PreviewPanel { background-color: #1f1f1f; border-left: 1px solid #2a2a2a; }

/* ── Wallpaper Grid ────────────────────────────────── */
QListWidget#WallpaperGrid {
    background-color: transparent; border: none; outline: none;
}
QListWidget#WallpaperGrid::item {
    background-color: #222; border: 1px solid #333; border-radius: 4px;
    margin: 6px; color: #fff; padding: 3px;
}
QListWidget#WallpaperGrid::item:selected { border: 2px solid #0A84FF; background-color: #2a2a2a; }
QListWidget#WallpaperGrid::item:hover { background-color: #2d2d2d; border-color: #444; }

/* ── Preview Panel ─────────────────────────────────── */
QLabel#PreviewImage {
    background-color: #111; border: 3px solid #fff; border-radius: 12px;
}
QLabel#PreviewTitle { font-size: 15px; font-weight: 600; color: #fff; }
QLabel#PreviewMeta { font-size: 12px; color: #888; }
QLabel#PreviewTag {
    background-color: transparent; border: 1px solid #666; border-radius: 10px;
    padding: 3px 8px; font-size: 11px; color: #ccc;
}

/* ── Properties Section ────────────────────────────── */
QLabel#SectionDivider { font-size: 13px; color: #aaa; }

/* ── Cards & Controls ──────────────────────────────── */
QFrame.Card { background-color: #222; border: 1px solid #333; border-radius: 8px; }
QLabel.CardTitle { font-weight: 600; font-size: 14px; color: #fff; }

QPushButton#PrimaryBtn {
    background-color: #0A84FF; color: white; border: none; border-radius: 5px;
    padding: 7px 18px; font-weight: 600; font-size: 13px;
}
QPushButton#PrimaryBtn:hover { background-color: #0070E0; }
QPushButton#PrimaryBtn:pressed { background-color: #005EC4; }

QPushButton#SecBtn {
    background-color: #333; color: #ddd; border: 1px solid #444; border-radius: 5px;
    padding: 7px 18px; font-size: 13px;
}
QPushButton#SecBtn:hover { background-color: #3a3a3a; }

QPushButton#DangerBtn {
    background-color: #FF453A; color: white; border: none; border-radius: 5px;
    padding: 7px 18px; font-weight: 600; font-size: 13px;
}
QPushButton#DangerBtn:hover { background-color: #D0342C; }

QPushButton#LinkBtn {
    background: transparent; border: none; color: #0A84FF;
    font-size: 12px; text-decoration: underline; padding: 2px;
}

QLineEdit, QComboBox {
    background-color: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 6px;
    padding: 5px 8px; color: #fff; min-height: 24px; font-size: 13px;
}
QLineEdit:focus, QComboBox:focus { border-color: #0A84FF; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #222; border: 1px solid #3a3a3a;
    selection-background-color: #0A84FF; color: #fff; outline: none;
}

QCheckBox { spacing: 8px; color: #ddd; font-size: 13px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #555; background: #2a2a2a; }
QCheckBox::indicator:checked { background: #0A84FF; border-color: #0A84FF; }

QSlider::groove:horizontal { border: none; height: 4px; background: #444; border-radius: 2px; }
QSlider::handle:horizontal { background: #fff; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #0A84FF; border-radius: 2px; }

QScrollBar:vertical { border: none; background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.15); min-height: 40px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.25); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

/* ── Workshop ──────────────────────────────────────── */
QPushButton#TagBtn {
    background: #333; border: none; border-radius: 12px;
    padding: 4px 10px; font-size: 11px; color: #ccc; min-height: 16px;
}
QPushButton#TagBtn:hover { background: #444; }
QPushButton#TagBtnActive {
    background: #0A84FF; border: none; border-radius: 12px;
    padding: 4px 10px; font-size: 11px; color: #fff; min-height: 16px;
}
QPushButton#TagBtnActive:hover { background: #0070E0; }
QWidget#WorkshopCard { background-color: #222; border: 1px solid #333; border-radius: 8px; }
QPushButton#DlBtn {
    background: #0A84FF; border: none; border-radius: 3px;
    padding: 3px 10px; font-size: 11px; color: white; min-height: 14px;
}
QPushButton#DlBtn:hover { background: #0070E0; }

/* ── Status Bar ────────────────────────────────────── */
QStatusBar { background: #1a1a1a; color: #666; font-size: 11px; border-top: 1px solid #2a2a2a; }
"""


# ── Helper Classes ──────────────────────────────────────────────────────────

class AsyncTask:
    """Run a function in a background thread and deliver the result on the main thread.
    Uses ThreadPoolExecutor + QTimer polling to avoid cross-thread signal crashes on Python 3.14."""
    _executor = None

    @classmethod
    def _get_executor(cls):
        if cls._executor is None:
            from concurrent.futures import ThreadPoolExecutor
            cls._executor = ThreadPoolExecutor(max_workers=4)
        return cls._executor

    def __init__(self, func, *args, callback=None, **kwargs):
        from concurrent.futures import Future
        self._callback = callback
        self._future = self._get_executor().submit(func, *args, **kwargs)
        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._check)
        self._timer.start()

    def _check(self):
        if self._future.done():
            self._timer.stop()
            try:
                result = self._future.result()
            except Exception as e:
                result = e
            if self._callback:
                self._callback(result)

class I18n:
    def __init__(self):
        self.locale_data = {}
        self.current_code = "en"
        self.available_languages = {
            "en": "English", "zh-TW": "繁體中文", "ru": "Русский", "de": "Deutsch",
            "uk": "Українська", "es": "Español", "fr": "Français"
        }
    def load(self, code):
        try:
            with open(os.path.join(LOCALE_DIR, f"{code}.json"), 'r', encoding='utf-8') as f:
                self.locale_data = json.load(f)
            self.current_code = code
            return True
        except: return False
    def get(self, key, **kwargs):
        text = self.locale_data.get(key, key)
        if kwargs: return text.format(**kwargs)
        return text


class WallpaperDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scales = {}
        self.current_scales = {}
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animations)
        self.timer.start(10)

    def update_animations(self):
        changed = False
        step = 0.02
        for index_ptr, target in self.scales.items():
            curr = self.current_scales.get(index_ptr, 1.0)
            if abs(curr - target) > 0.001:
                if curr < target:
                    self.current_scales[index_ptr] = min(curr + step, target)
                else:
                    self.current_scales[index_ptr] = max(curr - step, target)
                changed = True
        if changed and self.parent():
            self.parent().viewport().update()

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        idx_id = index.row()
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver
        self.scales[idx_id] = 1.08 if is_hovered else 1.0
        scale = self.current_scales.get(idx_id, 1.0)
        if scale > 1.0:
            painter.translate(option.rect.center())
            painter.scale(scale, scale)
            painter.translate(-option.rect.center())
        super().paint(painter, option, index)
        painter.restore()


class WallpaperChangeHandler(FileSystemEventHandler):
    """Receives file system events from watchdog (non-Qt thread).
    Sets a flag instead of emitting a signal to avoid Qt thread-safety crash."""
    def __init__(self):
        self._active = True
        self._changed = False
    def on_any_event(self, event):
        if event.is_directory or not self._active:
            return
        self._changed = True


class LibraryWatcher(QObject):
    library_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._observer = None
        self.handler = WallpaperChangeHandler()
        self.watched_paths = set()
        # Debounce timer: checks the flag periodically from the main thread
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._check_changes)
        self._poll_timer.start()

    def _check_changes(self):
        if self.handler._changed:
            self.handler._changed = False
            self.library_changed.emit()

    def _stop_observer(self):
        if self._observer is not None and self._observer.is_alive():
            self.handler._active = False
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None

    def update_watches(self, directories):
        new_paths = set(directories)
        if new_paths == self.watched_paths:
            return
        self._stop_observer()
        self.handler._active = True
        self._observer = Observer()
        self.watched_paths = new_paths
        for d in directories:
            if os.path.isdir(d):
                try:
                    self._observer.schedule(self.handler, d, recursive=True)
                except Exception as e:
                    print(f"Failed to watch {d}: {e}")
        try:
            self._observer.start()
        except Exception as e:
            print(f"Failed to start observer: {e}")

    def stop(self):
        self._stop_observer()


class ClickableSlider(QSlider):
    def mousePressEvent(self, signal):
        if signal.button() == Qt.MouseButton.LeftButton:
            offset = 5
            value = QStyle.sliderValueFromPosition(self.minimum() - offset, self.maximum() + offset,
                                                   signal.pos().x(), self.width())
            self.setValue(value)
        super().mousePressEvent(signal)


# ── Main Application ────────────────────────────────────────────────────────

class WallpaperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.i18n = I18n()
        self.translatable_labels = []
        self.properties_data = {}
        self.load_config_data()
        self.i18n.load(self.config.get("current_language", "en"))
        self._ = self.i18n.get

        # Workshop state
        self.steam_cmd = SteamCmdService()
        self.workshop_items: list[WorkshopItem] = []
        self.workshop_page_num = 1
        self.workshop_search_text = ""
        self.workshop_sort_order = SortOrder.TRENDING
        self.workshop_selected_tags: list[str] = ["Everyone"]
        self.workshop_api_key = self.config.get("steam_api_key", "")
        self._workshop_image_cache: dict[str, QPixmap] = {}
        self._img_threads: list = []

        self.setWindowTitle("Open Wallpaper Engine")
        self.setMinimumSize(1100, 700)
        self.resize(1200, 800)

        self.setup_ui()
        self.setStyleSheet(STYLESHEET)

        self.setup_tray()
        self.start_scan()

        self.screens = self.detect_screens()
        for s in self.screens:
            self.screen_combo.addItem(s["name"], s)
        self.update_texts()

        self.watcher = LibraryWatcher()
        self.watcher.library_changed.connect(self.on_library_changed_auto)

        QTimer.singleShot(500, self.restore_last_wallpaper)

        self.steam_cmd.login_state_changed.connect(self._on_steam_login_changed)
        self.steam_cmd.download_updated.connect(self._on_download_updated)

        # Auto-attempt cached Steam login
        saved_user = self.config.get("steam_username", "")
        if saved_user and self.steam_cmd.is_installed and not self.steam_cmd.is_logged_in:
            self.steam_username_input.setText(saved_user)
            self.steam_cmd.login_cached(saved_user)

        self.wallpaper_proc_manager = WallpaperProcessManager()
        self.wallpaper_watchdog = QTimer()
        self.wallpaper_watchdog.setInterval(1000)
        self.wallpaper_watchdog.timeout.connect(self.check_wallpaper_process)
        self.wallpaper_watchdog.start()

        # Default to Installed tab
        self._switch_tab(0)

    # ── UI Setup ────────────────────────────────────────────────────────

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root = QVBoxLayout(main_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar: tabs + buttons
        self._build_top_bar(root)

        # Main content: splitter with left panel + right preview
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self.main_splitter, 1)

        # Left panel: stacked (Installed | Workshop | Settings)
        left_panel = QWidget()
        left_panel.setObjectName("LeftPanel")
        self.left_layout = QVBoxLayout(left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)

        self.content_stack = QStackedWidget()
        self.left_layout.addWidget(self.content_stack)

        # Page 0: Installed (explorer bar + grid)
        self.page_installed = QWidget()
        self._build_installed_page()
        self.content_stack.addWidget(self.page_installed)

        # Page 1: Workshop
        self.page_workshop = QWidget()
        self._build_workshop_page()
        self.content_stack.addWidget(self.page_workshop)

        # Page 2: Settings
        self.page_settings = QWidget()
        self._build_settings_page()
        self.content_stack.addWidget(self.page_settings)

        self.main_splitter.addWidget(left_panel)

        # Right panel: Preview
        self.preview_panel = QWidget()
        self.preview_panel.setObjectName("PreviewPanel")
        self.preview_panel.setMinimumWidth(280)
        self.preview_panel.setMaximumWidth(360)
        self._build_preview_panel()
        self.main_splitter.addWidget(self.preview_panel)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setSizes([850, 320])

        self.status_bar = self.statusBar()
        self.status_bar.showMessage(self._("ready"))

    def _build_top_bar(self, parent):
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(44)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(0)

        # Tab buttons
        self.tab_installed = QPushButton(self._("tab_installed"))
        self.tab_installed.setObjectName("TabBtnActive")
        self.tab_installed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_installed.clicked.connect(lambda: self._switch_tab(0))

        self.tab_workshop = QPushButton(self._("tab_workshop"))
        self.tab_workshop.setObjectName("TabBtn")
        self.tab_workshop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_workshop.clicked.connect(lambda: self._switch_tab(1))

        h.addWidget(self.tab_installed)
        h.addWidget(self.tab_workshop)
        h.addStretch()

        # Right-side bar buttons
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFixedHeight(24)
        sep1.setStyleSheet("color: #333;")
        h.addWidget(sep1)

        btn_settings = QPushButton(self._("tab_settings"))
        btn_settings.setObjectName("BarButton")
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_settings.clicked.connect(lambda: self._switch_tab(2))
        h.addWidget(btn_settings)

        parent.addWidget(bar)

    def _switch_tab(self, index):
        self.content_stack.setCurrentIndex(index)
        # Update tab button styles
        self.tab_installed.setObjectName("TabBtnActive" if index == 0 else "TabBtn")
        self.tab_workshop.setObjectName("TabBtnActive" if index == 1 else "TabBtn")
        # Force style refresh
        self.tab_installed.setStyleSheet("")
        self.tab_workshop.setStyleSheet("")
        # Show/hide preview panel; give left panel full width on non-installed tabs
        show_preview = index == 0
        self.preview_panel.setVisible(show_preview)
        total = self.main_splitter.width()
        if show_preview:
            self.main_splitter.setSizes([total - 320, 320])
        else:
            self.main_splitter.setSizes([total, 0])
        # Re-render workshop grid when switching to workshop tab
        if index == 1 and self.workshop_items:
            QTimer.singleShot(0, self._render_ws_grid)

    # ── Installed Page ──────────────────────────────────────────────────

    def _build_installed_page(self):
        v = QVBoxLayout(self.page_installed)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Explorer top bar: search + sort + actions
        ebar = QWidget()
        ebar.setObjectName("ExplorerBar")
        ebar.setFixedHeight(44)
        eh = QHBoxLayout(ebar)
        eh.setContentsMargins(12, 6, 12, 6)
        eh.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchField")
        self.search_input.setPlaceholderText(self._("search_dots"))
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self.filter_wallpapers)
        eh.addWidget(self.search_input)

        self.btn_scan = QPushButton(self._("scan_library"))
        self.btn_scan.setObjectName("PrimaryBtn")
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.clicked.connect(self.start_scan)
        eh.addWidget(self.btn_scan)

        self.btn_select_folder = QPushButton(self._("open_folder"))
        self.btn_select_folder.setObjectName("SecBtn")
        self.btn_select_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_folder.clicked.connect(self.manual_scan)
        eh.addWidget(self.btn_select_folder)

        eh.addStretch()

        self.btn_reverse_sorted = QPushButton("↑")
        self.btn_reverse_sorted.setObjectName("BarButton")
        self.btn_reverse_sorted.setFixedSize(32, 32)
        self.btn_reverse_sorted.clicked.connect(self.reverse_sorted)
        eh.addWidget(self.btn_reverse_sorted)

        self.sorting_type = QComboBox()
        self.sorting_type.addItems([self._("sort_name"), self._("sort_subscription_date")])
        self.sorting_type.setFixedWidth(150)
        self.sort_reversed_state = False
        self.sorting_type.currentTextChanged.connect(self.on_sort_change)
        eh.addWidget(self.sorting_type)

        v.addWidget(ebar)

        # Wallpaper grid
        self.list_wallpapers = QListWidget()
        self.list_wallpapers.setObjectName("WallpaperGrid")
        self.list_wallpapers.setMovement(QListWidget.Movement.Static)
        self.list_wallpapers.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_wallpapers.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_wallpapers.setGridSize(QSize(180, 210))
        self.list_wallpapers.setSpacing(8)
        self.list_wallpapers.setWordWrap(True)
        self.list_wallpapers.setIconSize(QSize(160, 160))
        self.list_wallpapers.setItemDelegate(WallpaperDelegate(self.list_wallpapers))
        self.list_wallpapers.setMouseTracking(True)
        self.list_wallpapers.itemClicked.connect(self.on_wallpaper_selected)
        self.list_wallpapers.itemDoubleClicked.connect(self.run_wallpaper)
        self.list_wallpapers.setItemAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.list_wallpapers, 1)

        # Bottom bar: Open Wallpaper button
        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 6, 12, 6)
        self.btn_set_library = QPushButton(self._("set_wallpaper"))
        self.btn_set_library.setObjectName("PrimaryBtn")
        self.btn_set_library.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_set_library.clicked.connect(self.run_wallpaper)
        bottom.addWidget(self.btn_set_library)
        bottom.addStretch()
        v.addLayout(bottom)

    # ── Preview Panel (right side) ──────────────────────────────────────

    def _build_preview_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)
        v.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Preview image
        self.preview_image = QLabel()
        self.preview_image.setObjectName("PreviewImage")
        self.preview_image.setFixedSize(260, 260)
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setStyleSheet(
            "background-color: #111; border: 3px solid #fff; border-radius: 12px; color: #666;"
        )
        self.preview_image.setText(self._("no_wallpaper_selected"))
        v.addWidget(self.preview_image, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        self.preview_title = QLabel(self._("select_a_wallpaper"))
        self.preview_title.setObjectName("PreviewTitle")
        self.preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_title.setWordWrap(True)
        v.addWidget(self.preview_title)

        # Type + Size
        self.preview_meta = QLabel("")
        self.preview_meta.setObjectName("PreviewMeta")
        self.preview_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.preview_meta)

        # Tags row
        self.preview_tags_layout = QHBoxLayout()
        self.preview_tags_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_tags_layout.setSpacing(4)
        v.addLayout(self.preview_tags_layout)

        # ── Properties Section ──
        prop_header = QHBoxLayout()
        prop_header.setSpacing(4)
        prop_lbl = QLabel(self._("properties_section"))
        prop_lbl.setObjectName("SectionDivider")
        prop_header.addWidget(prop_lbl)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #0A84FF;")
        prop_header.addWidget(line, 1)
        v.addLayout(prop_header)

        # Screen selector
        screen_row = QHBoxLayout()
        screen_lbl = QLabel(self._("screen"))
        screen_lbl.setStyleSheet("font-size: 12px; color: #aaa;")
        screen_row.addWidget(screen_lbl)
        self.screen_combo = QComboBox()
        self.screen_combo.setEditable(True)
        screen_row.addWidget(self.screen_combo, 1)
        v.addLayout(screen_row)

        # Volume
        vol_row = QHBoxLayout()
        vol_lbl = QLabel(self._("volume"))
        vol_lbl.setStyleSheet("font-size: 12px; color: #aaa;")
        vol_row.addWidget(vol_lbl)
        self.chk_silent = QCheckBox(self._("mute"))
        self.chk_silent.clicked.connect(self.run_wallpaper)
        vol_row.addWidget(self.chk_silent)
        self.slider_volume = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(15)
        self.slider_volume.sliderReleased.connect(self.run_wallpaper)
        vol_row.addWidget(self.slider_volume, 1)
        v.addLayout(vol_row)

        # FPS
        fps_row = QHBoxLayout()
        fps_lbl = QLabel(self._("fps"))
        fps_lbl.setStyleSheet("font-size: 12px; color: #aaa;")
        fps_row.addWidget(fps_lbl)
        self.slider_fps = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider_fps.setRange(10, 144)
        self.slider_fps.setValue(30)
        self.slider_fps.sliderReleased.connect(self.run_wallpaper)
        fps_row.addWidget(self.slider_fps, 1)
        self.fps_value_label = QLabel("30")
        self.fps_value_label.setStyleSheet("font-size: 12px; color: #888; min-width: 24px;")
        self.slider_fps.valueChanged.connect(lambda val: self.fps_value_label.setText(str(val)))
        fps_row.addWidget(self.fps_value_label)
        v.addLayout(fps_row)

        # Scaling
        scale_row = QHBoxLayout()
        scale_lbl = QLabel(self._("scaling"))
        scale_lbl.setStyleSheet("font-size: 12px; color: #aaa;")
        scale_row.addWidget(scale_lbl)
        self.combo_scaling = QComboBox()
        self.combo_scaling.addItems(['default', 'stretch', 'fit', 'fill'])
        if "scale" in self.config:
            self.combo_scaling.setCurrentText(self.config["scale"])
        self.combo_scaling.currentTextChanged.connect(self.run_wallpaper)
        scale_row.addWidget(self.combo_scaling, 1)
        v.addLayout(scale_row)

        # Clamp
        clamp_row = QHBoxLayout()
        clamp_lbl = QLabel(self._("clamp"))
        clamp_lbl.setStyleSheet("font-size: 12px; color: #aaa;")
        clamp_row.addWidget(clamp_lbl)
        self.combo_clamp = QComboBox()
        self.combo_clamp.addItems(['clamp', 'border', 'repeat'])
        if "clamp" in self.config:
            self.combo_clamp.setCurrentText(self.config["clamp"])
        self.combo_clamp.currentTextChanged.connect(self.run_wallpaper)
        clamp_row.addWidget(self.combo_clamp, 1)
        v.addLayout(clamp_row)

        # Checkboxes
        self.chk_no_automute = QCheckBox(self._("no_automute"))
        self.chk_no_automute.clicked.connect(self.run_wallpaper)
        v.addWidget(self.chk_no_automute)
        self.chk_no_proc = QCheckBox(self._("no_audio_processing"))
        self.chk_no_proc.clicked.connect(self.run_wallpaper)
        v.addWidget(self.chk_no_proc)
        self.chk_mouse = QCheckBox(self._("disable_mouse"))
        self.chk_mouse.clicked.connect(self.run_wallpaper)
        v.addWidget(self.chk_mouse)
        self.chk_parallax = QCheckBox(self._("disable_parallax"))
        self.chk_parallax.clicked.connect(self.run_wallpaper)
        v.addWidget(self.chk_parallax)
        self.chk_fs_pause = QCheckBox(self._("no_fullscreen_pause"))
        self.chk_fs_pause.clicked.connect(self.run_wallpaper)
        v.addWidget(self.chk_fs_pause)
        self.chk_windowed_mode = QCheckBox(self._("windowed_mode"))
        self.chk_windowed_mode.clicked.connect(self.run_wallpaper)
        v.addWidget(self.chk_windowed_mode)

        # Hidden wallpaper ID field
        self.wp_id_input = QLineEdit()
        self.wp_id_input.setPlaceholderText(self._("wallpaper_id_placeholder"))
        self.wp_id_input.textChanged.connect(self.on_wallpaper_id_changed)
        v.addWidget(self.wp_id_input)

        # Custom args
        self.input_custom_args = QLineEdit()
        self.input_custom_args.setPlaceholderText(self._("custom_args_placeholder"))
        v.addWidget(self.input_custom_args)

        # Properties
        prop2_header = QHBoxLayout()
        prop2_header.setSpacing(4)
        prop2_lbl = QLabel(self._("wallpaper_properties"))
        prop2_lbl.setObjectName("SectionDivider")
        prop2_header.addWidget(prop2_lbl)
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("color: #0A84FF;")
        prop2_header.addWidget(line2, 1)
        v.addLayout(prop2_header)

        props_row = QHBoxLayout()
        self.properties_combo = QComboBox()
        self.properties_combo.setEditable(False)
        self.properties_combo.addItem(self._("select_property"), None)
        self.properties_combo.currentIndexChanged.connect(self.on_property_selected)
        props_row.addWidget(self.properties_combo, 1)
        v.addLayout(props_row)

        pval_row = QHBoxLayout()
        self.properties_type = QLabel()
        self.properties_type.setStyleSheet("font-size: 11px; color: #888;")
        pval_row.addWidget(self.properties_type)
        self.properties_value = QLineEdit()
        self.properties_value.setPlaceholderText(self._("value"))
        self.properties_value.editingFinished.connect(self.apply_property_value)
        pval_row.addWidget(self.properties_value, 1)
        v.addLayout(pval_row)

        props_btn_row = QHBoxLayout()
        self.btn_load_props = QPushButton(self._("load_props"))
        self.btn_load_props.setObjectName("SecBtn")
        self.btn_load_props.clicked.connect(self.load_properties)
        props_btn_row.addWidget(self.btn_load_props)
        self.btn_apply_prop = QPushButton(self._("apply"))
        self.btn_apply_prop.setObjectName("PrimaryBtn")
        self.btn_apply_prop.clicked.connect(self.apply_property_value)
        props_btn_row.addWidget(self.btn_apply_prop)
        v.addLayout(props_btn_row)

        # Action buttons
        v.addSpacing(8)
        act_header = QHBoxLayout()
        act_lbl = QLabel(self._("actions"))
        act_lbl.setObjectName("SectionDivider")
        act_header.addWidget(act_lbl)
        line3 = QFrame()
        line3.setFrameShape(QFrame.Shape.HLine)
        line3.setStyleSheet("color: #0A84FF;")
        act_header.addWidget(line3, 1)
        v.addLayout(act_header)

        self.btn_set = QPushButton(self._("set_wallpaper"))
        self.btn_set.setObjectName("PrimaryBtn")
        self.btn_set.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_set.clicked.connect(self.run_wallpaper)
        v.addWidget(self.btn_set)

        self.btn_show_log = QPushButton(self._("show_log"))
        self.btn_show_log.setObjectName("SecBtn")
        self.btn_show_log.clicked.connect(self.show_log_file)
        v.addWidget(self.btn_show_log)

        self.btn_stop = QPushButton(self._("stop_all"))
        self.btn_stop.setObjectName("DangerBtn")
        self.btn_stop.clicked.connect(self.stop_wallpapers)
        v.addWidget(self.btn_stop)

        v.addStretch()

        scroll.setWidget(inner)
        layout = QVBoxLayout(self.preview_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    # ── Settings Page ───────────────────────────────────────────────────

    def _build_settings_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(32, 32, 32, 32)
        v.setSpacing(16)
        v.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(self._("tab_settings"))
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #fff;")
        v.addWidget(title)

        # Language
        lang_row = QHBoxLayout()
        lang_lbl = QLabel(self._("language"))
        lang_lbl.setStyleSheet("font-size: 13px; color: #aaa;")
        lang_row.addWidget(lang_lbl)
        self.combo_lang = QComboBox()
        self.combo_lang.currentTextChanged.connect(self.change_lang)
        lang_row.addWidget(self.combo_lang, 1)
        v.addLayout(lang_row)

        v.addStretch()
        scroll.setWidget(inner)

        layout = QVBoxLayout(self.page_settings)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    # ── Workshop Page ───────────────────────────────────────────────────

    def _build_workshop_page(self):
        v = QVBoxLayout(self.page_workshop)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.workshop_stack = QStackedWidget()
        v.addWidget(self.workshop_stack)

        self._build_steamcmd_missing_view()
        self._build_steam_login_view()
        self._build_workshop_browser_view()
        self._update_workshop_view_state()

    def _build_steamcmd_missing_view(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(16)

        icon = QLabel("!")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 40px; color: #666;")
        v.addWidget(icon)

        title = QLabel(self._("steamcmd_not_found_title"))
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #fff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        desc = QLabel(self._("steamcmd_desc"))
        desc.setStyleSheet("font-size: 13px; color: #888;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        v.addWidget(desc)

        cmd_row = QHBoxLayout()
        cmd_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cmd = QLabel("yay -S steamcmd")
        cmd.setStyleSheet("font-family: monospace; font-size: 13px; background: #222; padding: 8px 14px; border-radius: 6px; color: #fff; border: 1px solid #333;")
        cmd_row.addWidget(cmd)
        self.btn_copy_cmd = QPushButton(self._("copy"))
        self.btn_copy_cmd.setObjectName("SecBtn")
        self.btn_copy_cmd.setFixedWidth(60)
        self.btn_copy_cmd.clicked.connect(lambda: (
            QApplication.clipboard().setText("yay -S steamcmd"),
            self.btn_copy_cmd.setText(self._("copied")),
            QTimer.singleShot(2000, lambda: self.btn_copy_cmd.setText(self._("copy")))
        ))
        cmd_row.addWidget(self.btn_copy_cmd)
        v.addLayout(cmd_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333;")
        sep.setFixedWidth(200)
        sh = QHBoxLayout()
        sh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sh.addWidget(sep)
        v.addLayout(sh)

        or_lbl = QLabel(self._("locate_steamcmd"))
        or_lbl.setStyleSheet("font-size: 13px; color: #888;")
        or_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(or_lbl)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_browse = QPushButton(self._("browse_dots"))
        btn_browse.setObjectName("SecBtn")
        btn_browse.clicked.connect(self._browse_steamcmd)
        btn_row.addWidget(btn_browse)
        btn_re = QPushButton(self._("redetect"))
        btn_re.setObjectName("LinkBtn")
        btn_re.clicked.connect(self._redetect_steamcmd)
        btn_row.addWidget(btn_re)
        v.addLayout(btn_row)

        self.workshop_stack.addWidget(page)

    def _build_steam_login_view(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(16)

        title = QLabel(self._("steam_login_title"))
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #fff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        desc = QLabel(self._("steam_login_desc"))
        desc.setStyleSheet("font-size: 13px; color: #888;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        v.addWidget(desc)

        self.steam_username_input = QLineEdit()
        self.steam_username_input.setPlaceholderText(self._("steam_username"))
        self.steam_username_input.setFixedWidth(280)
        v.addWidget(self.steam_username_input, alignment=Qt.AlignmentFlag.AlignCenter)

        self.steam_password_input = QLineEdit()
        self.steam_password_input.setPlaceholderText(self._("password"))
        self.steam_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.steam_password_input.setFixedWidth(280)
        v.addWidget(self.steam_password_input, alignment=Qt.AlignmentFlag.AlignCenter)

        self.steam_guard_input = QLineEdit()
        self.steam_guard_input.setPlaceholderText(self._("steam_guard_code"))
        self.steam_guard_input.setFixedWidth(280)
        self.steam_guard_input.hide()
        v.addWidget(self.steam_guard_input, alignment=Qt.AlignmentFlag.AlignCenter)

        self.steam_login_error = QLabel("")
        self.steam_login_error.setStyleSheet("font-size: 12px; color: #FF453A;")
        self.steam_login_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.steam_login_error.setWordWrap(True)
        self.steam_login_error.hide()
        v.addWidget(self.steam_login_error, alignment=Qt.AlignmentFlag.AlignCenter)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.setSpacing(12)
        self.btn_steam_login = QPushButton(self._("log_in"))
        self.btn_steam_login.setObjectName("PrimaryBtn")
        self.btn_steam_login.clicked.connect(self._steam_login)
        btn_row.addWidget(self.btn_steam_login)
        self.btn_steam_cached = QPushButton(self._("use_cached_session"))
        self.btn_steam_cached.setObjectName("SecBtn")
        self.btn_steam_cached.clicked.connect(self._steam_login_cached)
        btn_row.addWidget(self.btn_steam_cached)
        v.addLayout(btn_row)

        self.steam_login_progress = QLabel(self._("authenticating_steam"))
        self.steam_login_progress.setStyleSheet("font-size: 12px; color: #888;")
        self.steam_login_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.steam_login_progress.hide()
        v.addWidget(self.steam_login_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        # API key
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333;")
        sep.setFixedWidth(300)
        sh = QHBoxLayout()
        sh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sh.addWidget(sep)
        v.addLayout(sh)

        api_desc = QLabel(self._("api_key_desc"))
        api_desc.setStyleSheet("font-size: 12px; color: #888;")
        api_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(api_desc)

        self._add_api_key_row(v, is_login=True)

        self.workshop_stack.addWidget(page)

    def _add_api_key_row(self, parent, is_login=False):
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp = QLineEdit()
        inp.setPlaceholderText(self._("steam_api_key"))
        inp.setFixedWidth(300)
        inp.setText(self.workshop_api_key)
        # Keep strong reference to prevent GC/deletion crashes
        if not hasattr(self, '_api_key_inputs'):
            self._api_key_inputs = []
        self._api_key_inputs.append(inp)
        if is_login:
            self._login_api_input = inp
        row.addWidget(inp)
        btn_text = self._("save_button") if is_login else self._("save_and_search_button")
        btn = QPushButton(btn_text)
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(100 if not is_login else 60)
        # Capture inp by reference safely
        def _on_save(_, ref=inp):
            try:
                text = ref.text()
            except RuntimeError:
                text = self.workshop_api_key
            self._save_api_key_from(text)
        btn.clicked.connect(_on_save)
        row.addWidget(btn)
        parent.addLayout(row)

        link = QLabel(f'<a href="https://steamcommunity.com/dev/apikey" style="color: #0A84FF; font-size: 11px;">{self._("api_key_link")}</a>')
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.addWidget(link)

    def _build_workshop_browser_view(self):
        page = QWidget()
        main_v = QVBoxLayout(page)
        main_v.setContentsMargins(16, 8, 16, 8)
        main_v.setSpacing(8)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.ws_search = QLineEdit()
        self.ws_search.setObjectName("SearchField")
        self.ws_search.setPlaceholderText(self._("search_wallpapers"))
        self.ws_search.returnPressed.connect(self._ws_search)
        search_row.addWidget(self.ws_search)

        btn_clear = QPushButton("X")
        btn_clear.setObjectName("BarButton")
        btn_clear.setFixedSize(30, 30)
        btn_clear.clicked.connect(self._ws_clear_search)
        search_row.addWidget(btn_clear)

        self.ws_sort_combo = QComboBox()
        self.ws_sort_combo.setFixedWidth(160)
        for s in SortOrder:
            self.ws_sort_combo.addItem(s.display_name, s)
        self.ws_sort_combo.currentIndexChanged.connect(self._ws_sort_changed)
        search_row.addWidget(self.ws_sort_combo)
        main_v.addLayout(search_row)

        # Tag filters
        self.ws_tags_layout = QHBoxLayout()
        self.ws_tags_layout.setSpacing(4)
        tags_w = QWidget()
        tags_w.setLayout(self.ws_tags_layout)
        tags_scroll = QScrollArea()
        tags_scroll.setWidget(tags_w)
        tags_scroll.setWidgetResizable(True)
        tags_scroll.setFixedHeight(34)
        tags_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tags_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tags_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._populate_tag_buttons()
        main_v.addWidget(tags_scroll)

        # Results stack
        self.ws_results_stack = QStackedWidget()

        # 0: Empty
        empty = QWidget()
        ev = QVBoxLayout(empty)
        ev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(self._("search_workshop_title"))
        lbl.setStyleSheet("font-size: 20px; font-weight: 600; color: #fff;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(lbl)
        sub = QLabel(self._("search_workshop_desc"))
        sub.setStyleSheet("font-size: 13px; color: #888;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(sub)
        self.ws_empty_api = QWidget()
        api_v = QVBoxLayout(self.ws_empty_api)
        api_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        api_hint = QLabel(self._("api_key_required"))
        api_hint.setStyleSheet("font-size: 12px; color: #888;")
        api_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        api_v.addWidget(api_hint)
        self._add_api_key_row(api_v)
        self.ws_empty_api.setVisible(not bool(self.workshop_api_key))
        ev.addWidget(self.ws_empty_api)
        self.ws_results_stack.addWidget(empty)

        # 1: Loading
        loading = QWidget()
        lv = QVBoxLayout(loading)
        lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll = QLabel(self._("searching_workshop"))
        ll.setStyleSheet("font-size: 14px; color: #888;")
        ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lv.addWidget(ll)
        self.ws_results_stack.addWidget(loading)

        # 2: Error
        err_page = QWidget()
        erv = QVBoxLayout(err_page)
        erv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ws_error_lbl = QLabel("")
        self.ws_error_lbl.setStyleSheet("font-size: 13px; color: #FF453A;")
        self.ws_error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ws_error_lbl.setWordWrap(True)
        erv.addWidget(self.ws_error_lbl)
        self._add_api_key_row(erv)
        self.ws_results_stack.addWidget(err_page)

        # 3: Results grid
        results_w = QWidget()
        results_v = QVBoxLayout(results_w)
        results_v.setContentsMargins(0, 0, 0, 0)
        self.ws_scroll = QScrollArea()
        self.ws_scroll.setWidgetResizable(True)
        self.ws_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.ws_grid_widget = QWidget()
        self.ws_scroll.setWidget(self.ws_grid_widget)
        results_v.addWidget(self.ws_scroll)
        self.btn_load_more = QPushButton(self._("load_more"))
        self.btn_load_more.setObjectName("SecBtn")
        self.btn_load_more.clicked.connect(self._ws_load_more)
        self.btn_load_more.hide()
        results_v.addWidget(self.btn_load_more, alignment=Qt.AlignmentFlag.AlignCenter)
        self.ws_results_stack.addWidget(results_w)

        self.ws_results_stack.setCurrentIndex(0)
        main_v.addWidget(self.ws_results_stack, 1)
        self.workshop_stack.addWidget(page)

    # ── Workshop Helpers ────────────────────────────────────────────────

    def _populate_tag_buttons(self):
        while self.ws_tags_layout.count():
            child = self.ws_tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        lbl_r = QLabel(self._("rating_label"))
        lbl_r.setStyleSheet("font-size: 11px; color: #888;")
        self.ws_tags_layout.addWidget(lbl_r)
        for t in CONTENT_RATING_TAGS: self._add_tag_btn(t)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine); sep.setFixedHeight(20); sep.setStyleSheet("color: #333;")
        self.ws_tags_layout.addWidget(sep)
        lbl_t = QLabel(self._("type_label"))
        lbl_t.setStyleSheet("font-size: 11px; color: #888;")
        self.ws_tags_layout.addWidget(lbl_t)
        for t in TYPE_TAGS: self._add_tag_btn(t)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine); sep2.setFixedHeight(20); sep2.setStyleSheet("color: #333;")
        self.ws_tags_layout.addWidget(sep2)
        for t in GENRE_TAGS: self._add_tag_btn(t)
        self.ws_tags_layout.addStretch()

    def _add_tag_btn(self, tag):
        btn = QPushButton(tag)
        active = tag in self.workshop_selected_tags
        btn.setObjectName("TagBtnActive" if active else "TagBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.clicked.connect(lambda _, t=tag: self._toggle_ws_tag(t))
        self.ws_tags_layout.addWidget(btn)

    def _toggle_ws_tag(self, tag):
        if tag in self.workshop_selected_tags:
            self.workshop_selected_tags.remove(tag)
        else:
            self.workshop_selected_tags.append(tag)
        self._populate_tag_buttons()
        self.workshop_page_num = 1
        self._ws_search()

    def _update_workshop_view_state(self):
        if not self.steam_cmd.is_installed:
            self.workshop_stack.setCurrentIndex(0)
        elif not self.steam_cmd.is_logged_in:
            self.workshop_stack.setCurrentIndex(1)
        else:
            self.workshop_stack.setCurrentIndex(2)

    def _browse_steamcmd(self):
        path = QFileDialog.getOpenFileName(self, self._("select_steamcmd"))[0]
        if path and self.steam_cmd.set_custom_path(path):
            self._update_workshop_view_state()

    def _redetect_steamcmd(self):
        self.steam_cmd.redetect()
        self._update_workshop_view_state()
        self.status_bar.showMessage(self._("steamcmd_found") if self.steam_cmd.is_installed else self._("steamcmd_still_not_found"))

    def _steam_login(self):
        u, p = self.steam_username_input.text().strip(), self.steam_password_input.text()
        g = self.steam_guard_input.text().strip()
        if not u or not p: return
        self.btn_steam_login.setEnabled(False)
        self.btn_steam_cached.setEnabled(False)
        self.steam_login_progress.show()
        self.steam_cmd.login(u, p, g)

    def _steam_login_cached(self):
        u = self.steam_username_input.text().strip()
        if not u: return
        self.btn_steam_login.setEnabled(False)
        self.btn_steam_cached.setEnabled(False)
        self.steam_login_progress.show()
        self.steam_cmd.login_cached(u)

    def _on_steam_login_changed(self):
        self.btn_steam_login.setEnabled(True)
        self.btn_steam_cached.setEnabled(True)
        self.steam_login_progress.setVisible(self.steam_cmd.is_logging_in)
        if self.steam_cmd.login_error:
            self.steam_login_error.setText(self.steam_cmd.login_error)
            self.steam_login_error.show()
            if "Steam Guard" in self.steam_cmd.login_error:
                self.steam_guard_input.show()
        elif self.steam_cmd.is_logged_in:
            self.steam_login_error.hide()
            self.config["steam_username"] = self.steam_cmd.username
            self.save_config()
            self._update_workshop_view_state()
            if not self.workshop_items:
                QTimer.singleShot(200, self._ws_search)

    def _save_api_key_from(self, key_text):
        key = key_text.strip()
        if key:
            self.workshop_api_key = key
            self.config["steam_api_key"] = key
            self.save_config()
            if hasattr(self, 'ws_empty_api'):
                self.ws_empty_api.hide()
            self._ws_search()

    def _ws_search(self):
        self.workshop_page_num = 1
        self.workshop_items = []
        self.workshop_search_text = self.ws_search.text().strip() if hasattr(self, 'ws_search') else ""
        self.ws_results_stack.setCurrentIndex(1)
        self._do_ws_search()

    def _ws_load_more(self):
        self.workshop_page_num += 1
        self.btn_load_more.setEnabled(False)
        self._do_ws_search(append=True)

    def _ws_sort_changed(self):
        self.workshop_sort_order = self.ws_sort_combo.currentData()
        self.workshop_page_num = 1
        self.workshop_items = []
        self.ws_results_stack.setCurrentIndex(1)
        self._do_ws_search()

    def _ws_clear_search(self):
        self.ws_search.clear()
        self._ws_search()

    def _do_ws_search(self, append=False):
        def _search():
            return search_items(
                api_key=self.workshop_api_key,
                query=self.workshop_search_text,
                tags=self.workshop_selected_tags,
                sort_order=self.workshop_sort_order,
                page=self.workshop_page_num,
            )
        self._ws_task = AsyncTask(_search, callback=lambda r: self._ws_search_done(r, append))

    def _ws_search_done(self, result, append=False):
        self.btn_load_more.setEnabled(True)
        if isinstance(result, Exception):
            self.ws_error_lbl.setText(str(result))
            self.ws_results_stack.setCurrentIndex(2)
            return
        if isinstance(result, list):
            if append:
                self.workshop_items.extend(result)
            else:
                self.workshop_items = result
            if not self.workshop_items:
                self.ws_results_stack.setCurrentIndex(0)
                return
            # Switch to results page first so the scroll area gets laid out at full width
            self.ws_results_stack.setCurrentIndex(3)
            self.btn_load_more.setVisible(len(result) >= 20)
            # Defer grid render so layout settles
            QTimer.singleShot(0, self._render_ws_grid)

    def _render_ws_grid(self):
        # Ensure layout is finalized before measuring; defer if viewport has no real width yet
        vw = self.ws_scroll.viewport().width()
        if vw < 100 or self.content_stack.currentIndex() != 1:
            QTimer.singleShot(0, self._render_ws_grid)
            return
        old = self.ws_scroll.takeWidget()
        self.ws_grid_widget = QWidget()
        self.ws_grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(self.ws_grid_widget)
        grid.setSpacing(10)
        grid.setContentsMargins(8, 8, 8, 8)
        card_w = 200
        spacing = 10
        margins = 16
        avail = vw - margins
        cols = max(1, (avail + spacing) // (card_w + spacing))
        for i, item in enumerate(self.workshop_items):
            card = self._make_ws_card(item)
            grid.addWidget(card, i // cols, i % cols)
        self.ws_scroll.setWidget(self.ws_grid_widget)
        if old:
            old.deleteLater()

    def _make_ws_card(self, item: WorkshopItem) -> QWidget:
        card = QFrame()
        card.setObjectName("WorkshopCard")
        card.setFixedSize(200, 210)
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 8)
        v.setSpacing(4)

        img = QLabel()
        img.setFixedSize(200, 112)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("background: #111; border-top-left-radius: 8px; border-top-right-radius: 8px; border: none;")
        v.addWidget(img)
        if item.preview_url:
            self._load_preview_async(item.preview_url, img)

        info = QVBoxLayout()
        info.setContentsMargins(8, 2, 8, 0)
        info.setSpacing(2)
        t = QLabel(item.title)
        t.setStyleSheet("font-size: 12px; font-weight: 500; color: #fff;")
        t.setWordWrap(True)
        t.setMaximumHeight(32)
        info.addWidget(t)

        meta = QHBoxLayout()
        meta.setSpacing(4)
        if item.tags:
            tl = QLabel(", ".join(item.tags[:2]))
            tl.setStyleSheet("font-size: 11px; color: #888;")
            meta.addWidget(tl)
        meta.addStretch()
        if item.subscriptions > 0:
            sl = QLabel(self._fmt_count(item.subscriptions))
            sl.setStyleSheet("font-size: 11px; color: #888;")
            meta.addWidget(sl)
        info.addLayout(meta)

        dl = self.steam_cmd.download_progress.get(item.id)
        if dl and dl.status == DownloadStatus.DOWNLOADING:
            s = QLabel(dl.message)
            s.setStyleSheet("font-size: 11px; color: #888;")
            info.addWidget(s)
        elif dl and dl.status == DownloadStatus.COMPLETED:
            s = QLabel(self._("downloaded"))
            s.setStyleSheet("font-size: 11px; color: #30D158;")
            info.addWidget(s)
        elif dl and dl.status == DownloadStatus.FAILED:
            s = QLabel(self._("failed"))
            s.setStyleSheet("font-size: 11px; color: #FF453A;")
            s.setToolTip(dl.message)
            info.addWidget(s)
        elif self.steam_cmd.is_logged_in:
            b = QPushButton(self._("download"))
            b.setObjectName("DlBtn")
            b.setFixedHeight(22)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, wid=item.id: self._download_ws_item(wid))
            info.addWidget(b)
        else:
            s = QLabel(self._("login_to_download"))
            s.setStyleSheet("font-size: 11px; color: #666;")
            info.addWidget(s)

        v.addLayout(info)
        return card

    def _load_preview_async(self, url, label):
        if url in self._workshop_image_cache:
            pm = self._workshop_image_cache[url]
            label.setPixmap(pm.scaled(200, 112, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            return
        def _fetch():
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.read()
            except:
                return None
        def _done(data):
            if data:
                img = QImage()
                img.loadFromData(data)
                pm = QPixmap.fromImage(img)
                self._workshop_image_cache[url] = pm
                label.setPixmap(pm.scaled(200, 112, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        self._img_threads.append(AsyncTask(_fetch, callback=_done))

    def _download_ws_item(self, wid):
        dirs = self.get_steam_workshop_dirs()
        dest = list(dirs)[0] if dirs else os.path.expanduser("~/.local/share/Steam/steamapps/workshop/content/431960")
        os.makedirs(dest, exist_ok=True)
        self.steam_cmd.download_workshop_item(wid, dest)
        self._render_ws_grid()

    def _on_download_updated(self, wid):
        if self.ws_results_stack.currentIndex() == 3:
            self._render_ws_grid()
        dl = self.steam_cmd.download_progress.get(wid)
        if dl and dl.status == DownloadStatus.COMPLETED:
            self.start_scan()

    @staticmethod
    def _fmt_count(n):
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000: return f"{n/1_000:.1f}K"
        return str(n)

    # ── Library / Scanning ──────────────────────────────────────────────

    def on_library_changed_auto(self):
        if self.btn_scan.isEnabled():
            self.start_scan()

    def get_steam_workshop_dirs(self):
        workshop_dirs = set()
        base_paths = [
            os.path.expanduser("~/.local/share/Steam"),
            os.path.expanduser("~/.steam/steam"),
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam"),
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.data/Steam"),
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.steam/steam"),
        ]
        lib_configs = [
            os.path.expanduser("~/.local/share/Steam/steamapps/libraryfolders.vdf"),
            os.path.expanduser("~/.steam/steam/steamapps/libraryfolders.vdf"),
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/libraryfolders.vdf")
        ]
        for cfg in lib_configs:
            if os.path.isfile(cfg):
                try:
                    with open(cfg, 'r', encoding='utf-8') as f:
                        content = f.read()
                        paths = re.findall(r'"path"\s+"([^"]+)"', content)
                        for p in paths:
                            if os.path.isdir(p):
                                base_paths.append(p)
                except: pass
        base_paths = list(set(base_paths))
        base_paths.extend(glob.glob(os.path.expanduser("~/snap/steam/*/.local/share/Steam")))
        base_paths.extend(glob.glob(os.path.expanduser("~/snap/steam/*/.steam/steam")))
        for base in base_paths:
            if not os.path.exists(base): continue
            p_workshop = os.path.join(base, "steamapps/workshop/content/431960")
            if os.path.isdir(p_workshop):
                workshop_dirs.add(p_workshop)
            p_presets = os.path.join(base, "steamapps/common/wallpaper_engine/assets/presets")
            if os.path.isdir(p_presets):
                workshop_dirs.add(p_presets)
        if not workshop_dirs:
            try:
                search_roots = [os.path.expanduser("~")]
                cmd = ["find"] + search_roots + ["-maxdepth", "6", "-type", "d", "-name", "431960"]
                result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.DEVNULL)
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if os.path.isdir(line):
                            workshop_dirs.add(line)
            except Exception as e:
                logging.error(f"Deep scan error: {e}")
        return workshop_dirs

    def scan_logic(self, manual_dir=None):
        workshop_dirs = self.get_steam_workshop_dirs()
        is_append = manual_dir is not None
        if manual_dir:
            workshop_dirs.add(manual_dir)
        wallpapers = []
        seen = set()
        for w_dir in workshop_dirs:
            try:
                proj_self = os.path.join(w_dir, "project.json")
                if os.path.isfile(proj_self):
                    try:
                        with open(proj_self, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            item_id = os.path.basename(w_dir)
                            dep_id = get_dependency_id(data)
                            wallpapers.append({"title": data.get("title", "Untitled"), "id": item_id, "path": w_dir, "preview": data.get("preview"), "dependency": dep_id})
                            seen.add(item_id)
                    except: pass
                for item_id in os.listdir(w_dir):
                    if item_id in seen: continue
                    path = os.path.join(w_dir, item_id)
                    proj = os.path.join(path, "project.json")
                    if os.path.isfile(proj):
                        try:
                            with open(proj, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                dep_id = get_dependency_id(data)
                                wallpapers.append({"title": data.get("title", "Untitled"), "id": item_id, "path": path, "preview": data.get("preview"), "dependency": dep_id})
                                seen.add(item_id)
                        except: pass
            except: pass
        return wallpapers, is_append, list(workshop_dirs)

    def start_scan(self):
        self.status_bar.showMessage(self._("scanning_wallpapers"))
        self.btn_scan.setEnabled(False)
        self.search_input.clear()
        self._scan_task = AsyncTask(self.scan_logic, callback=self.scan_finished)

    def manual_scan(self):
        directory = QFileDialog.getExistingDirectory(self, self._("select_wallpaper_folder"))
        if directory:
            self.status_bar.showMessage(self._("scanning_folder"))
            self.btn_scan.setEnabled(False)
            self._scan_task = AsyncTask(self.scan_logic, manual_dir=directory, callback=self.scan_finished)

    def scan_finished(self, result):
        if isinstance(result, Exception):
            self.btn_scan.setEnabled(True)
            self.status_bar.showMessage(self._("scan_error", error=result))
            return
        wallpapers, is_append, scanned_dirs = result
        if hasattr(self, 'watcher'):
            self.watcher.update_watches(scanned_dirs)
        if not is_append:
            self.list_wallpapers.clear()
        existing_ids = set()
        for i in range(self.list_wallpapers.count()):
            data = self.list_wallpapers.item(i).data(Qt.ItemDataRole.UserRole)
            if data: existing_ids.add(data["id"])
        new_count = 0
        self.sort_wallpapers(wallpapers)
        for w in wallpapers:
            if w["id"] in existing_ids: continue
            item = QListWidgetItem(w["title"])
            item.setSizeHint(QSize(180, 200))
            item_font = QFont()
            item_font.setPointSize(10)
            item_font.setWeight(600)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignCenter)
            item.setFont(item_font)
            item.setData(Qt.ItemDataRole.UserRole, w)
            if w.get("preview"):
                path = os.path.join(w["path"], w["preview"])
                if os.path.isfile(path):
                    pixmap = QPixmap(path)
                    icon_pixmap = pixmap.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    rect = QRect(0, 0, 160, 160)
                    rect.moveCenter(icon_pixmap.rect().center())
                    icon_pixmap = icon_pixmap.copy(rect)
                    item.setIcon(QIcon(icon_pixmap))
            self.list_wallpapers.addItem(item)
            existing_ids.add(w["id"])
            new_count += 1
        self.btn_scan.setEnabled(True)
        if is_append:
            self.status_bar.showMessage(self._("added_wallpapers", count=new_count))
        else:
            self.status_bar.showMessage(self._("found_wallpapers", count=self.list_wallpapers.count()))

    def on_wallpaper_selected(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        self.wp_id_input.setText(data["id"])
        self._update_preview(data)

    def _update_preview(self, data):
        self.preview_title.setText(data.get("title", "Untitled"))
        # Load preview image
        if data.get("preview"):
            path = os.path.join(data["path"], data["preview"])
            if os.path.isfile(path):
                pm = QPixmap(path).scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_image.setPixmap(pm)
                self.preview_image.setText("")
        # Meta info
        proj_path = os.path.join(data["path"], "project.json")
        wp_type = ""
        wp_tags = []
        if os.path.isfile(proj_path):
            try:
                with open(proj_path, 'r', encoding='utf-8') as f:
                    proj = json.load(f)
                wp_type = proj.get("type", "")
                wp_tags = proj.get("tags", [])
            except: pass
        try:
            total = sum(f.stat().st_size for f in pathlib.Path(data["path"]).rglob("*") if f.is_file())
            size_str = f"{total / 1048576:.1f} MB"
        except:
            size_str = "? MB"
        self.preview_meta.setText(f"{wp_type}   {size_str}")
        # Tags
        while self.preview_tags_layout.count():
            child = self.preview_tags_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for tag in wp_tags[:6]:
            lbl = QLabel(tag)
            lbl.setObjectName("PreviewTag")
            self.preview_tags_layout.addWidget(lbl)

    def filter_wallpapers(self, text):
        query = text.lower()
        if hasattr(self, 'watcher'):
            if query:
                self.watcher.timer.stop()
            else:
                self.watcher.timer.start()
        for i in range(self.list_wallpapers.count()):
            item = self.list_wallpapers.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            title = item.text().lower()
            wp_id = str(data.get("id", "")).lower()
            item.setHidden(query not in title and query not in wp_id)

    def on_sort_change(self):
        try:
            self.config["sorting_type"] = self.sorting_type.currentIndex()
            self.save_config()
            if self.list_wallpapers:
                self.watcher.library_changed.emit()
        except: pass

    def sort_wallpapers(self, wallpapers):
        try:
            idx = self.sorting_type.currentIndex()
            if idx == 0:  # Name
                wallpapers.sort(key=lambda x: x["title"].lower(), reverse=self.sort_reversed_state)
            elif idx == 1:  # Subscription Date
                wallpapers.sort(key=lambda x: pathlib.Path(x["path"]).stat().st_ctime, reverse=not self.sort_reversed_state)
        except: pass

    def reverse_sorted(self):
        self.sort_reversed_state = not self.sort_reversed_state
        self.btn_reverse_sorted.setText("↓" if self.sort_reversed_state else "↑")
        self.config["reversed"] = self.sort_reversed_state
        self.save_config()
        self.watcher.library_changed.emit()

    # ── Properties ──────────────────────────────────────────────────────

    def on_property_selected(self):
        data = self.properties_combo.currentData()
        if not isinstance(data, dict):
            self.properties_type.setText("")
            self.properties_value.blockSignals(True)
            self.properties_value.clear()
            self.properties_value.blockSignals(False)
            return
        name = data.get("name", "")
        stored = self.properties_data.get(name, data)
        self.properties_type.setText(stored.get("type", ""))
        self.properties_value.blockSignals(True)
        self.properties_value.setText(stored.get("value", ""))
        self.properties_value.blockSignals(False)

    def apply_property_value(self):
        data = self.properties_combo.currentData()
        if not isinstance(data, dict): return
        value = self.properties_value.text().strip()
        data["value"] = value
        name = data.get("name", "")
        if name: self.properties_data[name] = data
        idx = self.properties_combo.currentIndex()
        self.properties_combo.setItemData(idx, data)
        self.run_wallpaper()

    def populate_properties_combo(self, props_dict):
        self.properties_combo.blockSignals(True)
        self.properties_combo.clear()
        self.properties_combo.addItem(self._("select_property"), None)
        self.properties_data = {}
        for name, data in props_dict.items():
            item = {"name": name, "value": data.get("value", ""), "sep": data.get("sep", "="), "type": data.get("type", "")}
            self.properties_data[name] = item
            self.properties_combo.addItem(name, item)
        self.properties_combo.setCurrentIndex(0)
        self.properties_combo.blockSignals(False)
        self.on_property_selected()

    def normalize_property_value(self, value):
        if "," in value:
            value = re.sub(r"\s*,\s*", ",", value)
        return value

    def parse_properties_output(self, output):
        props = []
        text = output.strip()
        if text:
            try: parsed = json.loads(text)
            except: parsed = None
            if parsed is None:
                start, end = text.find("{"), text.rfind("}")
                if start != -1 and end > start:
                    try: parsed = json.loads(text[start:end+1])
                    except: parsed = None
            if isinstance(parsed, dict):
                for name, value in parsed.items():
                    props.append((str(name), str(value), "=", ""))
                return props
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("property") or item.get("key")
                        if name is None: continue
                        props.append((str(name), str(item.get("value", "")), "=", ""))
                    elif isinstance(item, str):
                        props.append((item, "", "=", ""))
                if props: return props
        lines = output.splitlines()
        current_name = None
        current_type = ""
        for line in lines:
            stripped = line.strip()
            if not stripped: continue
            if stripped.startswith("_") or " - " in stripped:
                parts = stripped.split(" - ", 1)
                if parts:
                    current_name = parts[0].strip()
                    current_type = parts[1].strip() if len(parts) > 1 else ""
                continue
            if stripped.startswith("Value:"):
                if current_name:
                    value = stripped.split("Value:", 1)[1].strip()
                    props.append((current_name, value, "=", current_type))
                    current_name = None
                    current_type = ""
                continue
        if props: return props
        for line in lines:
            line = line.strip()
            if not line: continue
            lower = line.lower()
            if lower.startswith("properties") or line.startswith("#"): continue
            if lower.startswith("running with") or lower.startswith("particle "): continue
            if lower.startswith("found user setting with script value"): continue
            if "=" in line:
                name, value = line.split("=", 1)
                sep = "="
            elif ":" in line:
                name, value = line.split(":", 1)
                sep = ":"
            else:
                parts = line.split(None, 1)
                name = parts[0]
                value = parts[1] if len(parts) > 1 else ""
                sep = "="
            name, value = name.strip(), value.strip()
            if name: props.append((name, value, sep, ""))
        return props

    def list_properties_logic(self, wallpaper_id):
        cmd = ["linux-wallpaperengine", "-l", wallpaper_id]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.terminate()
            stdout, stderr = proc.communicate(timeout=2)
        returncode = proc.returncode if proc.returncode is not None else 0
        combined = (stdout or "")
        if stderr: combined = (combined + "\n" + stderr).strip()
        return returncode, combined, stderr or "", timed_out, wallpaper_id

    def load_properties(self):
        wid = self.wp_id_input.text().strip()
        if not wid:
            self.status_bar.showMessage(self._("no_wallpaper_selected_status"))
            return
        if not shutil.which("linux-wallpaperengine"):
            self.status_bar.showMessage(self._("engine_not_found"))
            return
        self.status_bar.showMessage(self._("loading_properties_status"))
        self.btn_load_props.setEnabled(False)
        self._props_task = AsyncTask(self.list_properties_logic, wid, callback=self.load_properties_finished)

    def load_properties_finished(self, result):
        if isinstance(result, Exception):
            self.btn_load_props.setEnabled(True)
            self.status_bar.showMessage(self._("properties_error", error=result))
            return
        returncode, stdout, stderr, timed_out, wallpaper_id = result
        self.btn_load_props.setEnabled(True)
        if returncode != 0 and not timed_out:
            self.status_bar.showMessage(self._("properties_failed", error=stderr.strip() or 'Unknown error'))
            return
        props = self.parse_properties_output(stdout)
        stored = self.config.get("properties_by_wallpaper", {}).get(wallpaper_id, {})
        merged = {}
        for name, value, sep, prop_type in props:
            data = {"name": name, "value": value, "sep": sep, "type": prop_type}
            if name in stored: data["value"] = stored[name].get("value", value)
            merged[name] = data
        self.populate_properties_combo(merged)
        count = len(props)
        if timed_out:
            self.status_bar.showMessage(self._("loaded_properties_timeout", count=count))
        else:
            self.status_bar.showMessage(self._("loaded_properties", count=count))

    def on_wallpaper_id_changed(self):
        wid = self.wp_id_input.text().strip()
        stored = self.config.get("properties_by_wallpaper", {}).get(wid, {})
        self.populate_properties_combo(stored)

    # ── Wallpaper Execution ─────────────────────────────────────────────

    def kill_external_wallpapers(self):
        self.wallpaper_proc_manager.kill_external("linux-wallpaperengine")

    def _resolve_wallpaper_path(self, wallpaper_id: str) -> tuple[str, bool]:
        """Resolve wallpaper ID to a launchable path, handling dependencies.

        Returns (path_to_use, was_resolved). If a dependency is missing and
        the user declines to download, returns (wallpaper_id, False).
        """
        # Find the wallpaper's full path
        workshop_dirs = self.get_steam_workshop_dirs()
        wallpaper_path = find_workshop_item(wallpaper_id, workshop_dirs)
        if not wallpaper_path:
            return wallpaper_id, False  # Let the engine try to resolve it

        resolved_path, missing_dep = resolve_wallpaper(wallpaper_path, workshop_dirs)
        if missing_dep:
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, self._("dependency_required_title"),
                self._("dependency_required_msg", dep_id=missing_dep),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.steam_cmd.is_logged_in:
                    dest = list(workshop_dirs)[0] if workshop_dirs else os.path.expanduser(
                        "~/.local/share/Steam/steamapps/workshop/content/431960")
                    os.makedirs(dest, exist_ok=True)
                    self.steam_cmd.download_workshop_item(missing_dep, dest)
                    self.status_bar.showMessage(
                        self._("downloading_dependency", dep_id=missing_dep))
                else:
                    QMessageBox.information(
                        self, self._("steam_login_needed_title"),
                        self._("steam_login_needed_msg"))
                return wallpaper_id, False
            return wallpaper_id, False

        if resolved_path != wallpaper_path:
            logging.info("Resolved dependency wallpaper %s -> %s", wallpaper_id, resolved_path)
            return resolved_path, True
        return wallpaper_id, False

    def run_wallpaper(self):
        if not shutil.which("linux-wallpaperengine"):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, self._("error_title"), self._("engine_not_found_dialog"))
            self.status_bar.showMessage(self._("engine_not_found"))
            return
        cmd = ['linux-wallpaperengine']
        screen_name = self.screen_combo.currentText()
        if self.chk_windowed_mode.isChecked():
            geom = "0x0x1920x1080"
            found = next((s for s in self.screens if s["name"] == screen_name), None)
            if found: geom = f"{found['x']}x{found['y']}x{found['w']}x{found['h']}"
            cmd.extend(['--window', geom])
        else:
            cmd.extend(['--screen-root', screen_name])
        bg_id = self.wp_id_input.text()
        resolved_path, _ = self._resolve_wallpaper_path(bg_id)
        cmd.extend(['--bg', resolved_path])
        if self.chk_silent.isChecked(): cmd.append('--silent')
        elif self.slider_volume.value() != 15: cmd.extend(['--volume', str(self.slider_volume.value())])
        if self.chk_no_automute.isChecked(): cmd.append('--noautomute')
        if self.chk_no_proc.isChecked(): cmd.append('--no-audio-processing')
        if self.slider_fps.value() != 30: cmd.extend(['--fps', str(self.slider_fps.value())])
        if self.chk_mouse.isChecked(): cmd.append('--disable-mouse')
        if self.chk_parallax.isChecked(): cmd.append('--disable-parallax')
        if self.chk_fs_pause.isChecked(): cmd.append('--no-fullscreen-pause')
        scale = self.combo_scaling.currentText()
        self.config["scale"] = scale
        if scale != 'default': cmd.extend(['--scaling', scale])
        clamp = self.combo_clamp.currentText()
        self.config["clamp"] = clamp
        if clamp != 'clamp': cmd.extend(['--clamp', clamp])
        if hasattr(self, "properties_data"):
            for name, data in self.properties_data.items():
                value = self.normalize_property_value(str(data.get("value", "")))
                sep = data.get("sep", "=")
                cmd.extend(['--set-property', f"{name}{sep}{value}"])
        custom_args = self.input_custom_args.text()
        if custom_args:
            for arg in custom_args.split(): cmd.append(arg)
        self.stop_wallpapers()
        try:
            self.wallpaper_proc_manager.start(cmd)
            self.status_bar.showMessage(self._("wallpaper_started"))
            self.save_config()
        except Exception as e:
            logging.error("Couldn't run: %s", e)
            self.status_bar.showMessage(f"Error: {e}")

    def show_log_file(self):
        log_path = self.wallpaper_proc_manager.log_path()
        if not log_path.exists():
            self.status_bar.showMessage(self._("log_not_found"))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))

    def stop_wallpapers(self):
        stopped = False
        if self.wallpaper_proc_manager.is_running():
            try: stopped = self.wallpaper_proc_manager.stop(timeout=1)
            except Exception as e: logging.error("Stop error: %s", e)
        if not stopped:
            self.kill_external_wallpapers()
        self.status_bar.showMessage(self._("wallpapers_stopped"))

    def check_wallpaper_process(self):
        result = self.wallpaper_proc_manager.check()
        if result is None or result["expected"]: return
        rc = result["returncode"]
        msg = self._("wallpaper_exited") if rc == 0 else self._("wallpaper_crashed", code=rc)
        if result["log_path"]: msg += f" Log: {result['log_path']}"
        self.status_bar.showMessage(msg)
        if hasattr(self, "tray") and self.tray.isVisible():
            self.tray.showMessage(self._("wallpaper_engine"), msg)

    def restore_last_wallpaper(self):
        c = self.config.get("last_wallpaper", {})
        if not c: return
        self.wp_id_input.setText(c.get("background_id", ""))
        self.screen_combo.setCurrentText(c.get("screen", ""))
        self.chk_silent.setChecked(c.get("silent", False))
        self.slider_volume.setValue(c.get("volume", 15))
        self.chk_no_automute.setChecked(c.get("noautomute", False))
        self.chk_no_proc.setChecked(c.get("no-audio-processing", False))
        self.slider_fps.setValue(c.get("fps", 30))
        self.chk_mouse.setChecked(c.get("disable-mouse", False))
        self.chk_parallax.setChecked(c.get("disable-parallax", False))
        self.chk_fs_pause.setChecked(c.get("no-fullscreen-pause", False))
        self.input_custom_args.setText(c.get("custom_args", ""))
        self.chk_windowed_mode.setChecked(c.get("windowed_mode", False))
        self.run_wallpaper()
        sort_idx = self.config.get("sorting_type", 0)
        if isinstance(sort_idx, str):
            sort_idx = 0  # legacy config compat
        self.sorting_type.setCurrentIndex(sort_idx)
        self.sort_reversed_state = self.config.get("reversed", False)
        self.btn_reverse_sorted.setText("↓" if self.sort_reversed_state else "↑")
        self.watcher.library_changed.emit()

    # ── Config / Misc ───────────────────────────────────────────────────

    def detect_screens(self):
        screens = []
        try:
            res = subprocess.run(['xrandr', '--query'], capture_output=True, text=True)
            pattern = re.compile(r'^(\S+)\s+connected\s+(?:primary\s+)?(\d+)x(\d+)\+(\d+)\+(\d+)')
            for line in res.stdout.splitlines():
                match = pattern.match(line)
                if match:
                    name, w, h, x, y = match.groups()
                    screens.append({"name": name, "w": w, "h": h, "x": x, "y": y})
        except Exception as e:
            logging.error(f"Screen detection: {e}")
        if not screens:
            screens = [{"name": "eDP-1", "w": "1920", "h": "1080", "x": "0", "y": "0"}]
        return screens

    def load_config_data(self):
        self.config = {}
        try: CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        except: pass
        old_config_path = pathlib.Path(__file__).parent / "wpe_gui_config.json"
        if old_config_path.exists() and not CONFIG_FILE.exists():
            try: shutil.move(str(old_config_path), str(CONFIG_FILE))
            except: pass
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: self.config = json.load(f)
            except: pass
        if "properties_by_wallpaper" not in self.config:
            self.config["properties_by_wallpaper"] = {}

    def save_config(self):
        self.config["last_wallpaper"] = {
            "background_id": self.wp_id_input.text(),
            "screen": self.screen_combo.currentText(),
            "silent": self.chk_silent.isChecked(),
            "volume": self.slider_volume.value(),
            "noautomute": self.chk_no_automute.isChecked(),
            "no-audio-processing": self.chk_no_proc.isChecked(),
            "fps": self.slider_fps.value(),
            "disable-mouse": self.chk_mouse.isChecked(),
            "disable-parallax": self.chk_parallax.isChecked(),
            "no-fullscreen-pause": self.chk_fs_pause.isChecked(),
            "custom_args": self.input_custom_args.text(),
            "windowed_mode": self.chk_windowed_mode.isChecked(),
        }
        wid = self.wp_id_input.text().strip()
        if wid:
            props_out = {}
            for name, data in self.properties_data.items():
                props_out[name] = {"value": str(data.get("value", "")), "sep": data.get("sep", "="), "type": data.get("type", "")}
            self.config.setdefault("properties_by_wallpaper", {})[wid] = props_out
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)
        except Exception as e:
            logging.error("Save config error: %s", e)

    def update_texts(self):
        self.combo_lang.blockSignals(True)
        self.combo_lang.clear()
        for code, name in self.i18n.available_languages.items():
            self.combo_lang.addItem(name, code)
        self.combo_lang.setCurrentText(self.i18n.available_languages.get(self.i18n.current_code, "English"))
        self.combo_lang.blockSignals(False)

    def change_lang(self, text):
        code = self.combo_lang.currentData()
        if code and self.i18n.load(code):
            self.config["current_language"] = code
            self.save_config()
            self._rebuild_ui()

    def _rebuild_ui(self):
        """Rebuild the entire UI to apply language changes."""
        # Save current state
        cur_tab = self.content_stack.currentIndex()
        cur_wp = self.wp_id_input.text() if hasattr(self, 'wp_id_input') else ""
        cur_screen = self.screen_combo.currentText() if hasattr(self, 'screen_combo') else ""
        # Remove old central widget
        old = self.centralWidget()
        if old:
            old.deleteLater()
        self._api_key_inputs = []
        # Rebuild
        self.setup_ui()
        self.setStyleSheet(STYLESHEET)
        # Restore screens
        self.screens = self.detect_screens()
        for s in self.screens:
            self.screen_combo.addItem(s["name"], s)
        if cur_screen:
            self.screen_combo.setCurrentText(cur_screen)
        # Restore state
        self.wp_id_input.setText(cur_wp)
        self._switch_tab(cur_tab)
        self.update_texts()
        # Re-populate tray
        self.setup_tray()
        # Re-scan
        self.start_scan()

    # ── Tray ────────────────────────────────────────────────────────────

    def setup_tray(self):
        self.tray = QSystemTrayIcon(QApplication.instance())
        img = QImage(64, 64, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        from PyQt6.QtGui import QBrush
        painter.setBrush(QBrush(QColor("#0A84FF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 64, 64)
        painter.end()
        self.tray.setIcon(QIcon(QPixmap.fromImage(img)))
        self.tray_menu = QMenu()
        a_show = QAction(self._("show_window"), self)
        a_show.triggered.connect(self.show)
        a_workshop = QAction(self._("browse_workshop"), self)
        a_workshop.triggered.connect(lambda: (self.show(), self._switch_tab(1)))
        a_exit = QAction(self._("quit"), self)
        a_exit.triggered.connect(self.quit_app)
        self.tray_menu.addAction(a_show)
        self.tray_menu.addAction(a_workshop)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(a_exit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-flow workshop grid when width changes
        if (hasattr(self, 'content_stack') and self.content_stack.currentIndex() == 1
                and self.workshop_items):
            self._render_ws_grid()

    def closeEvent(self, event):
        if self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self.quit_app()

    def quit_app(self):
        self.stop_wallpapers()
        if hasattr(self, 'watcher'):
            self.watcher.stop()
        self.kill_external_wallpapers()
        QApplication.quit()


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s] [%(levelname)s]:  %(message)s')
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    window = WallpaperApp()
    parser = argparse.ArgumentParser(description="Open Wallpaper Engine for Linux")
    parser.add_argument("--background", action="store_true", help="Start minimized to tray")
    args = parser.parse_args()
    if not args.background:
        window.show()
    sys.exit(app.exec())
