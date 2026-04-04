from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from application import FreeTreeWorkspaceController
from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree, FreeTreeNode
from infrastructure.storage import ProjectStorageService, UserConfigService, resolve_storage_roots
from UI.Widgets import (
    EmptyStateWidget,
    InfoStatTileWidget,
    ProjectWorkspaceWidget,
    SettingsWorkspaceWidget,
    SidebarMenu,
    resolve_block_asset_path,
)
from UI.themes import (
    FONT_SIZE_DEFAULT,
    active_theme_name,
    active_theme_tokens_ref,
    apply_theme,
    initialize_widget_primitives,
    install_widget_primitives,
)
from UI.windows.free_tree_window import FreeTreeWindow
from UI.windows.media_carousel_window import MediaCarouselWindow
from UI.windows.project_visual_picker_dialog import ProjectVisualPickerDialog
from UI.windows.thumbnail_list_window import ThumbnailListWindow
from UI.windows.window_helpers import (
    load_app_icon as _load_app_icon,
    resolve_app_icon_path as _resolve_app_icon_path,
    resolve_data_project_dir as _resolve_data_project_dir,
)

PROJECT_ROOT_BLOCK_ID = "blk_project_root"
CHARACTERS_ROOT_BLOCK_ID = "blk_characters_root"
STORY_ROOT_BLOCK_ID = "blk_story_root"
LIB_ROOT_BLOCK_ID = "blk_lib_root"
INTERNAL_LIB_ROOT_BLOCK_ID = "blk_internal_lib_root"
INTERNAL_LIB_EMPTY_BLOCK_ID = "blk_internal_lib_empty"
PROJECT_DIR_SUFFIX = ".sbcprj"

class MainWindow(QMainWindow):
    """Main empty application window."""

    def __init__(self, *, blocks: list[Block] | None = None, project_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SBC2")
        icon = _load_app_icon()
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)
        self._section_key = "dashboard"
        self._user_config = UserConfigService()

        resolved_blocks: list[Block] | None = list(blocks) if blocks is not None else None
        resolved_project_root = project_root
        if resolved_blocks is None and resolved_project_root is not None:
            resolved_blocks = self._load_blocks_safely(resolved_project_root)
        if resolved_blocks is None and resolved_project_root is None:
            restored_project_root = self._user_config.load_last_project_path()
            if restored_project_root is not None and restored_project_root.exists():
                restored_blocks = self._load_blocks_safely(restored_project_root)
                if restored_blocks is not None:
                    resolved_project_root = restored_project_root
                    resolved_blocks = restored_blocks
                else:
                    self._user_config.save_last_project_path(None)
            elif restored_project_root is not None:
                self._user_config.save_last_project_path(None)

        if resolved_blocks is None:
            resolved_blocks = []
            resolved_project_root = None
        elif resolved_project_root is not None:
            normalized_project_root = resolved_project_root.expanduser().resolve()
            resolved_blocks = self._ensure_workspace_structure_on_open(normalized_project_root, resolved_blocks)
            resolved_project_root = normalized_project_root

        self._blocks = resolved_blocks
        self._project_root = resolved_project_root
        self._thumbnail_window: ThumbnailListWindow | None = None
        self._media_carousel_window: MediaCarouselWindow | None = None
        self._free_tree_window: FreeTreeWindow | None = None
        self._storage_roots = resolve_storage_roots()
        self._icons_dir = Path(__file__).resolve().parents[2] / "icons"
        self._action_icon_cache: dict[tuple[str, str], QIcon] = {}
        self._sidebar = SidebarMenu(self, on_navigation=self._on_sidebar_navigation)
        self._workspace_header = QLabel("DASHBOARD", self)
        self._workspace_header.setObjectName("WorkspaceHeader")
        self._workspace_header.setProperty("section", True)
        self._workspace_header.setProperty("workspaceTitle", True)
        self._workspace_header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._workspace_footer = QLabel("Application is running", self)
        self._workspace_footer.setObjectName("WorkspaceFooter")
        self._workspace_footer.setProperty("muted", True)
        self._workspace_footer.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._workspace_actions_frame = QFrame(self)
        self._workspace_actions_frame.setProperty("panelAlt", True)
        self._settings_workspace = SettingsWorkspaceWidget(self)
        self._settings_workspace.theme_changed.connect(self._apply_theme_from_settings)
        self._settings_workspace.set_current_theme(active_theme_name())
        self._settings_workspace.set_storage_paths(
            projects_root=self._storage_roots.projects_root,
            user_libraries_root=self._storage_roots.user_libraries_root,
            application_libraries_root=self._storage_roots.application_libraries_root,
        )
        self._project_workspace = ProjectWorkspaceWidget(self)
        self._project_workspace.new_project_requested.connect(self._create_new_project)
        self._project_workspace.open_project_requested.connect(self._open_project_from_dialog)
        self._project_workspace.close_project_requested.connect(self._close_current_project)
        self._project_workspace.project_tree_requested.connect(self._open_free_tree_window)
        self._project_workspace.select_visual_requested.connect(self._select_project_visual_from_carousel)
        self._project_workspace.save_requested.connect(self._save_project_metadata_from_workspace)
        # Public aliases kept for compatibility with existing tests/callers.
        self._new_project_button = self._project_workspace._new_project_button
        self._open_project_button = self._project_workspace._open_project_button
        self._close_project_button = self._project_workspace._close_project_button
        self._open_free_tree_button = self._project_workspace._project_tree_button
        self._select_project_visual_button = self._project_workspace._select_visual_button
        self._open_thumbnail_button = self._create_open_thumbnail_button(
            "Open Thumbnail List",
            icon_name="project_folder_open.svg",
        )
        self._open_thumbnail_button_primary = self._create_open_thumbnail_button(
            "Open Primary",
            style_property="primary",
            icon_name="project_layout_dashboard.svg",
        )
        self._open_thumbnail_button_accent = self._create_open_thumbnail_button(
            "Open Accent",
            style_property="accent",
            icon_name="edit_filter_2_spark.svg",
        )
        self._open_thumbnail_button_ghost = self._create_open_thumbnail_button(
            "Open Ghost",
            style_property="ghost",
            icon_name="story_world_message_circle_user.svg",
        )
        self._open_thumbnail_button_magic = self._create_open_thumbnail_button(
            "Open AI Magic",
            style_property="aiMagic",
            icon_name="actions_adjustments_search.svg",
        )
        self._open_thumbnail_buttons = [
            self._open_thumbnail_button,
            self._open_thumbnail_button_primary,
            self._open_thumbnail_button_accent,
            self._open_thumbnail_button_ghost,
            self._open_thumbnail_button_magic,
        ]
        self._open_media_carousel_button = self._create_workspace_button(
            "Open Media Carousel",
            on_click=self._open_media_carousel_window,
            style_property="primary",
            icon_name="project_layout_dashboard.svg",
        )
        self._workspace_action_buttons = [*self._open_thumbnail_buttons, self._open_media_carousel_button]

        self._dashboard_stats_frame = QFrame(self)
        self._dashboard_stats_frame.setProperty("panelAlt", True)
        dashboard_stats_layout = QVBoxLayout(self._dashboard_stats_frame)
        dashboard_stats_layout.setContentsMargins(9, 9, 9, 9)
        dashboard_stats_layout.setSpacing(9)
        self._dashboard_stats_title = QLabel("PROJECT STATS", self._dashboard_stats_frame)
        self._dashboard_stats_title.setProperty("section", True)
        self._dashboard_stats_grid_widget = QWidget(self._dashboard_stats_frame)
        self._dashboard_stats_grid = QGridLayout(self._dashboard_stats_grid_widget)
        self._dashboard_stats_grid.setContentsMargins(0, 0, 0, 0)
        self._dashboard_stats_grid.setHorizontalSpacing(9)
        self._dashboard_stats_grid.setVerticalSpacing(9)
        self._dashboard_stat_tiles: dict[str, InfoStatTileWidget] = {}
        self._build_dashboard_stat_tiles()
        dashboard_stats_layout.addWidget(self._dashboard_stats_title)
        dashboard_stats_layout.addWidget(self._dashboard_stats_grid_widget)

        actions_layout = QHBoxLayout(self._workspace_actions_frame)
        actions_layout.setContentsMargins(9, 9, 9, 9)
        actions_layout.setSpacing(9)
        for button in self._workspace_action_buttons:
            actions_layout.addWidget(button, 0, Qt.AlignLeft)
        actions_layout.addStretch(1)

        self._workspace_dashboard_page = QWidget(self)
        dashboard_layout = QVBoxLayout(self._workspace_dashboard_page)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(9)
        dashboard_layout.addWidget(self._project_workspace, 1)
        dashboard_layout.addWidget(self._dashboard_stats_frame, 0)

        self._workspace_tools_page = QWidget(self)
        tools_layout = QVBoxLayout(self._workspace_tools_page)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(9)
        tools_layout.addWidget(self._workspace_actions_frame)
        tools_layout.addStretch(1)

        self._workspace_settings_page = QWidget(self)
        settings_layout = QVBoxLayout(self._workspace_settings_page)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(9)
        settings_layout.addWidget(self._settings_workspace, 1)

        self._workspace_project_page = QWidget(self)
        project_layout = QVBoxLayout(self._workspace_project_page)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(9)
        self._project_page_empty_state = EmptyStateWidget(
            "PROJECT WORKSPACE MOVED",
            description="Project actions and metadata are now available on DASHBOARD.",
            action_text="OPEN DASHBOARD",
            parent=self._workspace_project_page,
        )
        self._project_page_empty_state.action_requested.connect(lambda: self._navigate_to_workspace_section("dashboard"))
        project_layout.addWidget(self._project_page_empty_state, 1)

        self._workspace_stack = QStackedWidget(self)
        self._workspace_stack.addWidget(self._workspace_dashboard_page)
        self._workspace_stack.addWidget(self._workspace_tools_page)
        self._workspace_stack.addWidget(self._workspace_settings_page)
        self._workspace_stack.addWidget(self._workspace_project_page)
        self._workspace_stack.setCurrentWidget(self._workspace_dashboard_page)

        workspace_panel = QWidget(self)
        workspace_panel.setProperty("panel", True)
        workspace_layout = QVBoxLayout(workspace_panel)
        workspace_layout.setContentsMargins(14, 14, 14, 14)
        workspace_layout.setSpacing(9)
        workspace_layout.addWidget(self._workspace_header)
        workspace_layout.addWidget(self._workspace_stack, 1)
        workspace_layout.addWidget(self._workspace_footer)

        root = QWidget(self)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._sidebar, 0)
        root_layout.addWidget(workspace_panel, 1)
        self.setCentralWidget(root)
        self._update_workspace_footer()
        self._refresh_project_workspace()
        initialize_widget_primitives(self)

    def _on_sidebar_navigation(self, key: str) -> None:
        self._section_key = key
        self._workspace_header.setText(key.replace("_", " ").upper())
        if key == "tools":
            self._workspace_stack.setCurrentWidget(self._workspace_tools_page)
            return
        if key == "settings":
            self._workspace_stack.setCurrentWidget(self._workspace_settings_page)
            return
        if key == "project":
            self._workspace_stack.setCurrentWidget(self._workspace_project_page)
            return
        self._workspace_stack.setCurrentWidget(self._workspace_dashboard_page)

    def _navigate_to_workspace_section(self, key: str) -> None:
        button = self._sidebar.nav_button(key)
        if button is not None:
            button.click()
            return
        self._sidebar.set_active(key)
        self._on_sidebar_navigation(key)

    def _update_workspace_footer(self) -> None:
        if self._project_root is None:
            self._workspace_footer.setText("Application is running")
            return
        self._workspace_footer.setText(f"Project: {self._project_root}")

    @staticmethod
    def _format_fs_datetime(timestamp: float) -> str:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")

    def _project_preview_from_blocks(self) -> str:
        if self._project_root is None:
            return ""
        for block in self._blocks:
            if block.type != BlockType.IMAGE:
                continue
            resolved = resolve_block_asset_path(block, self._project_root)
            if resolved is not None and resolved.exists():
                return str(resolved)
        return ""

    def _project_metadata_view(self) -> dict:
        if self._project_root is None or not self._project_root.exists():
            return {
                "name": "-",
                "description": "",
                "preview_image_path": "",
                "created_at": "-",
                "updated_at": "-",
                "author_name": "-",
                "author_email": "-",
            }
        storage = ProjectStorageService()
        metadata: dict = {}
        try:
            metadata = storage.load_project_metadata(self._project_root)
        except Exception:
            metadata = {}

        stats = self._project_root.stat()
        name = str(metadata.get("name", "") or self._project_root.name)
        description = str(metadata.get("description", "") or "")
        preview_image_path = str(metadata.get("preview_image_path", "") or "")
        if not preview_image_path:
            preview_image_path = self._project_preview_from_blocks()
        created_at = str(metadata.get("created_at", "") or self._format_fs_datetime(stats.st_ctime))
        updated_at = str(metadata.get("updated_at", "") or self._format_fs_datetime(stats.st_mtime))
        author_name = str(metadata.get("author_name", "") or "-")
        author_email = str(metadata.get("author_email", "") or "-")
        return {
            "name": name,
            "description": description,
            "preview_image_path": preview_image_path,
            "created_at": created_at,
            "updated_at": updated_at,
            "author_name": author_name,
            "author_email": author_email,
        }

    def _refresh_project_workspace(self) -> None:
        self._project_workspace.set_project_metadata(
            project_path=self._project_root,
            metadata=self._project_metadata_view(),
        )
        self._refresh_dashboard_stats()

    def _build_dashboard_stat_tiles(self) -> None:
        specs: list[tuple[str, str, str]] = [
            ("images", "IMAGES", "media_photo_plus.svg"),
            ("videos", "VIDEOS", "media_photo_video.svg"),
            ("characters", "CHARACTERS", "story_world_user_star.svg"),
            ("shots", "SHOTS", "project_clipboard_list.svg"),
            ("forms", "CHARACTER FORMS", "story_world_users.svg"),
            ("prompts", "PROMPTS", "edit_filter_2_spark.svg"),
            ("audio", "AUDIO", "story_world_message_circle_user.svg"),
            ("total", "TOTAL BLOCKS", "project_file_stack.svg"),
        ]
        columns = 4
        for index, (key, title, icon_name) in enumerate(specs):
            tile = InfoStatTileWidget(title, icon_name=icon_name, value=0, parent=self._dashboard_stats_grid_widget)
            row = index // columns
            col = index % columns
            self._dashboard_stats_grid.addWidget(tile, row, col)
            self._dashboard_stat_tiles[key] = tile
            self._dashboard_stats_grid.setColumnStretch(col, 1)

    def _project_stats_view(self) -> dict[str, int]:
        counts = {
            "images": 0,
            "videos": 0,
            "characters": 0,
            "shots": 0,
            "forms": 0,
            "prompts": 0,
            "audio": 0,
            "total": 0,
        }
        for block in self._blocks:
            if block.profile == "workspace_root":
                continue
            counts["total"] += 1
            if block.type == BlockType.IMAGE:
                counts["images"] += 1
            if block.type == BlockType.VIDEO:
                counts["videos"] += 1
            if block.type == BlockType.AUDIO:
                counts["audio"] += 1
            if block.type == BlockType.PROMPT:
                counts["prompts"] += 1
            if block.profile == "character":
                counts["characters"] += 1
            if block.profile == "character_form":
                counts["forms"] += 1
            if block.profile == "shot":
                counts["shots"] += 1
        return counts

    def _refresh_dashboard_stats(self) -> None:
        stats = self._project_stats_view()
        for key, tile in self._dashboard_stat_tiles.items():
            tile.set_value(stats.get(key, 0))

    def _current_theme_font_size(self) -> int:
        app = QApplication.instance()
        if app is None:
            return FONT_SIZE_DEFAULT
        tokens = app.property("sbc2_theme_tokens")
        if isinstance(tokens, dict):
            raw_px = tokens.get("font_size_px")
            if isinstance(raw_px, str) and raw_px.endswith("px"):
                try:
                    return int(raw_px[:-2])
                except ValueError:
                    return FONT_SIZE_DEFAULT
        return FONT_SIZE_DEFAULT

    def _apply_theme_from_settings(self, theme_name: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        apply_theme(app, theme_name=theme_name, font_size=self._current_theme_font_size())
        initialize_widget_primitives(self)
        if self._thumbnail_window is not None:
            initialize_widget_primitives(self._thumbnail_window)
        if self._media_carousel_window is not None:
            initialize_widget_primitives(self._media_carousel_window)
        if self._free_tree_window is not None:
            initialize_widget_primitives(self._free_tree_window)
        self._refresh_workspace_action_icons()
        self._sidebar.set_active(self._section_key)
        self._settings_workspace.set_current_theme(theme_name)

    def _create_new_project(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nouveau Projet", "Nom du projet:")
        if not accepted:
            return
        base_name = name.strip() or "NOUVEAU_PROJET"
        if base_name.lower().endswith(PROJECT_DIR_SUFFIX):
            base_name = base_name[: -len(PROJECT_DIR_SUFFIX)]
        safe_name = self._sanitize_project_folder_name(base_name)
        project_dir_name = self._with_project_dir_suffix(safe_name)
        project_path = self._storage_roots.projects_root / project_dir_name
        if project_path.exists():
            project_path = self._unique_project_path(project_dir_name)
        storage = ProjectStorageService()
        storage.create_project(project_path, base_name)
        self._seed_workspace_structure_defaults(project_path, storage=storage)
        metadata = storage.load_project_metadata(project_path)
        if not str(metadata.get("author_name", "") or "").strip():
            metadata["author_name"] = os.getenv("USER", "").strip() or os.getenv("USERNAME", "").strip()
            storage.save_project_metadata(project_path, metadata)
        self._load_project(project_path)

    def _open_project_from_dialog(self) -> None:
        projects = self._list_sbc_project_directories()
        if not projects:
            QMessageBox.information(
                self,
                "Ouvrir Projet",
                f"Aucun projet '{PROJECT_DIR_SUFFIX}' trouvé dans:\n{self._storage_roots.projects_root}",
            )
            return
        selected_name, accepted = QInputDialog.getItem(
            self,
            "Ouvrir Projet",
            "Projet:",
            [path.name for path in projects],
            0,
            False,
        )
        if not accepted or not selected_name:
            return
        selected_path = next((path for path in projects if path.name == selected_name), None)
        if selected_path is None:
            return
        self._load_project(selected_path)

    def _load_project(self, project_path: Path) -> None:
        resolved_path = project_path.expanduser().resolve()
        blocks = self._load_blocks_safely(resolved_path)
        if blocks is None:
            return
        blocks = self._ensure_workspace_structure_on_open(resolved_path, blocks)
        self._project_root = resolved_path
        self._blocks = blocks
        self._user_config.save_last_project_path(resolved_path)
        self._update_workspace_footer()
        self._refresh_project_workspace()
        self._close_secondary_windows()

    def _close_current_project(self) -> None:
        if self._project_root is None and not self._blocks:
            self._user_config.save_last_project_path(None)
            return
        self._project_root = None
        self._blocks = []
        self._user_config.save_last_project_path(None)
        self._update_workspace_footer()
        self._refresh_project_workspace()
        self._project_workspace.set_save_feedback("")
        self._close_secondary_windows()

    def _close_secondary_windows(self) -> None:
        if self._thumbnail_window is not None:
            self._thumbnail_window.close()
            self._thumbnail_window.deleteLater()
            self._thumbnail_window = None
        if self._media_carousel_window is not None:
            self._media_carousel_window.close()
            self._media_carousel_window.deleteLater()
            self._media_carousel_window = None
        if self._free_tree_window is not None:
            self._free_tree_window.close()
            self._free_tree_window.deleteLater()
            self._free_tree_window = None

    @staticmethod
    def _load_blocks_safely(project_path: Path) -> list[Block] | None:
        if not project_path.exists():
            return None
        try:
            blocks = ProjectStorageService().load_blocks(project_path)
        except Exception:
            return None
        return list(blocks)

    def _save_project_metadata_from_workspace(self, payload: dict) -> None:
        if self._project_root is None:
            return
        storage = ProjectStorageService()
        try:
            metadata = storage.load_project_metadata(self._project_root)
        except Exception:
            metadata = {}
        metadata.update(
            {
                "author_name": str(payload.get("author_name", "") or ""),
                "author_email": str(payload.get("author_email", "") or ""),
                "description": str(payload.get("description", "") or ""),
            }
        )
        try:
            storage.save_project_metadata(self._project_root, metadata)
        except Exception:
            self._project_workspace.set_save_feedback("Save failed")
            return
        self._refresh_project_workspace()
        self._project_workspace.set_save_feedback("Saved")

    def _select_project_visual_from_carousel(self) -> None:
        if self._project_root is None:
            return

        image_blocks = self._project_image_blocks()
        if not image_blocks:
            self._project_workspace.set_save_feedback("No image block available")
            return

        storage = ProjectStorageService()
        try:
            metadata = storage.load_project_metadata(self._project_root)
        except Exception:
            metadata = {}
        current_preview_path = str(metadata.get("preview_image_path", "") or "")
        initial_selected_block_id = self._find_block_id_for_preview_path(current_preview_path, image_blocks)

        dialog = ProjectVisualPickerDialog(
            blocks=image_blocks,
            project_root=self._project_root,
            initial_selected_block_id=initial_selected_block_id,
            parent=self,
        )
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        selected_block = dialog.selected_block()
        if selected_block is None:
            return

        selected_path = resolve_block_asset_path(selected_block, self._project_root)
        if selected_path is None or not selected_path.exists():
            self._project_workspace.set_save_feedback("Selected image not found")
            return

        metadata["preview_image_path"] = self._serialize_preview_path(selected_path)
        try:
            storage.save_project_metadata(self._project_root, metadata)
        except Exception:
            self._project_workspace.set_save_feedback("Save failed")
            return

        self._refresh_project_workspace()
        self._project_workspace.set_save_feedback("Project visual updated")

    def _project_image_blocks(self) -> list[Block]:
        if self._project_root is None:
            return []
        image_blocks: list[Block] = []
        for block in self._blocks:
            if block.type != BlockType.IMAGE:
                continue
            resolved = resolve_block_asset_path(block, self._project_root)
            if resolved is None or not resolved.exists():
                continue
            image_blocks.append(block)
        return image_blocks

    def _find_block_id_for_preview_path(self, preview_path: str, image_blocks: list[Block]) -> str | None:
        if self._project_root is None:
            return None
        text = str(preview_path or "").strip()
        if not text:
            return None
        target = Path(text).expanduser()
        if not target.is_absolute():
            target = (self._project_root / target).resolve()
        else:
            target = target.resolve()

        for block in image_blocks:
            resolved = resolve_block_asset_path(block, self._project_root)
            if resolved is None:
                continue
            if resolved.resolve() == target:
                return block.id
        return None

    def _serialize_preview_path(self, resolved_path: Path) -> str:
        if self._project_root is None:
            return str(resolved_path)
        try:
            return resolved_path.resolve().relative_to(self._project_root.resolve()).as_posix()
        except Exception:
            return str(resolved_path.resolve())

    @staticmethod
    def _sanitize_project_folder_name(name: str) -> str:
        sanitized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name)
        sanitized = sanitized.strip("_")
        return sanitized or f"project_{uuid4().hex[:6]}"

    def _unique_project_path(self, base_name: str) -> Path:
        stem = base_name.strip()
        if stem.lower().endswith(PROJECT_DIR_SUFFIX):
            stem = stem[: -len(PROJECT_DIR_SUFFIX)]
        stem = stem.strip("_") or f"project_{uuid4().hex[:6]}"
        counter = 1
        while True:
            candidate_name = self._with_project_dir_suffix(f"{stem}_{counter}")
            candidate = self._storage_roots.projects_root / candidate_name
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _with_project_dir_suffix(name: str) -> str:
        normalized = name.strip()
        if normalized.lower().endswith(PROJECT_DIR_SUFFIX):
            normalized = normalized[: -len(PROJECT_DIR_SUFFIX)]
        normalized = normalized.strip("_") or f"project_{uuid4().hex[:6]}"
        return f"{normalized}{PROJECT_DIR_SUFFIX}"

    def _list_sbc_project_directories(self) -> list[Path]:
        root = self._storage_roots.projects_root
        if not root.exists():
            return []
        projects = [
            candidate
            for candidate in root.iterdir()
            if candidate.is_dir() and candidate.name.lower().endswith(PROJECT_DIR_SUFFIX)
        ]
        return sorted(projects, key=lambda item: item.name.lower())

    def _open_thumbnail_window(self) -> None:
        if self._thumbnail_window is None:
            self._thumbnail_window = ThumbnailListWindow(blocks=self._blocks, project_root=self._project_root)
            self._thumbnail_window.destroyed.connect(lambda *_: setattr(self, "_thumbnail_window", None))
        self._thumbnail_window.show()
        self._thumbnail_window.raise_()
        self._thumbnail_window.activateWindow()

    def _open_media_carousel_window(self) -> None:
        if self._media_carousel_window is None:
            self._media_carousel_window = MediaCarouselWindow(blocks=self._blocks, project_root=self._project_root)
            self._media_carousel_window.destroyed.connect(lambda *_: setattr(self, "_media_carousel_window", None))
        else:
            self._media_carousel_window.set_blocks(self._blocks, project_root=self._project_root)
        self._media_carousel_window.show()
        self._media_carousel_window.raise_()
        self._media_carousel_window.activateWindow()

    def _open_free_tree_window(self) -> None:
        if self._free_tree_window is None:
            self._free_tree_window = FreeTreeWindow(
                blocks=self._blocks,
                persisted_tree=None,
                project_root=self._project_root,
            )
            self._free_tree_window.blocks_changed.connect(self._persist_project_blocks)
            self._free_tree_window.destroyed.connect(lambda *_: setattr(self, "_free_tree_window", None))
        self._free_tree_window.show()
        self._free_tree_window.raise_()
        self._free_tree_window.activateWindow()

    def _persist_project_blocks(self, blocks: object) -> None:
        if not isinstance(blocks, list):
            return
        normalized = [block for block in blocks if isinstance(block, Block)]
        self._blocks = normalized
        if self._project_root is None:
            return
        try:
            ProjectStorageService().save_blocks(self._project_root, self._blocks)
        except Exception:
            return

        if self._thumbnail_window is not None:
            self._thumbnail_window.set_blocks(self._blocks, project_root=self._project_root)
        if self._media_carousel_window is not None:
            self._media_carousel_window.set_blocks(self._blocks, project_root=self._project_root)
        self._refresh_project_workspace()

    @staticmethod
    def _create_workspace_root_block(
        *,
        block_id: str,
        name: str,
        domain: BlockDomain,
        role: str,
        description: str,
    ) -> Block:
        return Block(
            id=block_id,
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name=name,
            description=description,
            domain=domain,
            shared=False,
            tags=["workspace_root", role],
            content={"workspace_role": role},
            tree=FreeTree(),
            graph=FreeGraph(),
        )

    @staticmethod
    def _default_workspace_structure_blocks() -> list[Block]:
        project_root = MainWindow._create_workspace_root_block(
            block_id=PROJECT_ROOT_BLOCK_ID,
            name="PROJET",
            domain=BlockDomain.LIB,
            role="project_root",
            description="Project root container.",
        )
        characters_root = MainWindow._create_workspace_root_block(
            block_id=CHARACTERS_ROOT_BLOCK_ID,
            name="Characters Root",
            domain=BlockDomain.CHARACTERS,
            role="characters_root",
            description="Characters workspace root.",
        )
        story_root = MainWindow._create_workspace_root_block(
            block_id=STORY_ROOT_BLOCK_ID,
            name="Story Root",
            domain=BlockDomain.STORY,
            role="story_root",
            description="Story workspace root.",
        )
        lib_root = MainWindow._create_workspace_root_block(
            block_id=LIB_ROOT_BLOCK_ID,
            name="Library Root",
            domain=BlockDomain.LIB,
            role="library_root",
            description="Library workspace root.",
        )
        internal_lib_root = MainWindow._create_workspace_root_block(
            block_id=INTERNAL_LIB_ROOT_BLOCK_ID,
            name="INTERNALLIB",
            domain=BlockDomain.LIB,
            role="internal_lib",
            description="Internal import workspace root.",
        )
        internal_lib_empty = Block(
            id=INTERNAL_LIB_EMPTY_BLOCK_ID,
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
            description="Drop a resource thumbnail on INTERNALLIB to create a new block in this container.",
            domain=BlockDomain.LIB,
            shared=False,
            tags=["internal_lib", "empty", "dropzone"],
            content={"internal_lib": True, "drop_target": True},
        )
        internal_lib_root.contains = [internal_lib_empty.id]
        project_root.contains = [characters_root.id, story_root.id, lib_root.id, internal_lib_root.id]
        return [project_root, characters_root, story_root, lib_root, internal_lib_root, internal_lib_empty]

    @staticmethod
    def _workspace_root_role(block: Block) -> str:
        if block.type != BlockType.CONTAINER or block.profile != "workspace_root":
            return ""
        role = str(block.content.get("workspace_role", "") or "").strip().lower()
        if role:
            return role
        normalized_name = (block.name or "").strip().upper().replace(" ", "_")
        if block.id == PROJECT_ROOT_BLOCK_ID or normalized_name == "PROJET":
            return "project_root"
        if block.id == INTERNAL_LIB_ROOT_BLOCK_ID:
            return "internal_lib"
        if normalized_name in {"INTERNALLIB", "INTERNAL_LIB"}:
            return "internal_lib"
        if block.id == CHARACTERS_ROOT_BLOCK_ID or "CHAR" in normalized_name:
            return "characters_root"
        if block.id == STORY_ROOT_BLOCK_ID or "STORY" in normalized_name:
            return "story_root"
        if block.id == LIB_ROOT_BLOCK_ID or ("LIB" in normalized_name and "INTERNAL" not in normalized_name):
            return "library_root"
        return ""

    @staticmethod
    def _replace_ids_in_text(value: str, mapping: dict[str, str]) -> str:
        updated = value
        for old, new in mapping.items():
            updated = updated.replace(old, new)
        return updated

    def _migrate_legacy_workspace_aliases(
        self,
        project_path: Path,
        blocks: list[Block],
    ) -> tuple[list[Block], bool]:
        id_mapping = {
            "blk_virtual_root": INTERNAL_LIB_ROOT_BLOCK_ID,
            "blk_virtual_empty": INTERNAL_LIB_EMPTY_BLOCK_ID,
        }
        if not any(block.id in id_mapping for block in blocks):
            return blocks, False

        changed = False
        working = list(blocks)
        by_id = {block.id: block for block in working}
        remove_ids: set[str] = set()

        for legacy_id, new_id in id_mapping.items():
            legacy = by_id.get(legacy_id)
            if legacy is None:
                continue
            existing = by_id.get(new_id)
            if existing is not None and existing is not legacy:
                for child_id in legacy.contains:
                    if child_id not in existing.contains:
                        existing.contains.append(child_id)
                remove_ids.add(legacy_id)
                changed = True
                continue
            legacy.id = new_id
            changed = True

        if remove_ids:
            working = [block for block in working if block.id not in remove_ids]

        for block in working:
            original_contains = list(block.contains)
            block.contains = [id_mapping.get(child_id, child_id) for child_id in block.contains if child_id not in remove_ids]
            block.contains = self._dedupe_ids(block.contains)
            if block.contains != original_contains:
                changed = True

            for input_connection in block.inputs:
                mapped_source = id_mapping.get(input_connection.source_block_id, input_connection.source_block_id)
                if mapped_source != input_connection.source_block_id:
                    input_connection.source_block_id = mapped_source
                    changed = True

            if block.tree is not None:
                for node in block.tree.nodes.values():
                    if node.block_id in remove_ids:
                        node.block_id = None
                        changed = True
                    elif node.block_id in id_mapping:
                        node.block_id = id_mapping[node.block_id]
                        changed = True

            if block.graph is not None:
                for node in block.graph.nodes.values():
                    mapped = id_mapping.get(node.block_id, node.block_id)
                    if mapped != node.block_id:
                        node.block_id = mapped
                        changed = True

        for block in working:
            if block.id == INTERNAL_LIB_ROOT_BLOCK_ID:
                if block.name != "INTERNALLIB":
                    block.name = "INTERNALLIB"
                    changed = True
                if block.profile != "workspace_root":
                    block.profile = "workspace_root"
                    changed = True
                if block.domain != BlockDomain.LIB:
                    block.domain = BlockDomain.LIB
                    changed = True
                if block.content.get("workspace_role") != "internal_lib":
                    block.content["workspace_role"] = "internal_lib"
                    changed = True
            if block.id == INTERNAL_LIB_EMPTY_BLOCK_ID:
                if block.profile != "internal_lib_empty":
                    block.profile = "internal_lib_empty"
                    changed = True
                if not block.content.get("internal_lib"):
                    block.content["internal_lib"] = True
                    changed = True
                if not block.content.get("drop_target"):
                    block.content["drop_target"] = True
                    changed = True

        if not changed:
            return working, False

        try:
            ui_state = ProjectStorageService().load_ui_state(project_path)
            tree_key = "project_free_tree"
            payload = ui_state.get(tree_key)
            if isinstance(payload, dict):
                nodes = payload.get("nodes")
                if isinstance(nodes, dict):
                    for node_data in nodes.values():
                        if not isinstance(node_data, dict):
                            continue
                        block_id = node_data.get("block_id")
                        if isinstance(block_id, str) and block_id in id_mapping:
                            node_data["block_id"] = id_mapping[block_id]
                        node_name = node_data.get("name")
                        if (
                            isinstance(node_name, str)
                            and node_data.get("block_id") == INTERNAL_LIB_ROOT_BLOCK_ID
                            and node_name.strip().upper() == "VIRTUAL"
                        ):
                            node_data["name"] = "INTERNALLIB"
                    renamed_nodes: dict[str, dict] = {}
                    for node_id, node_data in nodes.items():
                        if not isinstance(node_id, str):
                            continue
                        new_node_id = self._replace_ids_in_text(node_id, id_mapping)
                        if isinstance(node_data, dict):
                            node_data["id"] = self._replace_ids_in_text(str(node_data.get("id", new_node_id)), id_mapping)
                            children = node_data.get("children")
                            if isinstance(children, list):
                                node_data["children"] = [
                                    self._replace_ids_in_text(str(child_id), id_mapping) for child_id in children
                                ]
                        renamed_nodes[new_node_id] = node_data
                    payload["nodes"] = renamed_nodes
                root_ids = payload.get("root_ids")
                if isinstance(root_ids, list):
                    payload["root_ids"] = [self._replace_ids_in_text(str(node_id), id_mapping) for node_id in root_ids]
                ui_state[tree_key] = payload
                ProjectStorageService().save_ui_state(project_path, ui_state)
        except Exception:
            pass

        return working, True

    @staticmethod
    def _dedupe_ids(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _seed_workspace_structure_defaults(
        self,
        project_path: Path,
        *,
        storage: ProjectStorageService | None = None,
    ) -> None:
        service = storage or ProjectStorageService()
        try:
            existing = service.load_blocks(project_path)
        except Exception:
            existing = []
        if existing:
            return
        service.save_blocks(project_path, self._default_workspace_structure_blocks())

    def _ensure_workspace_structure_on_open(self, project_path: Path, blocks: list[Block]) -> list[Block]:
        if not blocks:
            return blocks

        updated_blocks, migrated_legacy = self._migrate_legacy_workspace_aliases(project_path, list(blocks))
        path_migration_changed = self._migrate_legacy_project_tree_to_block_paths(project_path, updated_blocks)
        by_id = {block.id: block for block in updated_blocks}
        changed = migrated_legacy or path_migration_changed

        def ensure_role(block: Block, role: str) -> None:
            nonlocal changed
            if block.content.get("workspace_role") != role:
                block.content["workspace_role"] = role
                changed = True

        def resolve_or_create_root(
            *,
            role: str,
            block_id: str,
            name: str,
            domain: BlockDomain,
            description: str,
            aliases: set[str] | None = None,
        ) -> Block:
            nonlocal changed
            aliases = aliases or set()
            candidate: Block | None = None
            for block in updated_blocks:
                if block.type != BlockType.CONTAINER or block.profile != "workspace_root":
                    continue
                block_role = self._workspace_root_role(block)
                if block_role == role:
                    candidate = block
                    break
                normalized_name = (block.name or "").strip().upper().replace(" ", "_")
                if block.id == block_id or block.id in aliases or normalized_name in aliases:
                    candidate = block
                    break
            if candidate is None:
                candidate = self._create_workspace_root_block(
                    block_id=block_id,
                    name=name,
                    domain=domain,
                    role=role,
                    description=description,
                )
                updated_blocks.append(candidate)
                by_id[candidate.id] = candidate
                changed = True

            ensure_role(candidate, role)
            if candidate.name != name:
                candidate.name = name
                changed = True
            if candidate.domain != domain:
                candidate.domain = domain
                changed = True
            if candidate.profile != "workspace_root":
                candidate.profile = "workspace_root"
                changed = True
            if candidate.type != BlockType.CONTAINER:
                candidate.type = BlockType.CONTAINER
                changed = True
            if candidate.tree is None:
                candidate.tree = FreeTree()
                changed = True
            if candidate.graph is None:
                candidate.graph = FreeGraph()
                changed = True
            candidate.contains = self._dedupe_ids(list(candidate.contains))
            return candidate

        project_root = resolve_or_create_root(
            role="project_root",
            block_id=PROJECT_ROOT_BLOCK_ID,
            name="PROJET",
            domain=BlockDomain.LIB,
            description="Project root container.",
            aliases={"PROJET"},
        )
        characters_root = resolve_or_create_root(
            role="characters_root",
            block_id=CHARACTERS_ROOT_BLOCK_ID,
            name="Characters Root",
            domain=BlockDomain.CHARACTERS,
            description="Characters workspace root.",
            aliases={"CHARACTERS_ROOT", "CHARACTERSROOT"},
        )
        story_root = resolve_or_create_root(
            role="story_root",
            block_id=STORY_ROOT_BLOCK_ID,
            name="Story Root",
            domain=BlockDomain.STORY,
            description="Story workspace root.",
            aliases={"STORY_ROOT", "STORYROOT"},
        )
        lib_root = resolve_or_create_root(
            role="library_root",
            block_id=LIB_ROOT_BLOCK_ID,
            name="Library Root",
            domain=BlockDomain.LIB,
            description="Library workspace root.",
            aliases={"LIB_ROOT", "LIBRARY_ROOT", "LIBRARYROOT"},
        )
        internal_lib_root = resolve_or_create_root(
            role="internal_lib",
            block_id=INTERNAL_LIB_ROOT_BLOCK_ID,
            name="INTERNALLIB",
            domain=BlockDomain.LIB,
            description="Internal import workspace root.",
            aliases={
                "INTERNAL_LIB",
                "INTERNALLIB",
            },
        )

        internal_empty = by_id.get(INTERNAL_LIB_EMPTY_BLOCK_ID)
        if internal_empty is None:
            for child_id in internal_lib_root.contains:
                child = by_id.get(child_id)
                if child is not None and child.type == BlockType.EMPTY:
                    internal_empty = child
                    break
        if internal_empty is None:
            internal_empty = Block(
                id=INTERNAL_LIB_EMPTY_BLOCK_ID,
                type=BlockType.EMPTY,
                profile="internal_lib_empty",
                name="Drop Resources Here",
                description="Drop a resource thumbnail on INTERNALLIB to create a new block in this container.",
                domain=BlockDomain.LIB,
                shared=False,
                tags=["internal_lib", "empty", "dropzone"],
                content={"internal_lib": True, "drop_target": True},
            )
            updated_blocks.append(internal_empty)
            by_id[internal_empty.id] = internal_empty
            changed = True
        else:
            if not bool(internal_empty.content.get("drop_target")):
                internal_empty.content["drop_target"] = True
                changed = True
            if not bool(internal_empty.content.get("internal_lib")):
                internal_empty.content["internal_lib"] = True
                changed = True
            if not internal_empty.name.strip():
                internal_empty.name = "Drop Resources Here"
                changed = True
            expected_description = "Drop a resource thumbnail on INTERNALLIB to create a new block in this container."
            if internal_empty.description != expected_description:
                internal_empty.description = expected_description
                changed = True

        if internal_empty.id not in internal_lib_root.contains:
            internal_lib_root.contains.append(internal_empty.id)
            changed = True
        internal_lib_root.contains = self._dedupe_ids(internal_lib_root.contains)

        workspace_root_ids = {
            block.id
            for block in updated_blocks
            if block.type == BlockType.CONTAINER and block.profile == "workspace_root"
        }
        expected_children = [
            characters_root.id,
            story_root.id,
            lib_root.id,
            internal_lib_root.id,
        ]
        for child_id in expected_children:
            if child_id not in project_root.contains:
                project_root.contains.append(child_id)
                changed = True
        for child_id in sorted(workspace_root_ids):
            if child_id == project_root.id:
                continue
            if child_id not in project_root.contains:
                project_root.contains.append(child_id)
                changed = True
        project_root.contains = self._dedupe_ids(project_root.contains)

        for block in updated_blocks:
            if block.type != BlockType.CONTAINER:
                continue
            original = list(block.contains)
            filtered: list[str] = []
            for child_id in original:
                if child_id == project_root.id:
                    continue
                if block.id != project_root.id and child_id in workspace_root_ids:
                    continue
                filtered.append(child_id)
            deduped = self._dedupe_ids(filtered)
            if deduped != original:
                block.contains = deduped
                changed = True

        if changed:
            try:
                ProjectStorageService().save_blocks(project_path, updated_blocks)
            except Exception:
                return updated_blocks
        return updated_blocks

    def _migrate_legacy_project_tree_to_block_paths(self, project_path: Path, blocks: list[Block]) -> bool:
        persisted_tree = self._load_legacy_project_free_tree(project_path)
        if persisted_tree is None:
            return False

        controller = FreeTreeWorkspaceController()
        controller.set_blocks(blocks)
        before = {
            block.id: dict(block.container_paths)
            for block in blocks
        }
        controller.apply_persisted_tree(persisted_tree)
        after = {
            block.id: dict(block.container_paths)
            for block in blocks
        }
        changed = before != after
        if not changed:
            return False

        try:
            ui_state = ProjectStorageService().load_ui_state(project_path)
            if "project_free_tree" in ui_state:
                ui_state.pop("project_free_tree", None)
                ProjectStorageService().save_ui_state(project_path, ui_state)
        except Exception:
            pass
        return True

    def _load_legacy_project_free_tree(self, project_path: Path) -> FreeTree | None:
        try:
            ui_state = ProjectStorageService().load_ui_state(project_path)
        except Exception:
            return None
        payload = ui_state.get("project_free_tree")
        if not isinstance(payload, dict):
            return None
        return self._legacy_tree_from_payload(payload)

    @staticmethod
    def _legacy_tree_from_payload(data: dict) -> FreeTree | None:
        nodes = {
            node_id: FreeTreeNode(
                id=str(node_data.get("id", node_id)),
                kind=str(node_data.get("kind", "folder")),
                name=str(node_data.get("name", "")),
                block_id=(str(node_data.get("block_id")) if node_data.get("block_id") is not None else None),
                children=[str(child_id) for child_id in node_data.get("children", [])],
            )
            for node_id, node_data in data.get("nodes", {}).items()
            if isinstance(node_data, dict)
        }
        if not nodes:
            return None
        referenced_ids = {
            child_id
            for node in nodes.values()
            for child_id in node.children
            if child_id in nodes
        }
        root_ids = [
            str(node_id)
            for node_id in data.get("root_ids", [])
            if str(node_id) in nodes and str(node_id) not in referenced_ids
        ]
        for node_id in nodes:
            if node_id in root_ids:
                continue
            if node_id not in referenced_ids:
                root_ids.append(node_id)
        return FreeTree(root_ids=root_ids, nodes=nodes)

    def _create_open_thumbnail_button(
        self,
        text: str,
        *,
        style_property: str | None = None,
        icon_name: str | None = None,
    ) -> QPushButton:
        return self._create_workspace_button(
            text,
            on_click=self._open_thumbnail_window,
            style_property=style_property,
            icon_name=icon_name,
        )

    def _create_open_free_tree_button(
        self,
        text: str,
        *,
        style_property: str | None = None,
        icon_name: str | None = None,
    ) -> QPushButton:
        return self._create_workspace_button(
            text,
            on_click=self._open_free_tree_window,
            style_property=style_property,
            icon_name=icon_name,
        )

    def _create_workspace_button(
        self,
        text: str,
        *,
        on_click,
        style_property: str | None = None,
        icon_name: str | None = None,
    ) -> QPushButton:
        button = QPushButton(text, self._workspace_actions_frame)
        button.setProperty("buttonStyleKey", style_property or "")
        button.setProperty("iconName", icon_name or "")
        if style_property:
            button.setProperty(style_property, True)
        if icon_name:
            icon_color = self._button_icon_color(style_property)
            button.setIcon(self._icon_for(icon_name, icon_color))
            button.setIconSize(QSize(16, 16))
        button.clicked.connect(on_click)
        return button

    def _button_icon_color(self, style_property: str | None) -> str:
        tokens = active_theme_tokens_ref()
        if style_property in {"primary", "accent"}:
            return tokens.get("on_primary_fixed", "#000000")
        return tokens.get("on_surface", "#f9f9fd")

    def _refresh_workspace_action_icons(self) -> None:
        self._action_icon_cache.clear()
        for button in self._workspace_action_buttons:
            icon_name = button.property("iconName")
            if not isinstance(icon_name, str) or not icon_name:
                continue
            style_property = str(button.property("buttonStyleKey") or "")
            button.setIcon(self._icon_for(icon_name, self._button_icon_color(style_property)))

    def _icon_for(self, filename: str, color_hex: str) -> QIcon:
        cache_key = (filename, color_hex)
        cached = self._action_icon_cache.get(cache_key)
        if cached is not None:
            return cached

        path = self._icons_dir / filename
        if not path.exists():
            return QIcon()

        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QIcon()

        icon = QIcon()
        tint = QColor(color_hex)
        for size in (16, 18, 20, 24):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            icon.addPixmap(pixmap)

        self._action_icon_cache[cache_key] = icon
        return icon

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        # Ensure all auxiliary windows are closed when main shell is closed.
        self._close_secondary_windows()

        app = QApplication.instance()
        if app is not None:
            for widget in list(app.topLevelWidgets()):
                if widget is self:
                    continue
                widget.close()
            app.quit()

        super().closeEvent(event)

def run_main_window() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    icon = _load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    theme_name = os.getenv("SBC2_THEME", "dark")
    try:
        font_size = int(os.getenv("SBC2_FONT_SIZE", str(FONT_SIZE_DEFAULT)))
    except ValueError:
        font_size = FONT_SIZE_DEFAULT
    apply_theme(app, theme_name=theme_name, font_size=font_size)
    window = MainWindow()
    install_widget_primitives(app)
    window.show()
    app.exec()
