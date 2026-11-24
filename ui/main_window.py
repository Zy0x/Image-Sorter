"""Primary Studio Slate application window (`ImageSorterApp`) coordinating media views, sorting, and workflows."""

from collections import deque
import copy
import json
import os
import shutil
import time

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QKeySequence, QMovie, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import (
    ALL_SLOT_LETTERS,
    APP_NAME,
    APP_VERSION,
    DEFAULT_CUSTOM_THEME,
    DEFAULT_FOLDER_NAMES,
    DEFAULT_FOLDER_PATHS,
    MAX_FOLDER_SLOTS,
    RAPID_MOVE_DEFAULT_MS,
    append_event_log,
    clamp_folder_slots,
    clamp_rapid_interval,
    debug_log,
    default_settings_copy,
    format_log_entry,
    load_settings,
    normalize_settings,
    read_recent_event_log,
    resource_path,
    save_settings,
)
from core.file_ops import (
    format_auto_rename_filename,
    generate_session_summary,
    get_unique_destination,
    norm_path_key,
    reveal_in_file_explorer,
    scan_image_files,
    send_to_recycle_bin,
)
from core.history import HistoryStore, save_history
from core.hot_reload import HotReloadWatcher
from core.media_queue import MediaQueueModel
from core.workers import DuplicateScanThread, FolderScanThread, UpdateCheckThread
from media.cache import PixmapLRUCache
from media.decoders import (
    load_animation_frames,
    load_pixmap,
    read_image_metadata,
    read_video_metadata,
)
from media.duplicates import find_duplicate_groups
from media.formats import (
    SUPPORTED_IMAGE_EXTENSIONS,
    fit_pixmap_to_box,
    format_duration,
    format_file_size,
    is_video_file,
    resize_next_preview,
)
from media.video_controller import VideoDecodeThread, VideoMediaController
from ui.dialogs import (
    AboutDialog,
    AutoRenameSettingsDialog,
    CustomThemeDialog,
    FolderSettingsDialog,
    ImagePreviewDialog,
    JumpToMediaDialog,
    RapidMoveSettingsDialog,
    SessionSummaryDialog,
    ShortcutsGuideDialog,
    UpdateDialog,
    show_studio_message,
)
from ui.theme import (
    SLOT_ACCENTS,
    apply_studio_palette,
    build_empty_state_html,
    build_studio_dialog_qss,
    darken_color,
    hex_rgba,
    make_vector_icon,
    resolve_studio_tokens,
    slot_text_color,
)
from ui.widgets import (
    FilmstripBar,
    LoadingOverlay,
    MediaHudOverlay,
    StageViewport,
    StudioComboBox,
    ToastNotification,
)

_ANIM_IMAGE_EXTS = (".gif", ".webp", ".apng", ".avif")


class ImageSorterApp(QMainWindow):
    """Main desktop media curation window with Studio Slate design system and zero-lock playback."""

    def __init__(self, initial_folder: str = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1120, 740)
        self.setAcceptDrops(True)

        icon_path = resource_path("assets/icons/app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Persistent core stores & models
        self.settings = load_settings()
        self.history_store = HistoryStore()
        self.media_queue = MediaQueueModel(self.history_store)
        self.pixmap_cache = PixmapLRUCache(max_entries=48)
        self.log_entries = deque(read_recent_event_log(500), maxlen=500)

        # Config-backed state
        self.theme_mode = self.settings.get("theme_mode", "system")
        self.custom_theme = copy.deepcopy(DEFAULT_CUSTOM_THEME)
        self.custom_theme.update(self.settings.get("custom_theme", {}))
        self.folder_slot_count = clamp_folder_slots(self.settings.get("folder_slot_count", 5))
        self.folder_names = list(self.settings.get("folder_names", DEFAULT_FOLDER_NAMES))
        self.folder_paths = list(self.settings.get("folder_paths", DEFAULT_FOLDER_PATHS))
        while len(self.folder_names) < MAX_FOLDER_SLOTS:
            self.folder_names.append(DEFAULT_FOLDER_NAMES[len(self.folder_names)])
        while len(self.folder_paths) < MAX_FOLDER_SLOTS:
            self.folder_paths.append(DEFAULT_FOLDER_PATHS[len(self.folder_paths)])

        self.recent_folders = list(self.settings.get("recent_folders", []))
        self.last_opened_folder = self.settings.get("last_opened_folder", "") or (
            self.recent_folders[0] if self.recent_folders else ""
        )
        self.hide_moved = bool(self.settings.get("hide_moved", False))
        self.include_subfolders = bool(self.settings.get("include_subfolders", False))
        self.rapid_move_interval_ms = clamp_rapid_interval(
            self.settings.get("rapid_move_interval", self.settings.get("rapid_move_interval_ms", RAPID_MOVE_DEFAULT_MS))
        )
        self.video_muted = bool(self.settings.get("video_muted", False))
        self.video_volume = float(self.settings.get("video_volume", 0.85))
        self.sort_by = str(self.settings.get("sort_by", "name"))
        self.sort_order = str(self.settings.get("sort_order", "asc"))
        self.filmstrip_bar = None
        self.flag_btn = None
        self.main_image_label = None
        self.main_stage_viewport = None
        self.main_card = None
        self.sort_actions = {}
        self.media_queue.load_flagged(self.settings.get("flagged_files", []))
        self.current_folder = None
        self.current_meta_cache = {}
        self.folder_buttons = []

        # Active media playback state
        self.current_movie = None
        self._movie_bytes = None
        self._movie_buffer = None
        self._anim_frames = []
        self._anim_index = 0
        self._main_paused = False
        self._main_seeking = False
        self._active_media_path = None
        self._active_main_pixmap = QPixmap()
        self._active_next_pixmap = QPixmap()
        self._menu_icon_specs = []
        self._hud_update_in_progress = False
        self._pending_scan_thread = None
        self._pending_dup_thread = None
        self._pending_update_thread = None
        self._video_decode_thread = None

        self.hud_overlay = None
        self.video_controller = VideoMediaController(self)
        self.video_controller.frame_image_ready.connect(self._on_main_qtmm_frame)
        self.video_controller.position_changed.connect(self._on_main_qtmm_position)
        self.video_controller.duration_changed.connect(self._on_main_qtmm_duration)
        self.video_controller.session_error.connect(self._on_main_qtmm_error)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._advance_main_anim_frame)

        self._deferred_anim_timer = QTimer(self)
        self._deferred_anim_timer.setSingleShot(True)
        self._deferred_anim_timer.timeout.connect(self._start_deferred_video_anim)

        self._history_flush_timer = QTimer(self)
        self._history_flush_timer.setSingleShot(True)
        self._history_flush_timer.setInterval(800)
        self._history_flush_timer.timeout.connect(self.history_store.flush)

        self._rapid_move_timer = QTimer(self)
        self._rapid_move_timer.timeout.connect(self._on_rapid_move_tick)
        self._rapid_move_delay_timer = QTimer(self)
        self._rapid_move_delay_timer.setSingleShot(True)
        self._rapid_move_delay_timer.timeout.connect(self._begin_rapid_loop)
        self._active_rapid_slot = None
        self._rapid_moved_in_hold = False

        self.loading_overlay = LoadingOverlay(self)
        self._init_ui()
        self.toast = ToastNotification(self.centralWidget())
        self.apply_theme()
        self._sync_minimum_window_size()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Recursive hot-reload watcher across core/media/ui/utils/main.py
        self.hot_reload = HotReloadWatcher(
            self,
            can_reload=lambda: QApplication.activeModalWidget() is None,
            on_external_settings=self._reload_external_settings,
            on_trigger_reload=self._perform_hot_reload,
        )

        # Resume hot-reload session or handle first run / initial CLI folder
        restored = HotReloadWatcher.pop_recent_state()
        if restored and restored.get("current_folder") and os.path.isdir(restored["current_folder"]):
            QTimer.singleShot(50, lambda: self._restore_hot_reload_session(restored))
        elif initial_folder and os.path.isdir(initial_folder):
            QTimer.singleShot(50, lambda: self.import_folder(initial_folder))
        elif self.settings.get("first_run", True):
            self.settings["first_run"] = False
            self._sync_and_save_settings()

    def _sync_and_save_settings(self) -> dict:
        """Synchronize all live in-memory configuration fields into self.settings and persist atomically."""
        latest = load_settings()
        latest.update(self.settings)
        latest["first_run"] = False
        latest["theme_mode"] = self.theme_mode
        latest["custom_theme"] = copy.deepcopy(self.custom_theme)
        latest["folder_slot_count"] = clamp_folder_slots(self.folder_slot_count)
        latest["folder_names"] = list(self.folder_names[:MAX_FOLDER_SLOTS])
        latest["folder_paths"] = list(self.folder_paths[:MAX_FOLDER_SLOTS])
        latest["recent_folders"] = list(self.recent_folders[:10])
        latest["last_opened_folder"] = (
            self.current_folder
            or getattr(self, "last_opened_folder", "")
            or (self.recent_folders[0] if self.recent_folders else "")
        )
        latest["hide_moved"] = bool(self.hide_moved)
        latest["include_subfolders"] = bool(self.include_subfolders)
        latest["rapid_move_interval"] = clamp_rapid_interval(self.rapid_move_interval_ms)
        latest["video_muted"] = bool(self.video_muted)
        latest["video_volume"] = float(self.video_volume)
        latest["sort_by"] = getattr(self, "sort_by", self.settings.get("sort_by", "name"))
        latest["sort_order"] = getattr(self, "sort_order", self.settings.get("sort_order", "asc"))
        latest["show_filmstrip"] = bool(self.settings.get("show_filmstrip", True))
        latest["auto_rename_enabled"] = bool(self.settings.get("auto_rename_enabled", False))
        latest["auto_rename_pattern"] = str(self.settings.get("auto_rename_pattern", "{folder}_{index:04d}"))
        latest["flagged_files"] = list(self.media_queue.get_flagged_list() if hasattr(self, "media_queue") else self.settings.get("flagged_files", []))
        self.settings = normalize_settings(latest, first_run_default=False)
        self.recent_folders = list(self.settings["recent_folders"])
        self.last_opened_folder = self.settings["last_opened_folder"]
        save_settings(self.settings)
        return self.settings

    # ------------------------------------------------------------------
    # Backwards-compatible properties & accessors for external tests
    # ------------------------------------------------------------------
    @property
    def queue_model(self):
        return self.media_queue

    @property
    def history(self):
        return self.history_store.records

    @history.setter
    def history(self, value):
        self.history_store.records = list(value or [])
        self.history_store.validate()

    @property
    def history_cache(self):
        return self.history_store.cache

    @property
    def image_files(self):
        return self.media_queue.all_files

    @image_files.setter
    def image_files(self, value):
        self.media_queue.all_files = list(value or [])

    @property
    def filtered_files(self):
        return self.media_queue.filtered_files

    @filtered_files.setter
    def filtered_files(self, value):
        self.media_queue.filtered_files = list(value or [])

    @property
    def current_index(self):
        return self.media_queue.current_index

    @current_index.setter
    def current_index(self, value):
        self.media_queue.current_index = int(value)

    @property
    def duplicate_norms(self):
        return self.media_queue.duplicate_norms

    @property
    def duplicate_groups(self):
        return self.media_queue.duplicate_groups

    @property
    def duplicate_group_lookup(self):
        return self.media_queue.duplicate_group_lookup

    @property
    def image_label(self):
        return self.main_image_label

    @property
    def _main_anim_frames(self):
        return self._anim_frames

    @property
    def _main_audio_player(self):
        return self.video_controller.player

    @property
    def _main_audio_output(self):
        return self.video_controller.output

    @property
    def _main_video_sink(self):
        return self.video_controller.sink

    @property
    def _main_video_using_qtmm(self):
        return bool(self.video_controller.active)

    @property
    def _play_pause_btn(self):
        return self.hud_overlay.play_pause_btn if self.hud_overlay is not None else None

    @property
    def _mute_btn(self):
        return self.hud_overlay.mute_btn if self.hud_overlay is not None else None

    @property
    def _video_seek_slider(self):
        return self.hud_overlay.seek_slider if self.hud_overlay is not None else None

    # ------------------------------------------------------------------
    # UI Construction & Menu Setup
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        self._build_menus()
        self._bind_shortcuts()

        central = QWidget()
        central.setObjectName("centralHost")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 14)
        root.setSpacing(10)

        # 1. Info bar: Moved status pill | File metadata | Queue counter pill
        info_bar = QFrame()
        info_bar.setObjectName("infoBar")
        info_lay = QHBoxLayout(info_bar)
        info_lay.setContentsMargins(12, 7, 12, 7)
        info_lay.setSpacing(10)

        self.moved_badge = QLabel("No media loaded")
        self.moved_badge.setObjectName("statusBadge")
        info_lay.addWidget(self.moved_badge)

        self.flag_btn = QPushButton("Flag")
        self.flag_btn.setObjectName("flagBtn")
        self.flag_btn.setCursor(Qt.PointingHandCursor)
        self.flag_btn.setFocusPolicy(Qt.NoFocus)
        self.flag_btn.setToolTip("Toggle Bookmark/Flag (* or Alt+F)")
        self.flag_btn.clicked.connect(self.toggle_flag_current)
        info_lay.addWidget(self.flag_btn)

        self.file_info_label = QLabel("")
        self.file_info_label.setObjectName("fileInfoLabel")
        self.file_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        info_lay.addWidget(self.file_info_label, stretch=1)

        self.counter_label = QLabel("0 / 0")
        self.counter_label.setObjectName("counterBadge")
        info_lay.addWidget(self.counter_label)
        root.addWidget(info_bar)

        # 2. Central split stage: Active media card (~74%) + Up Next queue panel (~26%)
        stage_row = QHBoxLayout()
        stage_row.setSpacing(14)

        self.main_card = QFrame()
        self.main_card.setObjectName("mainStageCard")
        main_card_lay = QVBoxLayout(self.main_card)
        main_card_lay.setContentsMargins(10, 10, 10, 10)

        self.main_image_label = QLabel()
        self.main_image_label.setObjectName("mainMediaSurface")
        self.main_image_label.setAlignment(Qt.AlignCenter)
        self.main_image_label.setCursor(Qt.PointingHandCursor)
        self.main_image_label.installEventFilter(self)

        self.main_stage_viewport = StageViewport(self.main_image_label, min_w=320, min_h=220)
        self.main_stage_viewport.resized.connect(self._relayout_stage_previews)
        self.main_stage_viewport.installEventFilter(self)
        self.main_card.installEventFilter(self)
        main_card_lay.addWidget(self.main_stage_viewport, stretch=1)
        stage_row.addWidget(self.main_card, stretch=74)

        # Up Next side panel
        self.next_panel = QFrame()
        self.next_panel.setObjectName("nextStageCard")
        next_lay = QVBoxLayout(self.next_panel)
        next_lay.setContentsMargins(10, 10, 10, 10)
        next_lay.setSpacing(8)

        self.next_header_lbl = QLabel("UP NEXT")
        self.next_header_lbl.setAlignment(Qt.AlignCenter)
        self.next_header_lbl.setObjectName("upNextHeader")
        next_lay.addWidget(self.next_header_lbl)

        self.next_image_label = QLabel("No upcoming\nmedia")
        self.next_image_label.setObjectName("nextMediaSurface")
        self.next_image_label.setAlignment(Qt.AlignCenter)
        self.next_image_label.setWordWrap(True)

        self.next_stage_viewport = StageViewport(self.next_image_label, min_w=130, min_h=160)
        self.next_stage_viewport.resized.connect(self._relayout_stage_previews)
        next_lay.addWidget(self.next_stage_viewport, stretch=1)

        # Filmstrip preview dock placed cleanly inside UP NEXT card beneath preview
        self.filmstrip_bar = FilmstripBar(parent=self)
        self.filmstrip_bar.item_selected.connect(self.jump_to_index)
        self.filmstrip_bar.setVisible(self.settings.get("show_filmstrip", True))
        next_lay.addWidget(self.filmstrip_bar)

        stage_row.addWidget(self.next_panel, stretch=26)
        root.addLayout(stage_row, stretch=1)

        # 3. Previous / Next navigation strip
        nav_row = QHBoxLayout()
        nav_row.setSpacing(10)

        self.prev_button = QPushButton("Previous")
        self.prev_button.setObjectName("navButton")
        self.prev_button.setCursor(Qt.PointingHandCursor)
        self.prev_button.setFocusPolicy(Qt.NoFocus)
        self.prev_button.clicked.connect(self.show_previous)
        nav_row.addWidget(self.prev_button, stretch=1)

        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("navButton")
        self.next_button.setCursor(Qt.PointingHandCursor)
        self.next_button.setFocusPolicy(Qt.NoFocus)
        self.next_button.clicked.connect(self.show_next)
        nav_row.addWidget(self.next_button, stretch=1)
        root.addLayout(nav_row)

        # 4. Dynamic 3..9 destination folder buttons
        self.folder_row_layout = QHBoxLayout()
        self.folder_row_layout.setSpacing(8)
        for i in range(MAX_FOLDER_SLOTS):
            btn = QPushButton()
            btn.setObjectName("folderSlotBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumHeight(44)
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, idx=i: self._show_folder_btn_context_menu(idx, pos))
            btn.pressed.connect(lambda idx=i: self._on_folder_btn_pressed(idx))
            btn.released.connect(self._on_folder_btn_released)
            self.folder_buttons.append(btn)
            self.folder_row_layout.addWidget(btn, stretch=1)
        root.addLayout(self.folder_row_layout)

        # 5. Bottom action strip: Filter combo | Undo | Skip
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.filter_combo = StudioComboBox()
        self.filter_combo.setObjectName("filterCombo")
        self.filter_combo.setCursor(Qt.PointingHandCursor)
        self.filter_combo.setFocusPolicy(Qt.NoFocus)
        self.filter_combo.setMaxVisibleItems(10)
        self.filter_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.filter_combo.setMinimumWidth(152)
        self.filter_combo.setMinimumHeight(38)
        self._populate_filter_combo()
        self.filter_combo.currentTextChanged.connect(lambda _txt: self.apply_filter())
        bottom_row.addWidget(self.filter_combo)

        self.undo_button = QPushButton("Undo")
        self.undo_button.setObjectName("actionButton")
        self.undo_button.setCursor(Qt.PointingHandCursor)
        self.undo_button.setFocusPolicy(Qt.NoFocus)
        self.undo_button.setMinimumHeight(38)
        self.undo_button.clicked.connect(self.undo_action)
        bottom_row.addWidget(self.undo_button, stretch=1)

        self.skip_button = QPushButton("Skip")
        self.skip_button.setObjectName("actionButton")
        self.skip_button.setCursor(Qt.PointingHandCursor)
        self.skip_button.setFocusPolicy(Qt.NoFocus)
        self.skip_button.setMinimumHeight(38)
        self.skip_button.clicked.connect(self.skip_image)
        bottom_row.addWidget(self.skip_button, stretch=1)
        root.addLayout(bottom_row)

        self.update_folder_buttons()

    def _populate_filter_combo(self) -> None:
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItems(
            ["All Files", "All Images", "All Videos", "Animated / GIF", "Duplicates Only", "Flagged Only"]
        )
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            self.filter_combo.addItem(ext)
        self.filter_combo.blockSignals(False)

    def _add_menu_action(self, menu: QMenu, text: str, icon_kind: str, handler, shortcut: str = None,
                         checkable: bool = False, checked: bool = False, icon_color: str = None) -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(shortcut)
        if checkable:
            act.setCheckable(True)
            act.setChecked(checked)
        act.triggered.connect(handler)
        menu.addAction(act)
        self._menu_icon_specs.append((act, icon_kind, icon_color))
        return act

    def _build_menus(self) -> None:
        menubar = self.menuBar()
        self._menu_icon_specs.clear()

        # File Menu
        file_menu = menubar.addMenu("File")
        self._add_menu_action(file_menu, "Import Folder", "folder_search", self.import_folder_dialog, "Ctrl+O", icon_color="#3b82f6")
        self._add_menu_action(file_menu, "Show in File Explorer", "folder", self.show_in_explorer, "Ctrl+E")
        self._add_menu_action(file_menu, "Move to Recycle Bin", "trash", self.move_to_recycle_bin, "Delete", icon_color="#ef4444")
        self._add_menu_action(file_menu, "Export Log", "file_text", self.export_log)
        self._add_menu_action(file_menu, "Session Summary Report...", "report", self.show_session_summary, "Ctrl+Shift+R")
        file_menu.addSeparator()
        self.recent_menu = file_menu.addMenu("Recent Folders")
        self._menu_icon_specs.append((self.recent_menu.menuAction(), "clock", None))
        self._rebuild_recent_menu()

        # View Menu
        view_menu = menubar.addMenu("View")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self.theme_actions = {}
        for mode_id, label, icon_kind, tint in (
            ("custom", "Custom Theme", "palette", "#f43f5e"),
            ("light", "Light Mode", "sun", "#f59e0b"),
            ("dark", "Dark Mode", "moon", "#8b5cf6"),
            ("system", "System Default", "monitor", "#38bdf8"),
        ):
            act = self._add_menu_action(
                view_menu,
                label,
                icon_kind,
                self.open_custom_theme_dialog if mode_id == "custom" else (lambda _c=False, m=mode_id: self.set_theme_mode(m)),
                checkable=True,
                checked=(self.theme_mode == mode_id),
                icon_color=tint,
            )
            theme_group.addAction(act)
            self.theme_actions[mode_id] = act

        view_menu.addSeparator()

        # Sort By Submenu
        sort_menu = view_menu.addMenu("Sort By")
        self._menu_icon_specs.append((sort_menu.menuAction(), "sort", None))
        sort_group = QActionGroup(self)
        sort_group.setExclusive(True)
        self.sort_actions = {}
        for s_by, s_ord, s_lbl in (
            ("name", "asc", "Name (A – Z)"),
            ("name", "desc", "Name (Z – A)"),
            ("date", "desc", "Date Modified (Newest First)"),
            ("date", "asc", "Date Modified (Oldest First)"),
            ("size", "desc", "File Size (Largest First)"),
            ("size", "asc", "File Size (Smallest First)"),
            ("ext", "asc", "File Type / Extension"),
        ):
            is_active = (self.sort_by == s_by and self.sort_order == s_ord)
            s_act = self._add_menu_action(
                sort_menu,
                s_lbl,
                "sort",
                lambda _c=False, sb=s_by, so=s_ord: self.set_sort_order(sb, so),
                checkable=True,
                checked=is_active,
            )
            sort_group.addAction(s_act)
            self.sort_actions[(s_by, s_ord)] = s_act

        self.show_filmstrip_action = self._add_menu_action(
            view_menu, "Show Filmstrip Bar", "filmstrip", self.toggle_filmstrip, "Ctrl+B",
            checkable=True, checked=self.settings.get("show_filmstrip", True),
        )
        self.hide_moved_action = self._add_menu_action(
            view_menu, "Hide Moved Images", "eye_off", self.toggle_hide_moved, "Ctrl+H",
            checkable=True, checked=self.hide_moved,
        )
        self.include_subfolders_action = self._add_menu_action(
            view_menu, "Include Subfolders", "folder_tree", self.toggle_include_subfolders, "Ctrl+Shift+S",
            checkable=True, checked=self.include_subfolders,
        )
        self._add_menu_action(view_menu, "Find Duplicate / Similar Images", "duplicates", lambda: self.scan_duplicates(), "Ctrl+D")
        self._add_menu_action(view_menu, "Jump to Image...", "jump", self.jump_to_image_dialog, "Ctrl+G")
        self._add_menu_action(view_menu, "Full-Size Preview", "expand", self.open_full_preview, "F")

        # Settings Menu
        settings_menu = menubar.addMenu("Settings")
        self._add_menu_action(settings_menu, "Folder Settings", "folder_plus", self.open_folder_settings, icon_color="#10b981")
        self._add_menu_action(settings_menu, "Rapid Move Settings", "bolt", self.open_rapid_move_settings, icon_color="#f59e0b")
        self._add_menu_action(settings_menu, "Auto-Rename on Move...", "rename", self.open_auto_rename_settings)
        settings_menu.addSeparator()
        self._add_menu_action(settings_menu, "Export Settings", "upload", self.export_settings)
        self._add_menu_action(settings_menu, "Import Settings", "download", self.import_settings)
        settings_menu.addSeparator()
        self._add_menu_action(settings_menu, "Reset Default Settings", "reset", lambda: self.set_default_settings(confirm=True))

        # Help Menu
        help_menu = menubar.addMenu("Help")
        self._add_menu_action(help_menu, "Keyboard Shortcuts & Guide", "keyboard", self.show_shortcuts_guide, "F1")
        self._add_menu_action(help_menu, "Check for Updates", "update", self.check_for_updates_manual)
        help_menu.addSeparator()
        self._add_menu_action(help_menu, f"About {APP_NAME}", "info", self.show_about_dialog)

        self._update_dynamic_menu_actions()

    def _update_dynamic_menu_actions(self) -> None:
        """Update toggle menu actions (hide-moved, filmstrip, subfolders, theme, sort) with dynamic smart text, icons, and state."""
        t = resolve_studio_tokens(self)
        ic_col = t.get("menu_text", "#e4e6eb")

        # 1. Hide / Show Moved Images
        if hasattr(self, "hide_moved_action") and self.hide_moved_action is not None:
            if self.hide_moved:
                self.hide_moved_action.setText("Show Moved Images")
                self.hide_moved_action.setIcon(make_vector_icon("eye", ic_col, 15))
                self.hide_moved_action.setToolTip("Show images that were already moved (Ctrl+H)")
            else:
                self.hide_moved_action.setText("Hide Moved Images")
                self.hide_moved_action.setIcon(make_vector_icon("eye_off", ic_col, 15))
                self.hide_moved_action.setToolTip("Hide images that were already moved (Ctrl+H)")
            self.hide_moved_action.setChecked(self.hide_moved)

        # 2. Hide / Show Filmstrip Bar
        if hasattr(self, "show_filmstrip_action") and self.show_filmstrip_action is not None:
            is_filmstrip_showing = bool(self.settings.get("show_filmstrip", True))
            if is_filmstrip_showing:
                self.show_filmstrip_action.setText("Hide Filmstrip Bar")
                self.show_filmstrip_action.setIcon(make_vector_icon("filmstrip_off", ic_col, 15))
                self.show_filmstrip_action.setToolTip("Hide the mini filmstrip bar (Ctrl+B)")
            else:
                self.show_filmstrip_action.setText("Show Filmstrip Bar")
                self.show_filmstrip_action.setIcon(make_vector_icon("filmstrip", ic_col, 15))
                self.show_filmstrip_action.setToolTip("Show the mini filmstrip bar (Ctrl+B)")
            self.show_filmstrip_action.setChecked(is_filmstrip_showing)

        # 3. Include / Exclude Subfolders
        if hasattr(self, "include_subfolders_action") and self.include_subfolders_action is not None:
            if self.include_subfolders:
                self.include_subfolders_action.setText("Exclude Subfolders")
                self.include_subfolders_action.setIcon(make_vector_icon("folder", ic_col, 15))
                self.include_subfolders_action.setToolTip("Exclude nested subfolders from recursive scan (Ctrl+Shift+S)")
            else:
                self.include_subfolders_action.setText("Include Subfolders")
                self.include_subfolders_action.setIcon(make_vector_icon("folder_tree", ic_col, 15))
                self.include_subfolders_action.setToolTip("Include nested subfolders when scanning (Ctrl+Shift+S)")
            self.include_subfolders_action.setChecked(self.include_subfolders)

        # 4. Themes: Show active indicator ✓
        if hasattr(self, "theme_actions") and self.theme_actions:
            cur_mode = self.theme_mode or "system"
            labels = {
                "custom": "Custom Theme",
                "light": "Light Mode",
                "dark": "Dark Mode",
                "system": "System Default",
            }
            for m_id, act in self.theme_actions.items():
                base = labels.get(m_id, m_id.capitalize())
                is_cur = (m_id == cur_mode)
                act.setChecked(is_cur)
                act.setText(f"{base}   ✓" if is_cur else base)

        # 5. Sort By: Show active indicator ✓
        if hasattr(self, "sort_actions") and self.sort_actions:
            labels = {
                ("name", "asc"): "Name (A – Z)",
                ("name", "desc"): "Name (Z – A)",
                ("date", "desc"): "Date Modified (Newest First)",
                ("date", "asc"): "Date Modified (Oldest First)",
                ("size", "desc"): "File Size (Largest First)",
                ("size", "asc"): "File Size (Smallest First)",
                ("ext", "asc"): "File Type / Extension",
            }
            for (sb, so), act in self.sort_actions.items():
                base = labels.get((sb, so), "Sort")
                is_active = (self.sort_by == sb and self.sort_order == so)
                act.setChecked(is_active)
                act.setText(f"{base}   ✓" if is_active else base)

    def _rebuild_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        tokens = resolve_studio_tokens(self)
        valid_recent = [p for p in self.recent_folders if isinstance(p, str) and p.strip()][:10]
        if not valid_recent:
            empty_act = QAction("(No recent folders)", self)
            empty_act.setEnabled(False)
            empty_act.setIcon(make_vector_icon("clock", tokens["text_muted"], 14))
            self.recent_menu.addAction(empty_act)
            return
        folder_col = slot_text_color("#3b82f6", tokens["is_dark"])
        for path in valid_recent:
            act = QAction(path, self)
            act.setIcon(make_vector_icon("folder", folder_col, 14))
            act.triggered.connect(lambda _=False, p=path: self.open_recent_folder(p))
            self.recent_menu.addAction(act)
        self.recent_menu.addSeparator()
        clear_act = QAction("Clear Recent Folders", self)
        clear_act.setIcon(make_vector_icon("trash", slot_text_color("#ef4444", tokens["is_dark"]), 14))
        clear_act.triggered.connect(self.clear_recent_folders)
        self.recent_menu.addAction(clear_act)

    def open_recent_folder(self, folder_path: str) -> None:
        """Open a folder from Recent Folders, or prune it cleanly if it no longer exists on disk."""
        if not folder_path or not os.path.isdir(folder_path):
            self.recent_folders = [
                p for p in self.recent_folders if norm_path_key(p) != norm_path_key(folder_path or "")
            ]
            self._sync_and_save_settings()
            self._rebuild_recent_menu()
            show_studio_message(
                self,
                "Folder Not Found",
                f"The folder no longer exists and was removed from Recent Folders:\n{folder_path}",
                kind="warning",
            )
            return
        self.import_folder(folder_path)

    def clear_recent_folders(self) -> None:
        """Clear saved recent folders list and persist immediately."""
        self.recent_folders = []
        self.last_opened_folder = self.current_folder or ""
        self._sync_and_save_settings()
        self._rebuild_recent_menu()
        self._show_toast("Cleared Recent Folders")

    def _set_status_badge(self, text: str, kind: str = "empty") -> None:
        """Update top-left status badge with high-contrast semantic styling for Dark and Light themes."""
        self._status_badge_kind = kind
        self.moved_badge.setText(text)
        t = resolve_studio_tokens(self)
        if kind == "moved":
            fg = slot_text_color("#10b981", t["is_dark"])
            bg = hex_rgba("#10b981", 32 if t["is_dark"] else 24)
            bd = hex_rgba(fg, 115)
        elif kind == "unsorted":
            fg = t["text"]
            bg = t["surface"]
            bd = t["border_strong"]
        else:
            fg = t["text_muted"]
            bg = t["surface"]
            bd = t["border"]
        self.moved_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {bd}; "
            f"border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 700;"
        )

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=self.show_previous)
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=self.show_next)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.skip_image)
        QShortcut(QKeySequence(Qt.Key_Home), self, activated=self.jump_first)
        QShortcut(QKeySequence(Qt.Key_End), self, activated=self.jump_last)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo_action)
        QShortcut(QKeySequence(Qt.Key_P), self, activated=self.toggle_main_playback)
        QShortcut(QKeySequence(Qt.Key_M), self, activated=self.toggle_main_mute)
        QShortcut(QKeySequence(Qt.Key_Asterisk), self, activated=self.toggle_flag_current)
        QShortcut(QKeySequence("Shift+8"), self, activated=self.toggle_flag_current)
        QShortcut(QKeySequence("Alt+F"), self, activated=self.toggle_flag_current)

    # ------------------------------------------------------------------
    # Theme & Responsive Button/Stage Styling
    # ------------------------------------------------------------------
    def set_theme_mode(self, mode: str) -> None:
        """Switch active Studio theme mode ('system', 'dark', 'light', 'custom') and persist."""
        if mode not in ("system", "dark", "light", "custom"):
            return
        self.theme_mode = mode
        if hasattr(self, "theme_actions") and mode in self.theme_actions:
            self.theme_actions[mode].setChecked(True)
        self._sync_and_save_settings()
        self.apply_theme()

    def apply_theme(self) -> None:
        """Apply unified Studio Slate tokens across window, menubar, menus, buttons, and media views."""
        t = resolve_studio_tokens(self)
        apply_studio_palette(t)
        accent_hover = darken_color(t["accent"], 0.88)
        self.setStyleSheet(f"""
            QMainWindow, QWidget#centralHost {{
                background-color: {t['win_bg']};
                color: {t['text']};
            }}
            QWidget {{
                color: {t['text']};
            }}
            QMenuBar {{
                background-color: {t['win_bg']};
                color: {t['text']};
                border-bottom: 1px solid {t['border']};
                padding: 3px 8px;
                font-size: 12.5px;
                font-weight: 600;
            }}
            QMenuBar::item {{
                background: transparent;
                color: {t['text']};
                padding: 5px 11px;
                border-radius: 6px;
            }}
            QMenuBar::item:selected {{
                background-color: {t['surface_hover']};
                color: {t['text']};
            }}
            QMenu {{
                background-color: {t['menu_bg']};
                color: {t['menu_text']};
                border: 1px solid {t['border_strong']};
                border-radius: 10px;
                padding: 6px 4px;
            }}
            QMenu::item {{
                color: {t['menu_text']};
                padding: 7px 26px 7px 10px;
                border-radius: 6px;
                margin: 1px 4px;
            }}
            QMenu::icon {{
                left: 8px;
            }}
            QMenu::item:selected {{
                background-color: {t['surface_hover']};
                color: {t['menu_text']};
            }}
            QMenu::item:disabled {{
                color: {t['text_muted']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {t['border']};
                margin: 5px 10px;
            }}
            QFrame#infoBar, QFrame#nextStageCard {{
                background-color: {t['stage_bg']};
                border: 1px solid {t['next_border']};
                border-radius: 10px;
            }}
            QFrame#mainStageCard {{
                background-color: {t['stage_bg']};
                border: 1px solid {t['border_strong']};
                border-radius: 12px;
            }}
            QLabel#statusBadge {{
                background-color: {t['surface']};
                color: {t['text_muted']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11.5px;
                font-weight: 700;
            }}
            QLabel#fileInfoLabel {{
                color: {t['text']};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
            QLabel#counterBadge {{
                background-color: {t['surface']};
                color: {t['text']};
                border: 1px solid {t['border_strong']};
                border-radius: 6px;
                padding: 3px 12px;
                font-family: Consolas, monospace;
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#upNextHeader {{
                color: {t['text_muted']};
                font-size: 10.5px;
                font-weight: 800;
                letter-spacing: 1.1px;
                background: transparent;
                border: none;
            }}
            QLabel#mainMediaSurface, QLabel#nextMediaSurface {{
                background-color: {t['card_bg']};
                border: 1px solid {t['border']};
                border-radius: 9px;
                color: {t['text_muted']};
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#navButton, QPushButton#actionButton {{
                background-color: {t['surface']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 9px;
                font-size: 12.5px;
                font-weight: 600;
                padding: 6px 14px;
                min-height: 28px;
            }}
            QPushButton#navButton:hover, QPushButton#actionButton:hover {{
                background-color: {t['surface_hover']};
                border-color: {t['border_strong']};
            }}
            QPushButton#navButton:pressed, QPushButton#actionButton:pressed {{
                background-color: {t['surface_pressed']};
            }}
            QComboBox#filterCombo {{
                combobox-popup: 0;
                background-color: {t['surface']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 9px;
                padding: 4px 28px 4px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QComboBox#filterCombo:hover {{
                background-color: {t['surface_hover']};
                border-color: {accent_hover};
            }}
            QComboBox#filterCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border: none;
                background: transparent;
            }}
            QComboBox#filterCombo::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
                border: none;
            }}
            QComboBox#filterCombo QAbstractItemView {{
                background-color: {t['menu_bg']};
                color: {t['menu_text']};
                border: 1px solid {t['border_strong']};
                border-radius: 8px;
                padding: 4px;
                outline: 0;
                selection-background-color: {t['surface_hover']};
                selection-color: {t['menu_text']};
            }}
            QComboBox#filterCombo QAbstractItemView::item {{
                color: {t['menu_text']};
                min-height: 26px;
                padding: 3px 10px;
                border-radius: 5px;
            }}
            QComboBox#filterCombo QAbstractItemView::item:selected {{
                background-color: {t['surface_hover']};
                color: {t['menu_text']};
            }}
            QComboBox#filterCombo QAbstractItemView QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0;
            }}
            QComboBox#filterCombo QAbstractItemView QScrollBar::handle:vertical {{
                background: {t['border_strong']};
                min-height: 24px;
                border-radius: 4px;
            }}
            QComboBox#filterCombo QAbstractItemView QScrollBar::add-line:vertical,
            QComboBox#filterCombo QAbstractItemView QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        if hasattr(self, "filter_combo") and hasattr(self.filter_combo, "set_arrow_color"):
            self.filter_combo.set_arrow_color(t["text"])

        # Refresh vector icons across menus and navigation/action buttons
        for act, kind, explicit_col in self._menu_icon_specs:
            ic = slot_text_color(explicit_col, t["is_dark"]) if explicit_col else t["menu_text"]
            act.setIcon(make_vector_icon(kind, ic, 15))
        self.prev_button.setIcon(make_vector_icon("prev", t["text"], 14))
        self.prev_button.setIconSize(QSize(14, 14))
        self.next_button.setIcon(make_vector_icon("next", t["text"], 14))
        self.next_button.setIconSize(QSize(14, 14))
        self.undo_button.setIcon(make_vector_icon("undo", t["text"], 14))
        self.undo_button.setIconSize(QSize(14, 14))
        self.skip_button.setIcon(make_vector_icon("skip", t["text"], 14))
        self.skip_button.setIconSize(QSize(14, 14))

        self._rebuild_recent_menu()
        self.update_folder_buttons()
        if hasattr(self, "filmstrip_bar") and self.filmstrip_bar is not None:
            self.filmstrip_bar.apply_tokens(t)
        self._update_flag_button()
        self._render_empty_or_current_stage()
        if self.hud_overlay is not None:
            self.hud_overlay.apply_tokens(t)
            self.hud_overlay.refresh_labels(paused=self._main_paused, muted=self.video_muted)
        self._update_dynamic_menu_actions()

    def update_folder_buttons(self) -> None:
        """Render 3..9 visible quick-sort folder buttons with semantic Studio accent tinting."""
        t = resolve_studio_tokens(self)
        compact = self.folder_slot_count >= 7
        font_px = 11.5 if compact else 12.5
        for i, btn in enumerate(self.folder_buttons):
            visible = i < self.folder_slot_count
            btn.setVisible(visible)
            if not visible:
                continue
            accent = SLOT_ACCENTS[i % len(SLOT_ACCENTS)]
            fg_accent = slot_text_color(accent, t["is_dark"])
            label = (self.folder_names[i] if i < len(self.folder_names) else DEFAULT_FOLDER_NAMES[i]) or DEFAULT_FOLDER_NAMES[i]
            btn.setText(f"[{i + 1}] {label}")
            btn.setToolTip(f"Move to '{label}'\nDestination: {self.folder_paths[i]}\n(Klik kanan untuk opsi folder)")
            btn.setIcon(make_vector_icon("folder", fg_accent, 14 if compact else 15))
            btn.setIconSize(QSize(14 if compact else 15, 14 if compact else 15))
            btn.setStyleSheet(
                f"QPushButton#folderSlotBtn {{"
                f" background-color: {hex_rgba(accent, 36 if t['is_dark'] else 26)};"
                f" color: {t['text']};"
                f" border: 1px solid {hex_rgba(fg_accent, 120 if t['is_dark'] else 135)};"
                f" border-radius: 10px;"
                f" font-size: {font_px}px; font-weight: 700; padding: 6px 8px;"
                f"}}"
                f"QPushButton#folderSlotBtn:hover {{"
                f" background-color: {hex_rgba(accent, 64 if t['is_dark'] else 48)};"
                f" border-color: {fg_accent};"
                f"}}"
                f"QPushButton#folderSlotBtn:pressed {{"
                f" background-color: {hex_rgba(accent, 92 if t['is_dark'] else 68)};"
                f"}}"
            )

    def _sync_minimum_window_size(self) -> None:
        min_w = max(780, self.folder_slot_count * 98)
        self.setMinimumSize(min_w, 560)
        if self.width() < min_w:
            self.resize(min_w, self.height())

    def load_custom_folders(self) -> None:
        """Reload slot count, names, and paths from persisted settings and refresh folder buttons."""
        s = load_settings()
        self.settings.update(s)
        self.folder_slot_count = clamp_folder_slots(s.get("folder_slot_count", self.folder_slot_count))
        names = list(s.get("folder_names", self.folder_names))
        paths = list(s.get("folder_paths", self.folder_paths))
        while len(names) < MAX_FOLDER_SLOTS:
            names.append(DEFAULT_FOLDER_NAMES[len(names)])
        while len(paths) < MAX_FOLDER_SLOTS:
            paths.append(DEFAULT_FOLDER_PATHS[len(paths)])
        self.folder_names = names
        self.folder_paths = paths
        self.update_folder_buttons()
        self._sync_minimum_window_size()

    # ------------------------------------------------------------------
    # Toast, Folder Import, Scanning & Queue Loading
    # ------------------------------------------------------------------
    def _show_toast(self, message: str) -> None:
        self.toast.show_message(message, resolve_studio_tokens(self))

    def show_loading(self, message: str = "Loading folder...") -> None:
        self.loading_overlay.set_text(message)
        self.loading_overlay.show_with_tokens(resolve_studio_tokens(self))

    def hide_loading(self) -> None:
        self.loading_overlay.hide()

    def import_folder_dialog(self) -> None:
        start_dir = ""
        for candidate in (self.current_folder, self.last_opened_folder, *(self.recent_folders or [])):
            if candidate and os.path.isdir(candidate):
                start_dir = candidate
                break
        if not start_dir:
            start_dir = os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Sort", start_dir)
        if folder:
            self.import_folder(folder)

    def import_folder(self, folder_path: str) -> None:
        """Scan a source folder on a background QThread and populate the media queue."""
        if not folder_path or not os.path.isdir(folder_path):
            show_studio_message(self, "Invalid Folder", "The selected folder does not exist.", kind="warning")
            return

        if self._pending_scan_thread is not None and self._pending_scan_thread.isRunning():
            self._pending_scan_thread.cancel()
            self._pending_scan_thread.wait(500)

        self._record_recent_folder(folder_path)
        self.show_loading("Scanning media folder...")
        excluded = self.folder_paths[: self.folder_slot_count] if self.include_subfolders else []
        thread = FolderScanThread(
            folder_path,
            parent=self,
            include_subfolders=self.include_subfolders,
            excluded_dirs=excluded,
        )
        thread.progress_updated.connect(lambda cnt: self.loading_overlay.set_text(f"Found {cnt} media files..."))
        thread.finished.connect(lambda t=thread, fp=folder_path: self._on_folder_scan_finished(fp, t))
        self._pending_scan_thread = thread
        thread.start()

    def _on_folder_scan_finished(self, folder_path: str, thread: FolderScanThread) -> None:
        self.hide_loading()
        if thread.error:
            show_studio_message(self, "Scan Error", f"Could not scan folder:\n{thread.error}", kind="error")
            return
        self.load_file_list(folder_path, thread.files)

    def _record_recent_folder(self, folder_path: str) -> None:
        if not folder_path or not os.path.isdir(folder_path):
            return
        norm = os.path.normpath(os.path.abspath(folder_path))
        self.last_opened_folder = norm
        self.recent_folders = [norm] + [p for p in self.recent_folders if norm_path_key(p) != norm_path_key(norm)]
        self.recent_folders = self.recent_folders[:10]
        self._sync_and_save_settings()
        self._rebuild_recent_menu()

    def load_file_list(self, folder_path: str, file_list) -> None:
        """Load pre-scanned media paths into the queue, validate history, and render index 0."""
        self.current_folder = folder_path
        if folder_path and os.path.isdir(folder_path):
            self._record_recent_folder(folder_path)
        self.current_meta_cache.clear()
        self.pixmap_cache.clear()
        self.media_queue.set_files(file_list)
        self.media_queue.load_flagged(self.settings.get("flagged_files", []))
        sort_by = self.settings.get("sort_by", "name")
        sort_order = self.settings.get("sort_order", "asc")
        if sort_by != "name" or sort_order != "asc":
            self.media_queue.sort_files(sort_by, sort_order)
        self.history_store.validate()
        self.apply_filter(preserve_current=False)

    def apply_filter(self, preserve_current: bool = True) -> None:
        """Apply active extension/category & Hide-Moved filters without losing queue anchor."""
        selected = self.filter_combo.currentText() if hasattr(self, "filter_combo") else "All Files"
        self.media_queue.apply_filter(selected, self.hide_moved, preserve_current=preserve_current)
        if not preserve_current:
            self.media_queue.current_index = 0
        self.show_current_image(self.filtered_files)

    def toggle_hide_moved(self, checked: bool = None) -> None:
        if checked is not None:
            self.hide_moved = bool(checked)
        else:
            self.hide_moved = not self.hide_moved
        self._sync_and_save_settings()
        self._update_dynamic_menu_actions()
        self.apply_filter()
        self._show_toast("Hiding moved images" if self.hide_moved else "Showing moved images")

    def toggle_include_subfolders(self, checked: bool = None) -> None:
        if checked is not None:
            self.include_subfolders = bool(checked)
        else:
            self.include_subfolders = not self.include_subfolders
        self._sync_and_save_settings()
        self._update_dynamic_menu_actions()
        if self.current_folder and os.path.isdir(self.current_folder):
            self.import_folder(self.current_folder)
        self._show_toast("Including subfolders in scan" if self.include_subfolders else "Excluding subfolders from scan")

    # ------------------------------------------------------------------
    # Media Display, Pre-Fetch Cache & Zero-Lock Playback
    # ------------------------------------------------------------------
    def _stop_all_media_playback(self) -> None:
        self._deferred_anim_timer.stop()
        self._anim_timer.stop()
        if self._video_decode_thread is not None and self._video_decode_thread.isRunning():
            self._video_decode_thread.cancel()
            self._video_decode_thread.wait(300)
        self._video_decode_thread = None

        self.video_controller.stop()

        if self.current_movie is not None:
            try:
                self.current_movie.stop()
                self.current_movie.frameChanged.disconnect()
            except Exception:
                pass
            self.current_movie.deleteLater()
            self.current_movie = None
        if self._movie_buffer is not None:
            try:
                self._movie_buffer.close()
            except Exception:
                pass
            self._movie_buffer.deleteLater()
            self._movie_buffer = None
        self._movie_bytes = None
        self._anim_frames = []
        self._anim_index = 0

        if self.hud_overlay is not None:
            self.hud_overlay.hide()
            self.hud_overlay.deleteLater()
            self.hud_overlay = None

    def _paint_fitted_pixmap(self, label: QLabel, viewport: StageViewport, pix: QPixmap, max_w: int, max_h: int,
                             is_next: bool = False) -> QSize:
        """Fit pixmap into stage box, update QLabel geometry, center in viewport, and raise HUD if main."""
        fitted = resize_next_preview(pix, max_w, max_h) if is_next else fit_pixmap_to_box(pix, max_w, max_h)
        if fitted is not None and not fitted.isNull():
            sz = fitted.size()
            label.setText("")
            label.setPixmap(fitted)
            label.setFixedSize(sz)
            viewport.center_child()
            if not is_next and self.hud_overlay is not None:
                self.hud_overlay.raise_()
            return sz
        return QSize(max_w, max_h)

    def _stage_budgets(self):
        vp_m = self.main_stage_viewport.size()
        vp_n = self.next_stage_viewport.size()
        return (
            max(180, vp_m.width() - 8),
            max(140, vp_m.height() - 8),
            max(90, vp_n.width() - 8),
            max(100, vp_n.height() - 8),
        )

    def _render_empty_or_current_stage(self) -> None:
        if self.filtered_files:
            self.show_current_image(self.filtered_files)
            return
        self._stop_all_media_playback()
        t = resolve_studio_tokens(self)
        mw, mh, nw, nh = self._stage_budgets()
        self.main_image_label.setPixmap(QPixmap())
        self.main_image_label.setText(build_empty_state_html(t, self.folder_slot_count, compact=(mw < 420)))
        self.main_image_label.setFixedSize(mw, mh)
        self.main_image_label.setToolTip("Click to import folder (Ctrl+O) or drop a folder here")
        self.main_stage_viewport.setToolTip("Click to import folder (Ctrl+O) or drop a folder here")
        self.main_image_label.setCursor(Qt.PointingHandCursor)
        self.main_stage_viewport.setCursor(Qt.PointingHandCursor)
        self.main_stage_viewport.center_child()

        self.next_image_label.setPixmap(QPixmap())
        self.next_image_label.setText("No upcoming\nmedia")
        self.next_image_label.setFixedSize(nw, nh)
        self.next_stage_viewport.center_child()

        self._set_status_badge("Empty Queue" if self.image_files else "No media loaded", kind="empty")
        self.file_info_label.setText("Drop a folder or press Ctrl+O to start sorting" if not self.image_files else "No items match the active filter")
        self.counter_label.setText(f"0 / {len(self.image_files)}" if self.image_files else "0 / 0")
        self._update_flag_button(None)
        self._update_filmstrip()

    def show_current_image(self, files=None) -> None:
        """Display the active queue item, Up-Next preview, metadata strip, and deferred animation/video."""
        queue = self.filtered_files if files is None else files
        if not queue or not (0 <= self.current_index < len(queue)):
            self._render_empty_or_current_stage()
            return

        self._stop_all_media_playback()
        self._main_paused = False
        self._main_seeking = False

        src_path = queue[self.current_index]
        actual_path = self.history_store.resolve_actual_path(src_path)
        self._active_media_path = actual_path

        self.main_image_label.setToolTip("Double-click to open Full-Size Zoom Preview (F)")
        self.main_stage_viewport.setToolTip("")
        self.main_image_label.setCursor(Qt.PointingHandCursor)
        self.main_stage_viewport.setCursor(Qt.ArrowCursor)

        self.counter_label.setText(f"{self.current_index + 1} / {len(queue)}")
        moved_folder = self.history_store.get_folder_name(src_path, self.folder_names, self.folder_paths)
        if moved_folder:
            self._set_status_badge(f"Moved → {moved_folder}", kind="moved")
        else:
            self._set_status_badge("Unsorted", kind="unsorted")

        mw, mh, nw, nh = self._stage_budgets()
        if not os.path.exists(actual_path):
            self._active_main_pixmap = QPixmap()
            self.main_image_label.setPixmap(QPixmap())
            self.main_image_label.setText("File missing or moved externally")
            self.main_image_label.setFixedSize(mw, mh)
            self.main_stage_viewport.center_child()
            self._update_file_info_bar(src_path, actual_path, self._active_main_pixmap)
            self._update_next_preview(queue, nw, nh)
            return

        pix = self.pixmap_cache.get_pixmap(actual_path, mw, mh)
        self._active_main_pixmap = pix

        if not pix.isNull():
            target_sz = self._paint_fitted_pixmap(self.main_image_label, self.main_stage_viewport, pix, mw, mh)
        else:
            target_sz = QSize(mw, mh)
            self.main_image_label.setPixmap(QPixmap())
            self.main_image_label.setText(f"Cannot preview {os.path.basename(actual_path)}")
            self.main_image_label.setFixedSize(mw, mh)
            self.main_stage_viewport.center_child()

        dur_s = self._update_file_info_bar(src_path, actual_path, pix)
        self._update_next_preview(queue, nw, nh)
        self._update_flag_button(src_path)
        self._update_filmstrip()

        ext = os.path.splitext(actual_path)[1].lower()
        is_vid = is_video_file(actual_path)
        if is_vid or ext in _ANIM_IMAGE_EXTS:
            fcount = 2 if is_vid else (self.current_meta_cache.get(actual_path, (0, 0, 0, "", 1))[4])
            if is_vid or fcount > 1:
                self._create_main_hud(target_sz, is_video=is_vid, duration_s=dur_s)
                if ext == ".gif" and not is_vid:
                    self._start_gif_movie(actual_path)
                else:
                    self._deferred_anim_timer.start(85)

        self._prefetch_neighbor_images()

    def _create_main_hud(self, target_size: QSize, is_video: bool, duration_s: float = 0.0) -> None:
        self.hud_overlay = MediaHudOverlay(
            self.main_image_label,
            target_size,
            is_video=is_video,
            duration_s=duration_s,
            volume=self.video_volume,
            tokens=resolve_studio_tokens(self),
        )
        self.hud_overlay.play_pause_clicked.connect(self.toggle_main_playback)
        self.hud_overlay.mute_clicked.connect(self.toggle_main_mute)
        self.hud_overlay.volume_changed.connect(self.set_video_volume)
        self.hud_overlay.seek_pressed.connect(lambda: setattr(self, "_main_seeking", True))
        self.hud_overlay.seek_released.connect(self._on_main_seek_released)
        self.hud_overlay.seek_clicked.connect(self._on_main_seek_clicked)
        self.hud_overlay.reposition(self.main_image_label.size(), paused=self._main_paused, muted=self.video_muted)

    def set_video_volume(self, volume: float) -> None:
        """Update live audio volume and persist setting."""
        self.video_volume = max(0.0, min(1.0, float(volume)))
        self.settings["video_volume"] = self.video_volume
        if self._main_video_using_qtmm and self._main_audio_output:
            self._main_audio_output.setVolume(self.video_volume)
        if self.video_muted and self.video_volume > 0.0:
            self.set_video_muted(False)
        self._sync_and_save_settings()

    def _update_flag_button(self, src_path: str = None) -> None:
        """Update bookmark/flag button label and icon reflecting the active media state."""
        if not hasattr(self, "flag_btn") or self.flag_btn is None:
            return
        t = resolve_studio_tokens(self)
        if not src_path and self.filtered_files and 0 <= self.current_index < len(self.filtered_files):
            src_path = self.filtered_files[self.current_index]
        is_fl = self.media_queue.is_flagged(src_path) if src_path else False
        if is_fl:
            self.flag_btn.setText("Flagged")
            self.flag_btn.setIcon(make_vector_icon("star_filled", "#f59e0b", 13))
            self.flag_btn.setStyleSheet(
                "QPushButton#flagBtn {"
                " background-color: rgba(245, 158, 11, 42);"
                " color: #f59e0b;"
                " border: 1px solid rgba(245, 158, 11, 150);"
                " border-radius: 6px;"
                " font-size: 11.5px; font-weight: 700; padding: 3px 9px;"
                "}"
            )
        else:
            self.flag_btn.setText("Flag")
            self.flag_btn.setIcon(make_vector_icon("star", t["text_muted"], 13))
            self.flag_btn.setStyleSheet(
                f"QPushButton#flagBtn {{"
                f" background-color: {t['surface']};"
                f" color: {t['text_muted']};"
                f" border: 1px solid {t['border']};"
                f" border-radius: 6px;"
                f" font-size: 11.5px; font-weight: 600; padding: 3px 9px;"
                f"}}"
                f"QPushButton#flagBtn:hover {{"
                f" color: {t['text']};"
                f" border-color: {t['border_strong']};"
                f"}}"
            )

    def toggle_flag_current(self) -> None:
        """Toggle bookmark/flag state for currently selected media item."""
        if not self.filtered_files or not (0 <= self.current_index < len(self.filtered_files)):
            return
        src_path = self.filtered_files[self.current_index]
        new_state = self.media_queue.toggle_flag(src_path)
        self.settings["flagged_files"] = self.media_queue.get_flagged_list()
        self._sync_and_save_settings()
        self._update_flag_button(src_path)
        self._update_filmstrip()
        self._show_toast("Marked as Flagged ★" if new_state else "Removed Flag ☆")
        if hasattr(self, "filter_combo") and self.filter_combo.currentText() == "Flagged Only":
            self.apply_filter()

    def _update_filmstrip(self) -> None:
        """Synchronize filmstrip bar thumbnails with active queue item."""
        if not hasattr(self, "filmstrip_bar") or self.filmstrip_bar is None:
            return
        if not self.settings.get("show_filmstrip", True):
            self.filmstrip_bar.hide()
            return
        self.filmstrip_bar.update_strip(
            self.filtered_files,
            self.current_index,
            self.pixmap_cache,
            is_flagged_cb=self.media_queue.is_flagged,
            is_moved_cb=self.history_store.is_moved,
        )

    def toggle_filmstrip(self, checked: bool = None) -> None:
        """Toggle filmstrip preview bar visibility and persist setting."""
        if checked is not None:
            show = bool(checked)
        else:
            show = not self.settings.get("show_filmstrip", True)
        self.settings["show_filmstrip"] = show
        self._sync_and_save_settings()
        if hasattr(self, "filmstrip_bar"):
            self.filmstrip_bar.setVisible(show)
            if show:
                self._update_filmstrip()
            self._relayout_stage_previews()
        self._update_dynamic_menu_actions()
        self._show_toast("Filmstrip visible" if show else "Filmstrip hidden")

    def set_sort_order(self, sort_by: str, sort_order: str) -> None:
        """Re-sort media queue by selected criteria (name, date, size, ext) and preserve active anchor."""
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.settings["sort_by"] = sort_by
        self.settings["sort_order"] = sort_order
        self._sync_and_save_settings()
        self._update_dynamic_menu_actions()

        if hasattr(self, "sort_actions"):
            for (sb, so), act in self.sort_actions.items():
                act.setChecked(sb == sort_by and so == sort_order)

        selected_filter = self.filter_combo.currentText() if hasattr(self, "filter_combo") else "All Files"
        self.media_queue.sort_files(
            sort_by=sort_by,
            sort_order=sort_order,
            selected_filter=selected_filter,
            hide_moved=self.hide_moved,
        )
        self.show_current_image(self.filtered_files)
        self._update_filmstrip()

        titles = {
            ("name", "asc"): "Name (A – Z)",
            ("name", "desc"): "Name (Z – A)",
            ("date", "desc"): "Date Modified (Newest First)",
            ("date", "asc"): "Date Modified (Oldest First)",
            ("size", "desc"): "File Size (Largest First)",
            ("size", "asc"): "File Size (Smallest First)",
            ("ext", "asc"): "File Type / Extension",
        }
        title = titles.get((sort_by, sort_order), f"{sort_by} ({sort_order})")
        self._show_toast(f"Sorted by {title}")

    def open_auto_rename_settings(self) -> None:
        """Open auto-rename configuration dialog."""
        dlg = AutoRenameSettingsDialog(self)
        dlg.exec()

    def show_session_summary(self) -> None:
        """Open session sorting statistics summary report dialog."""
        summary = generate_session_summary(
            source_folder=self.current_folder,
            all_files=self.media_queue.all_files,
            history_records=self.history_store.records,
            flagged_paths=self.media_queue.flagged_norms,
            slot_names=self.folder_names[: self.folder_slot_count],
            slot_paths=self.folder_paths[: self.folder_slot_count],
        )
        dlg = SessionSummaryDialog(summary, self)
        dlg.exec()

    def _update_file_info_bar(self, src_path: str, actual_path: str, pix: QPixmap) -> float:
        meta = self.current_meta_cache.get(actual_path)
        duration_s = 0.0
        if os.path.exists(actual_path):
            if meta is None:
                if is_video_file(actual_path):
                    w, h, sz, _fps, fcount, duration_s = self.pixmap_cache.get_video_metadata(actual_path)
                    ext_lbl = os.path.splitext(src_path)[1].lstrip(".").upper()
                    fmt = f"{ext_lbl} VIDEO" if ext_lbl else "VIDEO"
                    meta = (w, h, sz, fmt, fcount, duration_s)
                else:
                    w, h, sz, fmt_raw, fcount = self.pixmap_cache.get_metadata(actual_path)
                    fmt = (
                        fmt_raw.decode("ascii", "ignore").upper()
                        if isinstance(fmt_raw, (bytes, bytearray))
                        else str(fmt_raw or "").upper()
                    )
                    meta = (w, h, sz, fmt, fcount, 0.0)
                self.current_meta_cache[actual_path] = meta
            else:
                duration_s = meta[5] if len(meta) > 5 else 0.0
            w, h, sz, fmt, fcount = meta[:5]
            if (w <= 0 or h <= 0) and not pix.isNull():
                w, h = pix.width(), pix.height()
            parts = [
                os.path.basename(src_path),
                f"{w}×{h}" if w > 0 and h > 0 else "—",
                format_file_size(sz),
                fmt or os.path.splitext(src_path)[1].lstrip(".").upper(),
            ]
            if is_video_file(actual_path) and duration_s > 0:
                parts.append(format_duration(duration_s))
            elif fcount > 1:
                parts.append(f"{fcount} frames")
        else:
            parts = [os.path.basename(src_path), "Missing"]

        dup_info = self.media_queue.duplicate_group_lookup.get(norm_path_key(src_path))
        if dup_info:
            parts.append(f"DUP #{dup_info[0]} ({dup_info[1]} copies)")

        self.file_info_label.setText("  ·  ".join(parts))
        return duration_s

    def _update_next_preview(self, queue, nw: int, nh: int) -> None:
        next_idx = self.media_queue.find_valid_next_index(self.current_index, queue)
        if next_idx is None:
            self._active_next_pixmap = QPixmap()
            self.next_image_label.setPixmap(QPixmap())
            self.next_image_label.setText("End of\nqueue")
            self.next_image_label.setFixedSize(nw, nh)
            self.next_stage_viewport.center_child()
            return

        next_actual = self.history_store.resolve_actual_path(queue[next_idx])
        next_pix = self.pixmap_cache.get_pixmap(next_actual, nw, nh)
        self._active_next_pixmap = next_pix

        if not next_pix.isNull():
            self._paint_fitted_pixmap(self.next_image_label, self.next_stage_viewport, next_pix, nw, nh, is_next=True)
        else:
            self.next_image_label.setPixmap(QPixmap())
            self.next_image_label.setText(os.path.basename(next_actual))
            self.next_image_label.setFixedSize(nw, nh)
            self.next_stage_viewport.center_child()

    def _prefetch_neighbor_images(self) -> None:
        queue = self.filtered_files
        if not queue:
            return
        mw, mh, nw, nh = self._stage_budgets()
        for delta in (1, 2, -1, 3, -2):
            idx = self.current_index + delta
            if 0 <= idx < len(queue):
                actual = self.history_store.resolve_actual_path(queue[idx])
                if actual and os.path.exists(actual):
                    if not self.pixmap_cache.has_pixmap(actual, mw, mh):
                        self.pixmap_cache.get_pixmap(actual, mw, mh)
                    if not self.pixmap_cache.has_pixmap(actual, nw, nh):
                        self.pixmap_cache.get_pixmap(actual, nw, nh)

    def _relayout_stage_previews(self) -> None:
        if not self.filtered_files or not (0 <= self.current_index < len(self.filtered_files)):
            self._render_empty_or_current_stage()
            return
        mw, mh, nw, nh = self._stage_budgets()
        if not self._active_main_pixmap.isNull():
            self._paint_fitted_pixmap(self.main_image_label, self.main_stage_viewport, self._active_main_pixmap, mw, mh)
        else:
            self.main_stage_viewport.center_child()

        if not self._active_next_pixmap.isNull():
            self._paint_fitted_pixmap(self.next_image_label, self.next_stage_viewport, self._active_next_pixmap, nw, nh, is_next=True)
        else:
            self.next_stage_viewport.center_child()

        if self.hud_overlay is not None:
            self.hud_overlay.reposition(self.main_image_label.size(), paused=self._main_paused, muted=self.video_muted)

    # ------------------------------------------------------------------
    # Deferred Animation & Zero-Lock Video Playback
    # ------------------------------------------------------------------
    def _start_gif_movie(self, path: str) -> bool:
        """Load animated GIF via in-memory QBuffer + QMovie so Windows never holds a file handle."""
        try:
            with open(path, "rb") as f:
                raw = f.read()
            self._movie_bytes = QByteArray(raw)
            self._movie_buffer = QBuffer(self)
            self._movie_buffer.setData(self._movie_bytes)
            self._movie_buffer.open(QIODevice.ReadOnly)
            movie = QMovie(self._movie_buffer, b"gif", self)
            if movie.isValid() and movie.frameCount() > 1:
                self.current_movie = movie
                movie.frameChanged.connect(self._on_movie_frame_changed)
                movie.start()
                if self._main_paused:
                    movie.setPaused(True)
                return True
            movie.deleteLater()
        except Exception as e:
            debug_log(f"In-memory GIF QMovie fallback: {e}")
        return False

    def _start_deferred_video_anim(self) -> None:
        """Start in-memory QMovie (GIF) or QtMultimedia video+audio (fallback: OpenCV) with zero file lock."""
        self._deferred_anim_timer.stop()
        path = self._active_media_path
        if not path or not os.path.exists(path):
            return

        if is_video_file(path):
            started = self.video_controller.start(
                path, muted=self.video_muted, volume=self.video_volume, paused=self._main_paused
            )
            if not started:
                mw, mh, _, _ = self._stage_budgets()
                self._video_decode_thread = VideoDecodeThread(path, max_width=mw, max_height=mh, parent=self)
                self._video_decode_thread.chunk_ready.connect(self._on_video_decode_chunk)
                self._video_decode_thread.start()
            return

        ext = os.path.splitext(path)[1].lower()
        if ext == ".gif" and self.current_movie is None:
            if self._start_gif_movie(path):
                return

        if ext in _ANIM_IMAGE_EXTS:
            mw, mh, _, _ = self._stage_budgets()
            frames = load_animation_frames(path, mw, mh, max_frames=120)
            if len(frames) > 1:
                self._anim_frames = frames
                self._anim_index = 0
                if not self._main_paused:
                    self._anim_timer.start(max(25, frames[0][1]))

    def _on_movie_frame_changed(self, _frame_num: int) -> None:
        if self.current_movie is None or self._main_paused:
            return
        pix = self.current_movie.currentPixmap()
        if not pix.isNull():
            mw, mh, _, _ = self._stage_budgets()
            self._paint_fitted_pixmap(self.main_image_label, self.main_stage_viewport, pix, mw, mh)

    def _on_video_decode_chunk(self, target_path: str, chunk) -> None:
        if target_path != self._active_media_path or not chunk:
            return
        for qimg, delay in chunk:
            pix = QPixmap.fromImage(qimg)
            if not pix.isNull():
                self._anim_frames.append((pix, delay))
        if self._anim_frames and not self._anim_timer.isActive() and not self._main_paused:
            self._anim_timer.start(max(30, self._anim_frames[0][1]))

    def _advance_main_anim_frame(self) -> None:
        if not self._anim_frames or self._main_paused:
            return
        self._anim_index = (self._anim_index + 1) % len(self._anim_frames)
        pix, delay = self._anim_frames[self._anim_index]
        mw, mh, _, _ = self._stage_budgets()
        self._paint_fitted_pixmap(self.main_image_label, self.main_stage_viewport, pix, mw, mh)
        self._anim_timer.setInterval(max(25, int(delay)))

    def _on_main_qtmm_frame(self, qimg: QImage) -> None:
        if self._main_paused:
            return
        pix = QPixmap.fromImage(qimg)
        if pix.isNull():
            return
        mw, mh, _, _ = self._stage_budgets()
        self._paint_fitted_pixmap(self.main_image_label, self.main_stage_viewport, pix, mw, mh)

    def _on_main_qtmm_position(self, pos_ms: int) -> None:
        if not self._main_seeking and self.hud_overlay is not None:
            self.hud_overlay.set_position_ms(pos_ms)

    def _on_main_qtmm_duration(self, dur_ms: int) -> None:
        if self.hud_overlay is not None:
            self.hud_overlay.set_duration_ms(dur_ms)

    def _on_main_qtmm_error(self, _err: str) -> None:
        if self._active_media_path and is_video_file(self._active_media_path):
            mw, mh, _, _ = self._stage_budgets()
            self._video_decode_thread = VideoDecodeThread(self._active_media_path, max_width=mw, max_height=mh, parent=self)
            self._video_decode_thread.chunk_ready.connect(self._on_video_decode_chunk)
            self._video_decode_thread.start()

    def _on_main_seek_released(self) -> None:
        self._main_seeking = False
        if self.hud_overlay is not None and self.hud_overlay.seek_slider is not None:
            self._on_main_seek_clicked(int(self.hud_overlay.seek_slider.value()))

    def _on_main_seek_clicked(self, pos_ms: int) -> None:
        self.video_controller.seek(pos_ms)
        if self.hud_overlay is not None:
            self.hud_overlay.set_position_ms(pos_ms)

    def toggle_main_playback(self) -> None:
        """Toggle main preview playback between Playing and Paused."""
        if self.hud_overlay is None:
            return
        self._main_paused = not self._main_paused
        if self.video_controller.player is not None:
            if self._main_paused:
                self.video_controller.pause()
            else:
                self.video_controller.play()
        elif self.current_movie is not None:
            self.current_movie.setPaused(self._main_paused)
        elif self._anim_frames:
            if self._main_paused:
                self._anim_timer.stop()
            else:
                self._anim_timer.start(max(25, self._anim_frames[self._anim_index][1]))
        self.hud_overlay.refresh_labels(paused=self._main_paused, muted=self.video_muted)

    def set_video_muted(self, muted: bool, notify: bool = True) -> None:
        """Persist mute preference and update active QtMultimedia audio output & HUD."""
        self.video_muted = bool(muted)
        self.video_controller.set_muted(self.video_muted)
        self._sync_and_save_settings()
        if self.hud_overlay is not None:
            self.hud_overlay.refresh_labels(paused=self._main_paused, muted=self.video_muted)
        if notify:
            self._show_toast("Sound Muted" if self.video_muted else "Sound Unmuted")

    def toggle_main_mute(self) -> None:
        if self.hud_overlay is not None and self.hud_overlay.is_video:
            self.set_video_muted(not self.video_muted)

    # ------------------------------------------------------------------
    # Navigation, Moving, Rapid Move, Undo, Recycle Bin
    # ------------------------------------------------------------------
    def _record_nav(self) -> None:
        if self.filtered_files and 0 <= self.current_index < len(self.filtered_files):
            self.media_queue.nav_history.append(self.current_index)

    def show_next(self) -> None:
        if not self.filtered_files:
            return
        next_idx = self.media_queue.find_valid_next_index(self.current_index)
        if next_idx is not None:
            self._record_nav()
            self.current_index = next_idx
            self.show_current_image(self.filtered_files)

    def show_previous(self) -> None:
        if not self.filtered_files:
            return
        prev_idx = self.media_queue.find_valid_previous_index(self.current_index)
        if prev_idx is not None:
            self._record_nav()
            self.current_index = prev_idx
            self.show_current_image(self.filtered_files)

    def skip_image(self) -> None:
        if not self.filtered_files:
            return
        idx = self.media_queue.find_next_unmoved_index(self.current_index)
        if idx is None:
            idx = self.media_queue.find_next_unmoved_index(-1)
        if idx is not None and idx != self.current_index:
            self._record_nav()
            self.current_index = idx
            self.show_current_image(self.filtered_files)
        else:
            self._show_toast("All visible items sorted!")

    def jump_first(self) -> None:
        if self.filtered_files:
            self._record_nav()
            self.current_index = 0
            self.show_current_image(self.filtered_files)

    def jump_last(self) -> None:
        if self.filtered_files:
            self._record_nav()
            self.current_index = len(self.filtered_files) - 1
            self.show_current_image(self.filtered_files)

    def jump_to_image_dialog(self) -> None:
        if not self.filtered_files:
            self._show_toast("No media loaded.")
            return
        dlg = JumpToMediaDialog(self, total_count=len(self.filtered_files), current_one_based=self.current_index + 1)
        if dlg.exec() == JumpToMediaDialog.Accepted:
            self._record_nav()
            self.current_index = max(0, min(len(self.filtered_files) - 1, dlg.selected_index()))
            self.show_current_image(self.filtered_files)

    def jump_to_index(self, idx: int) -> None:
        """Jump directly to a specific 0-based queue index."""
        if not self.filtered_files:
            return
        if 0 <= idx < len(self.filtered_files) and idx != self.current_index:
            self._record_nav()
            self.current_index = idx
            self.show_current_image(self.filtered_files)

    def open_full_preview(self) -> None:
        src, actual = self.media_queue.current_paths()
        if not actual or not os.path.exists(actual):
            return
        was_playing = not self._main_paused
        if was_playing and self.hud_overlay is not None:
            self.toggle_main_playback()
        dlg = ImagePreviewDialog(actual, self)
        dlg.exec()
        if was_playing and self.hud_overlay is not None and self._main_paused:
            self.toggle_main_playback()

    def move_to_custom_folder(self, dest_folder: str) -> bool:
        """Move current media safely to dest_folder with collision auto-renaming & undo history."""
        if not self.filtered_files or not (0 <= self.current_index < len(self.filtered_files)):
            return False
        if not dest_folder:
            return False

        src_path = self.filtered_files[self.current_index]
        actual_path = self.history_store.resolve_actual_path(src_path)
        if not os.path.exists(actual_path):
            self._show_toast("Source file not found.")
            return False

        # Release any playback locks (Windows safety) before file move
        self._stop_all_media_playback()

        try:
            os.makedirs(dest_folder, exist_ok=True)
            norm_src_dir = norm_path_key(os.path.dirname(actual_path))
            norm_dest_dir = norm_path_key(dest_folder)
            if norm_src_dir == norm_dest_dir:
                self._show_toast("Already in destination folder.")
                self.show_current_image(self.filtered_files)
                return False

            filename_candidate = os.path.basename(actual_path)
            matched_name = None
            for name, p in zip(self.folder_names, self.folder_paths):
                if p and norm_path_key(p) == norm_dest_dir:
                    matched_name = name
                    break
            folder_label = matched_name or os.path.basename(dest_folder)

            if self.settings.get("auto_rename_enabled", False):
                pattern = self.settings.get("auto_rename_pattern", "{folder}_{index:04d}")
                filename_candidate = format_auto_rename_filename(
                    pattern=pattern,
                    orig_path=actual_path,
                    folder_name=folder_label,
                    index=len(self.history_store.records) + 1,
                )

            dest_path = get_unique_destination(dest_folder, filename_candidate)
            shutil.move(actual_path, dest_path)

            self.history_store.record_move(src_path, dest_path)
            self._history_flush_timer.start()

            entry = format_log_entry(f"Moved '{os.path.basename(actual_path)}' -> '{dest_folder}'")
            self.log_entries.append(entry)
            append_event_log([entry])

            folder_label = self.history_store.get_folder_name(src_path, self.folder_names, self.folder_paths) or os.path.basename(dest_folder)
            self._show_toast(f"Moved → {folder_label}")

            if self.hide_moved:
                old_idx = self.current_index
                self.media_queue.apply_filter(self.filter_combo.currentText(), True, preserve_current=False)
                self.current_index = min(old_idx, max(0, len(self.filtered_files) - 1))
            else:
                next_idx = self.media_queue.find_valid_next_index(self.current_index)
                if next_idx is not None:
                    self.current_index = next_idx

            self.show_current_image(self.filtered_files)
            return True
        except Exception as e:
            debug_log(f"Move error: {e}")
            show_studio_message(self, "Move Failed", f"Could not move file:\n{e}", kind="error")
            self.show_current_image(self.filtered_files)
            return False

    def undo_action(self) -> None:
        """Restore the most recently sorted file back to its prior location safely."""
        last_entry = self.history_store.pop_last()
        if not last_entry:
            self._show_toast("Nothing to undo.")
            return

        orig_src, moved_dest = last_entry
        if not os.path.exists(moved_dest):
            self.history_store.clear_cache_entry(orig_src)
            self._history_flush_timer.start()
            self._show_toast("Moved file missing — removed stale history entry.")
            return

        self._stop_all_media_playback()
        try:
            os.makedirs(os.path.dirname(orig_src), exist_ok=True)
            restore_target = orig_src
            if os.path.lexists(restore_target):
                restore_target = get_unique_destination(os.path.dirname(orig_src), os.path.basename(orig_src))
            shutil.move(moved_dest, restore_target)
            self.history_store.clear_cache_entry(orig_src)
            self.history_store.dirty = True
            self._history_flush_timer.start()

            entry = format_log_entry(f"Undo -> '{os.path.basename(restore_target)}'")
            self.log_entries.append(entry)
            append_event_log([entry])

            if self.hide_moved:
                self.media_queue.apply_filter(self.filter_combo.currentText(), True, preserve_current=False)
            if orig_src in self.filtered_files:
                self.current_index = self.filtered_files.index(orig_src)

            self.show_current_image(self.filtered_files)
            self._show_toast(f"Undo → Restored {os.path.basename(restore_target)}")
        except Exception as e:
            self.history_store.push_back(orig_src, moved_dest)
            show_studio_message(self, "Undo Failed", f"Could not restore file:\n{e}", kind="error")
            self.show_current_image(self.filtered_files)

    def move_to_recycle_bin(self) -> None:
        src_path, actual_path = self.media_queue.current_paths()
        if not actual_path or not os.path.exists(actual_path):
            return
        self._stop_all_media_playback()
        if send_to_recycle_bin(actual_path):
            self.history_store.remove_source(src_path)
            self._history_flush_timer.start()
            self.media_queue.all_files = [p for p in self.media_queue.all_files if p != src_path]
            old_idx = self.current_index
            self.media_queue.apply_filter(self.filter_combo.currentText(), self.hide_moved, preserve_current=False)
            self.current_index = min(old_idx, max(0, len(self.filtered_files) - 1))
            self.show_current_image(self.filtered_files)
            self._show_toast("Moved to Recycle Bin")
        else:
            show_studio_message(self, "Delete Failed", "Could not move file to the Recycle Bin.", kind="error")
            self.show_current_image(self.filtered_files)

    def show_in_explorer(self) -> None:
        _, actual = self.media_queue.current_paths()
        if actual and os.path.exists(actual):
            reveal_in_file_explorer(actual)

    # ------------------------------------------------------------------
    # Rapid Move Keyboard & Mouse Handlers
    # ------------------------------------------------------------------
    @property
    def is_rapid_moving(self) -> bool:
        """Return True while a Rapid Move slot session is active."""
        return self._active_rapid_slot is not None

    def start_rapid_move(self, slot_idx: int, source: str = "key") -> None:
        """Begin a Rapid Move session for slot_idx (used by interactive hold & automated tests)."""
        if slot_idx < 0 or slot_idx >= self.folder_slot_count:
            return
        self._stop_rapid_move()
        self._active_rapid_slot = int(slot_idx)
        self._rapid_moved_in_hold = False
        self._rapid_move_delay_timer.start(self.rapid_move_interval_ms)

    def rapid_move(self) -> bool:
        """Execute one step of an active Rapid Move session and stop when exhausted."""
        if self._active_rapid_slot is None or not self.filtered_files:
            self._stop_rapid_move()
            return False
        idx = self._active_rapid_slot
        if idx < 0 or idx >= self.folder_slot_count:
            self._stop_rapid_move()
            return False
        moved = self.move_to_custom_folder(self.folder_paths[idx])
        if not moved:
            self._stop_rapid_move()
            return False
        return True

    def _on_folder_btn_pressed(self, slot_idx: int) -> None:
        if slot_idx < 0 or slot_idx >= self.folder_slot_count:
            return
        self.start_rapid_move(slot_idx, source="mouse")
        if self.move_to_custom_folder(self.folder_paths[slot_idx]):
            self._rapid_moved_in_hold = True

    def _on_folder_btn_released(self) -> None:
        self._stop_rapid_move()

    def _begin_rapid_loop(self) -> None:
        if self._active_rapid_slot is not None:
            self._rapid_move_timer.start(self.rapid_move_interval_ms)

    def _on_rapid_move_tick(self) -> None:
        self.rapid_move()

    def _stop_rapid_move(self) -> None:
        self._rapid_move_delay_timer.stop()
        self._rapid_move_timer.stop()
        self._active_rapid_slot = None

    def _show_folder_btn_context_menu(self, slot_idx: int, pos) -> None:
        """Present a context menu for folder slot buttons allowing instant folder picking, explorer opening, and renaming."""
        if slot_idx < 0 or slot_idx >= self.folder_slot_count:
            return
        btn = self.folder_buttons[slot_idx]
        cur_name = (self.folder_names[slot_idx] if slot_idx < len(self.folder_names) else DEFAULT_FOLDER_NAMES[slot_idx]) or DEFAULT_FOLDER_NAMES[slot_idx]
        cur_path = self.folder_paths[slot_idx] if slot_idx < len(self.folder_paths) else ""
        t = resolve_studio_tokens(self)

        menu = QMenu(self)
        menu.setStyleSheet(build_studio_dialog_qss(t))

        header_action = QAction(f"Folder Slot [{slot_idx + 1}] — {cur_name}", self)
        header_action.setEnabled(False)
        menu.addAction(header_action)
        menu.addSeparator()

        change_act = QAction("Pilih / Ganti Folder...", self)
        change_act.setIcon(make_vector_icon("folder", t["accent"], 14))
        change_act.triggered.connect(lambda: self._quick_pick_slot_folder(slot_idx))
        menu.addAction(change_act)

        open_act = QAction("Buka di File Explorer", self)
        open_act.setIcon(make_vector_icon("folder_tree", t["text"], 14))
        path_exists = bool(cur_path and os.path.exists(cur_path))
        open_act.setEnabled(path_exists)
        if path_exists:
            open_act.triggered.connect(lambda: reveal_in_file_explorer(cur_path))
        menu.addAction(open_act)

        rename_act = QAction("Ubah Nama Slot...", self)
        rename_act.setIcon(make_vector_icon("rename", t["text"], 14))
        rename_act.triggered.connect(lambda: self._quick_rename_slot(slot_idx))
        menu.addAction(rename_act)

        menu.addSeparator()
        full_settings_act = QAction("Pengaturan Folder Lengkap...", self)
        full_settings_act.setIcon(make_vector_icon("sliders", t["text"], 14))
        full_settings_act.triggered.connect(self.open_folder_settings)
        menu.addAction(full_settings_act)

        menu.exec(btn.mapToGlobal(pos))

    def _quick_pick_slot_folder(self, slot_idx: int) -> None:
        """Quick directory picker for an individual folder slot."""
        if slot_idx < 0 or slot_idx >= self.folder_slot_count:
            return
        cur_path = self.folder_paths[slot_idx] if slot_idx < len(self.folder_paths) else ""
        start_dir = cur_path if cur_path and os.path.exists(cur_path) else os.getcwd()
        new_dir = QFileDialog.getExistingDirectory(
            self,
            f"Pilih Folder Tujuan untuk Slot [{slot_idx + 1}]",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if new_dir:
            self.folder_paths[slot_idx] = new_dir
            self._sync_and_save_settings()
            self.update_folder_buttons()
            leaf = os.path.basename(os.path.normpath(new_dir))
            self._show_toast(f"Slot [{slot_idx + 1}] diarahkan ke: {leaf}")

    def _quick_rename_slot(self, slot_idx: int) -> None:
        """Quick dialog to rename an individual folder slot."""
        if slot_idx < 0 or slot_idx >= self.folder_slot_count:
            return
        cur_name = (self.folder_names[slot_idx] if slot_idx < len(self.folder_names) else DEFAULT_FOLDER_NAMES[slot_idx]) or DEFAULT_FOLDER_NAMES[slot_idx]
        new_name, ok = QInputDialog.getText(
            self,
            "Ubah Nama Slot",
            f"Nama baru untuk Slot [{slot_idx + 1}]:",
            text=cur_name,
        )
        if ok and new_name.strip():
            self.folder_names[slot_idx] = new_name.strip()
            self._sync_and_save_settings()
            self.update_folder_buttons()
            self._show_toast(f"Slot [{slot_idx + 1}] dinamai: {new_name.strip()}")

    def eventFilter(self, obj, event):
        etype = event.type()
        targets = [w for w in (self.main_image_label, self.main_stage_viewport, self.main_card) if w is not None]
        if obj in targets:
            if etype == event.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                if not self.filtered_files:
                    self.import_folder_dialog()
                    return True
            elif etype == event.Type.MouseButtonDblClick and event.button() == Qt.LeftButton:
                if self.filtered_files:
                    self.open_full_preview()
                    return True

        if etype in (event.Type.KeyPress, event.Type.KeyRelease):
            if QApplication.activeModalWidget() is not None:
                return super().eventFilter(obj, event)
            fw = QApplication.focusWidget()
            if isinstance(fw, (QLineEdit, QSpinBox)):
                return super().eventFilter(obj, event)

            key = event.key()
            if Qt.Key_1 <= key <= Qt.Key_9 and not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
                slot_idx = key - Qt.Key_1
                if slot_idx < self.folder_slot_count:
                    if etype == event.Type.KeyPress and not event.isAutoRepeat():
                        self._stop_rapid_move()
                        self._active_rapid_slot = slot_idx
                        self.move_to_custom_folder(self.folder_paths[slot_idx])
                        self._rapid_move_delay_timer.start(self.rapid_move_interval_ms)
                        return True
                    if etype == event.Type.KeyRelease and not event.isAutoRepeat():
                        self._stop_rapid_move()
                        return True

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Duplicate Scanner
    # ------------------------------------------------------------------
    def scan_duplicates(self, max_distance: int = 6, synchronous: bool = False) -> int:
        """Scan loaded media with perceptual dHash and filter queue to detected duplicate clusters."""
        if not self.image_files:
            self._show_toast("Load a folder before scanning for duplicates.")
            return 0

        targets = self.media_queue.resolve_duplicate_targets()
        actual_paths = []
        actual_to_srcs = {}
        seen_actuals = set()
        for src, act in targets:
            na = norm_path_key(act)
            actual_to_srcs.setdefault(na, []).append(src)
            if na not in seen_actuals:
                seen_actuals.add(na)
                actual_paths.append(act)

        if len(actual_paths) < 2:
            self._show_toast("Need at least 2 existing media items to compare.")
            return 0

        if synchronous:
            _dup_norms, groups, _hash_map = find_duplicate_groups(actual_paths, max_distance=max_distance)
            return self._on_duplicate_scan_done(groups, actual_to_srcs, show_toast=False)

        self.show_loading("Scanning perceptual dHash signatures...")
        t = DuplicateScanThread(actual_paths, max_distance=max_distance, parent=self)
        t.progress_updated.connect(lambda done, total: self.loading_overlay.set_text(f"Analyzing {done} / {total} files..."))
        t.finished.connect(lambda th=t, m=actual_to_srcs: self._on_dup_thread_finished(th, m))
        self._pending_dup_thread = t
        t.start()
        return 0

    def _on_dup_thread_finished(self, thread: DuplicateScanThread, actual_to_srcs: dict) -> None:
        self.hide_loading()
        if thread.error:
            show_studio_message(self, "Duplicate Scan Error", thread.error, kind="error")
            return
        self._on_duplicate_scan_done(thread.groups, actual_to_srcs, show_toast=True)

    def _on_duplicate_scan_done(self, groups, actual_to_srcs: dict, show_toast: bool = True) -> int:
        self.media_queue.populate_duplicate_results(groups, actual_to_srcs)
        found = len(self.media_queue.duplicate_norms)
        if found > 0:
            self.filter_combo.setCurrentText("Duplicates Only")
            self.apply_filter(preserve_current=False)
            if show_toast:
                self._show_toast(f"Found {found} similar/duplicate files across {len(self.duplicate_groups)} groups.")
        elif show_toast:
            self._show_toast("No duplicate or visually similar files found.")
        return found

    # ------------------------------------------------------------------
    # Dialogs, Log/Settings Import-Export, Updates, Drag & Drop
    # ------------------------------------------------------------------
    def open_custom_theme_dialog(self) -> None:
        CustomThemeDialog(self).exec()

    def open_folder_settings(self) -> None:
        FolderSettingsDialog(self).exec()

    def open_rapid_move_settings(self) -> None:
        RapidMoveSettingsDialog(self).exec()

    def show_shortcuts_guide(self) -> None:
        ShortcutsGuideDialog(self).exec()

    def show_about_dialog(self) -> None:
        AboutDialog(self).exec()

    def check_for_updates_manual(self) -> None:
        self.show_loading("Checking GitHub releases...")
        t = UpdateCheckThread(parent=self, manual=True)
        t.update_checked.connect(self._on_update_checked)
        t.error_occurred.connect(self._on_update_error)
        self._pending_update_thread = t
        t.start()

    def _on_update_checked(self, latest: str, notes: str, url: str) -> None:
        self.hide_loading()
        UpdateDialog(
            self,
            current_version=APP_VERSION,
            latest_version=latest,
            release_notes=notes,
            download_url=url,
        ).exec()

    def _on_update_error(self, err: str) -> None:
        self.hide_loading()
        UpdateDialog(self, current_version=APP_VERSION, check_failed=True, error_message=err).exec()

    def export_log(self) -> None:
        default_name = f"imagesorter_log_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Export Event Log", default_name, "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.log_entries) + ("\n" if self.log_entries else ""))
            self._show_toast("Event log exported.")
        except OSError as e:
            show_studio_message(self, "Export Failed", f"Could not write log file:\n{e}", kind="error")

    def export_settings(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Settings", "imagesorter_settings.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            current_cfg = self._sync_and_save_settings()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(current_cfg, f, indent=4, ensure_ascii=False)
            self._show_toast("Settings exported.")
        except OSError as e:
            show_studio_message(self, "Export Failed", f"Could not export settings:\n{e}", kind="error")

    def import_settings(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Settings", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                imported = json.load(f)
            if not isinstance(imported, dict):
                raise ValueError("Invalid settings JSON structure.")
            merged = normalize_settings(imported, first_run_default=False)
            save_settings(merged)
            self._apply_loaded_settings(merged)
            self._show_toast("Settings imported and applied.")
        except Exception as e:
            show_studio_message(self, "Import Failed", f"Invalid settings file:\n{e}", kind="error")

    def set_default_settings(self, confirm: bool = False) -> None:
        """Restore clean default settings across themes, slots, filters, and rapid move speed."""
        if confirm:
            ans = show_studio_message(
                self,
                "Reset Default Settings",
                "Reset theme, folder slot settings, and preferences back to defaults?",
                kind="question",
                buttons=QMessageBox.Yes | QMessageBox.No,
                default_button=QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return

        defaults = default_settings_copy(first_run=False)
        save_settings(defaults)
        self._apply_loaded_settings(defaults)

    def _apply_loaded_settings(self, data: dict) -> None:
        norm = normalize_settings(data, first_run_default=False)
        self.settings = norm
        self.theme_mode = norm["theme_mode"]
        self.custom_theme = copy.deepcopy(norm["custom_theme"])
        self.folder_slot_count = norm["folder_slot_count"]
        self.folder_names = list(norm["folder_names"])
        self.folder_paths = list(norm["folder_paths"])
        self.recent_folders = list(norm["recent_folders"])
        self.last_opened_folder = norm["last_opened_folder"]
        self.rapid_move_interval_ms = norm["rapid_move_interval"]
        self.video_muted = norm["video_muted"]
        self.video_volume = norm["video_volume"]
        self.hide_moved = norm["hide_moved"]
        self.include_subfolders = norm["include_subfolders"]
        self.hide_moved_action.setChecked(self.hide_moved)
        self.include_subfolders_action.setChecked(self.include_subfolders)
        if self.theme_mode in self.theme_actions:
            self.theme_actions[self.theme_mode].setChecked(True)
        self.apply_theme()
        self._sync_minimum_window_size()
        if self.image_files:
            self.apply_filter()

    def _reload_external_settings(self) -> None:
        self._apply_loaded_settings(load_settings())
        self._show_toast("Reloaded external settings.json")

    def _perform_hot_reload(self) -> None:
        state = {
            "timestamp": time.time(),
            "current_folder": self.current_folder,
            "current_index": self.current_index,
            "filter": self.filter_combo.currentText(),
        }
        self._stop_all_media_playback()
        self.history_store.flush()
        if HotReloadWatcher.write_state_and_spawn(state):
            QApplication.quit()

    def _restore_hot_reload_session(self, state: dict) -> None:
        folder = state.get("current_folder")
        if folder and os.path.isdir(folder):
            self.import_folder(folder)
            if state.get("filter"):
                self.filter_combo.setCurrentText(state["filter"])
            if isinstance(state.get("current_index"), int):
                self.current_index = max(0, min(max(0, len(self.filtered_files) - 1), state["current_index"]))
                self.show_current_image(self.filtered_files)

    # ------------------------------------------------------------------
    # Qt Events: Drag & Drop, Resize, Close Cleanup
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                if u.isLocalFile() and os.path.isdir(u.toLocalFile()):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            if u.isLocalFile() and os.path.isdir(u.toLocalFile()):
                self.import_folder(u.toLocalFile())
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast.reposition()

    def closeEvent(self, event):
        self._stop_rapid_move()
        self._stop_all_media_playback()
        if hasattr(self, "hot_reload"):
            self.hot_reload.stop()
        if hasattr(self, "_history_flush_timer"):
            self._history_flush_timer.stop()
        self.history_store.flush()
        self._sync_and_save_settings()
        super().closeEvent(event)
