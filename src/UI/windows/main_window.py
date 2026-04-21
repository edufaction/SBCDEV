from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from application import (
    BlockWorkspaceService,
    CharacterWorkspaceController,
    ContainerContentService,
    GraphWorkspaceController,
    ProjectLifecycleController,
    ProjectStructureService,
    ProjectWindowController,
    ProjectWorkspaceController,
    ProjectSession,
    SecondaryWindowsController,
    StoryWorkspaceController,
    StoryWorkspaceService,
    WindowNavigationController,
)
from application.workspaces import CharacterWorkspaceService, ProjectWorkspaceService, SettingsWorkspaceService
from domain import Block, BlockDomain, FreeGraph
from infrastructure.storage import ProjectStorageService, UserConfigService, resolve_storage_roots
from UI.Widgets import ProjectWorkspaceWidget, SettingsWorkspaceWidget, SidebarMenu
from UI.Frames import CharacterWorkspacePanel, LibraryWorkspacePanel, ProjectWorkspacePanel, SettingsWorkspacePanel, StoryWorkspacePanel
from UI.themes import (
    FONT_SIZE_DEFAULT,
    active_theme_name,
    apply_theme,
    initialize_widget_primitives,
    install_widget_primitives,
)
from UI.windows.free_tree_window import FreeTreeWindow
from UI.windows.media_carousel_window import MediaCarouselWindow
from UI.windows.project_visual_picker_dialog import ProjectVisualPickerDialog
from UI.windows.workspace_action_buttons import WorkspaceActionButtonFactory
from UI.windows.thumbnail_list_window import ThumbnailListWindow
from UI.windows.workspace_shell_builder import WorkspaceShellBuilder
from UI.windows.window_helpers import (
    load_app_icon as _load_app_icon,
    resolve_app_icon_path as _resolve_app_icon_path,
    resolve_data_project_dir as _resolve_data_project_dir,
)

class MainWindow(QMainWindow):
    """Primary application shell coordinating workspaces and secondary windows.

    MainWindow wires dashboard, tools, settings, and project interactions.
    It also owns project lifecycle actions: create, open, close, metadata save,
    and synchronization of child windows using the current block state.
    """

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
        self._project_structure_service = ProjectStructureService()

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

        self._session = ProjectSession(project_root=resolved_project_root, blocks=resolved_blocks)
        self._blocks = self._session.blocks
        self._project_root = self._session.project_root
        self._thumbnail_window: ThumbnailListWindow | None = None
        self._media_carousel_window: MediaCarouselWindow | None = None
        self._free_tree_window: FreeTreeWindow | None = None
        self._project_workspace_service = ProjectWorkspaceService()
        self._block_workspace_service = BlockWorkspaceService()
        self._container_content_service = ContainerContentService()
        self._character_workspace_service = CharacterWorkspaceService()
        self._settings_workspace_service = SettingsWorkspaceService()
        self._story_workspace_service = StoryWorkspaceService()
        self._storage_roots = resolve_storage_roots()
        configured_projects_root = self._user_config.load_projects_root_path()
        if configured_projects_root is not None:
            self._update_projects_root(configured_projects_root, persist=False)
        self._icons_dir = Path(__file__).resolve().parents[2] / "icons"
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
        self._project_workspace = ProjectWorkspaceWidget(self)
        self._project_workspace_panel = ProjectWorkspacePanel(self._project_workspace, self)
        self._character_workspace_panel = CharacterWorkspacePanel(self)
        self._character_workspace_panel.relative_path_changed.connect(self._on_character_block_relative_path_changed)
        self._character_workspace_panel.graph_link_create_requested.connect(self._on_graph_link_create_requested)
        self._character_workspace_panel.graph_link_delete_requested.connect(self._on_graph_link_delete_requested)
        self._character_workspace_panel.graph_block_move_requested.connect(self._on_graph_block_move_requested)
        self._character_workspace_panel.graph_layout_initialize_requested.connect(
            self._on_graph_layout_initialize_requested
        )
        self._character_workspace_panel.graph_files_drop_requested.connect(self._on_graph_files_drop_requested)
        self._story_workspace_panel = StoryWorkspacePanel(self)
        self._story_workspace_panel.relative_path_changed.connect(self._on_story_block_relative_path_changed)
        self._story_workspace_panel.graph_link_create_requested.connect(self._on_graph_link_create_requested)
        self._story_workspace_panel.graph_link_delete_requested.connect(self._on_graph_link_delete_requested)
        self._story_workspace_panel.graph_block_move_requested.connect(self._on_graph_block_move_requested)
        self._story_workspace_panel.graph_layout_initialize_requested.connect(
            self._on_graph_layout_initialize_requested
        )
        self._story_workspace_panel.graph_files_drop_requested.connect(self._on_graph_files_drop_requested)
        self._library_workspace_panel = LibraryWorkspacePanel(self)
        self._settings_workspace_panel = SettingsWorkspacePanel(self._settings_workspace, self)
        self._character_workspace_controller = CharacterWorkspaceController(
            panel=self._character_workspace_panel,
            session=self._session,
            content_service=self._container_content_service,
            block_workspace_service=self._block_workspace_service,
            character_workspace_service=self._character_workspace_service,
            persist_blocks=self._persist_project_blocks,
        )
        self._story_workspace_controller = StoryWorkspaceController(
            panel=self._story_workspace_panel,
            session=self._session,
            content_service=self._container_content_service,
            block_workspace_service=self._block_workspace_service,
            story_workspace_service=self._story_workspace_service,
            persist_blocks=self._persist_project_blocks,
        )
        self._graph_workspace_controller = GraphWorkspaceController(
            session=self._session,
            persist_blocks=self._persist_project_blocks,
            set_feedback=self._set_workspace_link_feedback,
        )
        self._project_window_controller = ProjectWindowController(
            session=self._session,
            project_workspace_service=self._project_workspace_service,
            project_workspace_panel=self._project_workspace_panel,
            character_workspace_panel=self._character_workspace_panel,
            story_workspace_panel=self._story_workspace_panel,
            library_workspace_panel=self._library_workspace_panel,
            update_workspace_footer=self._update_workspace_footer,
            close_secondary_windows=self._close_secondary_windows,
            save_last_project_path=self._user_config.save_last_project_path,
            ensure_workspace_structure_on_open=self._project_structure_service.ensure_workspace_structure_on_open,
            load_blocks_safely=self._load_blocks_safely,
            refresh_dashboard_stats=self._refresh_dashboard_stats,
            get_user_libraries_root=lambda: self._storage_roots.user_libraries_root,
            get_application_libraries_root=lambda: self._storage_roots.application_libraries_root,
        )
        self._project_workspace_actions_controller = ProjectWorkspaceController(
            session=self._session,
            project_workspace_service=self._project_workspace_service,
            refresh_workspace=self._refresh_project_workspace,
            set_feedback=self._project_workspace_panel.set_save_feedback,
            visual_picker_dialog_cls=ProjectVisualPickerDialog,
            dialog_parent=self,
        )
        self._secondary_windows_controller = SecondaryWindowsController(
            thumbnail_window_cls=ThumbnailListWindow,
            media_carousel_window_cls=MediaCarouselWindow,
            free_tree_window_cls=FreeTreeWindow,
            persist_blocks=self._persist_project_blocks,
            parent=self,
        )
        self._project_lifecycle_controller = ProjectLifecycleController(
            project_window_controller=self._project_window_controller,
            settings_workspace_service=self._settings_workspace_service,
            get_storage_roots=lambda: self._storage_roots,
            set_storage_roots=self._set_storage_roots_runtime,
            save_projects_root_path=self._user_config.save_projects_root_path,
            set_storage_paths=self._apply_storage_paths_to_settings_panel,
            prompt_new_project_name=lambda: QInputDialog.getText(self, "Nouveau Projet", "Nom du projet:"),
            prompt_project_choice=lambda items: QInputDialog.getItem(self, "Open Project", "Project:", items, 0, False),
            prompt_projects_root=lambda current_root: QFileDialog.getExistingDirectory(
                self,
                "Select Projects Folder",
                current_root,
                QFileDialog.ShowDirsOnly,
            ),
            show_open_project_info=lambda title, message: QMessageBox.information(self, title, message),
            seed_workspace_structure_defaults=self._project_structure_service.seed_workspace_structure_defaults,
        )
        self._character_workspace_panel.block_update_requested.connect(self._character_workspace_controller.update_block)
        self._character_workspace_panel.note_create_requested.connect(self._character_workspace_controller.create_note)
        self._character_workspace_panel.block_files_add_requested.connect(self._character_workspace_controller.import_blocks)
        self._character_workspace_panel.placeholder_block_create_requested.connect(self._character_workspace_controller.create_placeholder)
        self._story_workspace_panel.block_update_requested.connect(self._story_workspace_controller.update_block)
        self._story_workspace_panel.note_create_requested.connect(self._story_workspace_controller.create_note)
        self._character_workspace_panel.character_create_requested.connect(
            self._character_workspace_controller.create_character
        )
        self._character_workspace_panel.character_update_requested.connect(
            self._character_workspace_controller.update_character
        )
        self._settings_workspace_panel.theme_changed.connect(self._apply_theme_from_settings)
        self._settings_workspace_panel.set_current_theme(active_theme_name())
        self._settings_workspace_panel.set_storage_paths(
            projects_root=self._storage_roots.projects_root,
            user_libraries_root=self._storage_roots.user_libraries_root,
            application_libraries_root=self._storage_roots.application_libraries_root,
        )
        self._project_workspace_panel.new_project_requested.connect(self._create_new_project)
        self._project_workspace_panel.open_project_requested.connect(self._open_project_from_dialog)
        self._project_workspace_panel.close_project_requested.connect(self._close_current_project)
        self._project_workspace_panel.project_tree_requested.connect(self._open_free_tree_window)
        self._project_workspace_panel.select_visual_requested.connect(self._select_project_visual_from_carousel)
        self._project_workspace_panel.save_requested.connect(self._save_project_metadata_from_workspace)
        # Public aliases kept for compatibility with existing tests/callers.
        self._new_project_button = self._project_workspace._new_project_button
        self._open_project_button = self._project_workspace._open_project_button
        self._close_project_button = self._project_workspace._close_project_button
        self._open_free_tree_button = self._project_workspace._project_tree_button
        self._select_project_visual_button = self._project_workspace._select_visual_button
        self._workspace_action_button_factory = WorkspaceActionButtonFactory(
            parent=self._workspace_actions_frame,
            icons_dir=self._icons_dir,
        )
        action_buttons = self._workspace_action_button_factory.build(
            open_thumbnail_handler=self._open_thumbnail_window,
            open_media_carousel_handler=self._open_media_carousel_window,
        )
        self._open_thumbnail_buttons = action_buttons.open_thumbnail_buttons
        self._open_thumbnail_button = self._open_thumbnail_buttons[0]
        self._open_thumbnail_button_primary = self._open_thumbnail_buttons[1]
        self._open_thumbnail_button_accent = self._open_thumbnail_buttons[2]
        self._open_thumbnail_button_ghost = self._open_thumbnail_buttons[3]
        self._open_thumbnail_button_magic = self._open_thumbnail_buttons[4]
        self._open_media_carousel_button = action_buttons.open_media_carousel_button
        self._workspace_action_buttons = action_buttons.all_buttons

        shell_parts = WorkspaceShellBuilder(self).build(
            workspace_header=self._workspace_header,
            workspace_footer=self._workspace_footer,
            workspace_actions_frame=self._workspace_actions_frame,
            workspace_action_buttons=self._workspace_action_buttons,
            project_workspace_panel=self._project_workspace_panel,
            library_workspace_panel=self._library_workspace_panel,
            character_workspace_panel=self._character_workspace_panel,
            settings_workspace_panel=self._settings_workspace_panel,
            story_workspace_panel=self._story_workspace_panel,
        )
        self._dashboard_stats_frame = shell_parts.dashboard_stats_frame
        self._dashboard_stats_title = shell_parts.dashboard_stats_title
        self._dashboard_stats_grid_widget = shell_parts.dashboard_stats_grid_widget
        self._dashboard_stats_grid = shell_parts.dashboard_stats_grid
        self._dashboard_stat_tiles = shell_parts.dashboard_stat_tiles
        self._workspace_dashboard_page = shell_parts.workspace_dashboard_page
        self._workspace_asset_library_page = shell_parts.workspace_asset_library_page
        self._workspace_character_studio_page = shell_parts.workspace_character_studio_page
        self._workspace_ai_presets_page = shell_parts.workspace_ai_presets_page
        self._workspace_tools_page = shell_parts.workspace_tools_page
        self._workspace_settings_page = shell_parts.workspace_settings_page
        self._workspace_story_page = shell_parts.workspace_story_page
        self._workspace_project_page = shell_parts.workspace_project_page
        self._workspace_support_page = shell_parts.workspace_support_page
        self._ai_presets_empty_state = shell_parts.ai_presets_empty_state
        self._projects_page_empty_state = shell_parts.projects_page_empty_state
        self._support_empty_state = shell_parts.support_empty_state
        self._workspace_stack = shell_parts.workspace_stack
        self._window_navigation_controller = WindowNavigationController(
            workspace_stack=self._workspace_stack,
            workspace_header=self._workspace_header,
            sidebar=self._sidebar,
            set_section_key=lambda key: setattr(self, "_section_key", key),
            default_page=self._workspace_dashboard_page,
            pages_by_key={
                "dashboard": self._workspace_dashboard_page,
                "asset_library": self._workspace_asset_library_page,
                "character_studio": self._workspace_character_studio_page,
                "ai_presets": self._workspace_ai_presets_page,
                "tools": self._workspace_tools_page,
                "settings": self._workspace_settings_page,
                "story_planner": self._workspace_story_page,
                "project": self._workspace_project_page,
                "support": self._workspace_support_page,
            },
            header_overrides={"project": "PROJETS"},
        )

        root = QWidget(self)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._sidebar, 0)
        root_layout.addWidget(shell_parts.workspace_panel, 1)
        self.setCentralWidget(root)
        self._update_workspace_footer()
        self._refresh_project_workspace()
        initialize_widget_primitives(self)

    def _on_sidebar_navigation(self, key: str) -> None:
        self._window_navigation_controller.navigate(key)

    def _navigate_to_workspace_section(self, key: str) -> None:
        self._window_navigation_controller.navigate_to_section(key)

    def _update_workspace_footer(self) -> None:
        project_root = self._session.project_root
        if project_root is None:
            self._workspace_footer.setText("Application is running")
            return
        self._workspace_footer.setText(f"Project: {project_root}")

    def _set_storage_roots_runtime(self, storage_roots) -> None:
        self._storage_roots = storage_roots

    def _apply_storage_paths_to_settings_panel(self, storage_roots) -> None:
        settings_panel = getattr(self, "_settings_workspace_panel", None)
        if settings_panel is not None:
            settings_panel.set_storage_paths(
                projects_root=storage_roots.projects_root,
                user_libraries_root=storage_roots.user_libraries_root,
                application_libraries_root=storage_roots.application_libraries_root,
            )

    def _refresh_project_workspace(self) -> None:
        self._project_window_controller.refresh_workspace()

    def _on_character_block_relative_path_changed(self, block_id: str, container_id: str, relative_path: str) -> None:
        if self._project_root is None:
            self._character_workspace_panel.set_message("Open a project first.")
            return
        changed = self._character_workspace_panel.set_block_relative_path(
            block_id=block_id,
            container_id=container_id,
            relative_path=relative_path,
        )
        if not changed:
            self._character_workspace_panel.set_message("No path change applied.")
            return
        self._persist_project_blocks(self._blocks)
        self._character_workspace_panel.set_message("Character tree path updated.")

    def _on_story_block_relative_path_changed(self, block_id: str, container_id: str, relative_path: str) -> None:
        if self._project_root is None:
            self._story_workspace_panel.set_message("Open a project first.")
            return
        changed = self._story_workspace_panel.set_block_relative_path(
            block_id=block_id,
            container_id=container_id,
            relative_path=relative_path,
        )
        if not changed:
            self._story_workspace_panel.set_message("No path change applied.")
            return
        self._persist_project_blocks(self._blocks)
        self._story_workspace_panel.set_message("Story tree path updated.")

    def _on_graph_link_create_requested(
        self,
        container_id: str,
        source_block_id: str,
        target_block_id: str,
        target_port: str,
        name: str,
    ) -> None:
        self._graph_workspace_controller.create_link(
            container_id=container_id,
            source_block_id=source_block_id,
            target_block_id=target_block_id,
            target_port=target_port,
            name=name,
        )

    def _on_graph_link_delete_requested(
        self,
        container_id: str,
        source_block_id: str,
        target_block_id: str,
        target_port: str,
        name: str,
    ) -> None:
        self._graph_workspace_controller.delete_link(
            container_id=container_id,
            source_block_id=source_block_id,
            target_block_id=target_block_id,
            target_port=target_port,
            name=name,
        )

    def _on_graph_block_move_requested(
        self,
        container_id: str,
        block_id: str,
        x: float,
        y: float,
    ) -> None:
        self._graph_workspace_controller.move_block(container_id=container_id, block_id=block_id, x=x, y=y)

    def _on_graph_layout_initialize_requested(self, container_id: str, positions: object) -> None:
        self._graph_workspace_controller.initialize_layout(container_id=container_id, positions=positions)

    def _sync_runtime_state_from_session(self) -> None:
        self._blocks = self._session.blocks
        self._project_root = self._session.project_root

    def _sync_secondary_window_refs(self) -> None:
        self._thumbnail_window = self._secondary_windows_controller.thumbnail_window
        self._media_carousel_window = self._secondary_windows_controller.media_carousel_window
        self._free_tree_window = self._secondary_windows_controller.free_tree_window

    def _workspace_controller_for_domain(self, domain: BlockDomain):
        if domain == BlockDomain.CHARACTERS:
            return self._character_workspace_controller
        return self._story_workspace_controller

    def _workspace_controller_for_container(self, container_id: str):
        container = self._session.find_container(container_id)
        if container is not None:
            return self._workspace_controller_for_domain(container.domain)
        return self._story_workspace_controller

    def _workspace_panel_for_domain(self, domain: BlockDomain):
        if domain == BlockDomain.CHARACTERS:
            return self._character_workspace_panel
        return self._story_workspace_panel

    def _workspace_panel_for_container(self, container_id: str):
        container = self._session.find_container(container_id)
        if container is not None:
            return self._workspace_panel_for_domain(container.domain)
        return self._story_workspace_panel

    def _dispatch_workspace_import(
        self,
        *,
        container_id: str,
        file_paths: object,
        target_block_id: str = "",
        graph_position: tuple[float, float] | None = None,
    ) -> None:
        controller = self._workspace_controller_for_container(container_id)
        controller.import_blocks(
            container_id,
            file_paths,
            target_block_id=target_block_id,
            graph_position=graph_position,
        )

    def _set_workspace_link_feedback(self, container_id: str, message: str) -> None:
        self._workspace_panel_for_container(container_id).set_message(message)

    def _on_graph_files_drop_requested(
        self,
        container_id: str,
        target_block_id: str,
        file_paths: object,
        x: float,
        y: float,
    ) -> None:
        self._dispatch_workspace_import(
            container_id=container_id,
            file_paths=file_paths,
            target_block_id=target_block_id,
            graph_position=(x, y),
        )

    def _project_stats_view(self) -> dict[str, int]:
        return self._project_workspace_service.project_stats_view(self._blocks)

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
        self._workspace_action_button_factory.refresh_icons(self._workspace_action_buttons)
        self._sidebar.set_active(self._section_key)
        self._settings_workspace_panel.set_current_theme(theme_name)

    def _create_new_project(self) -> None:
        self._project_lifecycle_controller.create_new_project()
        self._sync_runtime_state_from_session()

    def _open_project_from_dialog(self) -> None:
        self._project_lifecycle_controller.open_project_from_dialog()
        self._sync_runtime_state_from_session()

    def _select_projects_root_from_dialog(self) -> Path | None:
        return self._project_lifecycle_controller.select_projects_root_from_dialog()

    def _update_projects_root(self, projects_root: Path, *, persist: bool) -> None:
        controller = getattr(self, "_project_lifecycle_controller", None)
        if controller is not None:
            controller.update_projects_root(projects_root, persist=persist)
            return
        storage_roots = self._settings_workspace_service.apply_projects_root(projects_root)
        self._set_storage_roots_runtime(storage_roots)
        if persist:
            self._user_config.save_projects_root_path(storage_roots.projects_root)
        self._apply_storage_paths_to_settings_panel(storage_roots)

    def _load_project(self, project_path: Path) -> None:
        if not self._project_window_controller.load_project(project_path):
            return
        self._sync_runtime_state_from_session()

    def _close_current_project(self) -> None:
        self._project_window_controller.close_current_project()
        self._sync_runtime_state_from_session()

    def _close_secondary_windows(self) -> None:
        self._secondary_windows_controller.close_all()
        self._sync_secondary_window_refs()

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
        self._project_workspace_actions_controller.save_project_metadata(payload)

    def _select_project_visual_from_carousel(self) -> None:
        self._project_workspace_actions_controller.select_project_visual()

    def _open_thumbnail_window(self) -> None:
        self._secondary_windows_controller.open_thumbnail_window(blocks=self._blocks, project_root=self._project_root)
        self._sync_secondary_window_refs()

    def _open_media_carousel_window(self) -> None:
        self._secondary_windows_controller.open_media_carousel_window(blocks=self._blocks, project_root=self._project_root)
        self._sync_secondary_window_refs()

    def _open_free_tree_window(self) -> None:
        self._secondary_windows_controller.open_free_tree_window(blocks=self._blocks, project_root=self._project_root)
        self._sync_secondary_window_refs()

    def _persist_project_blocks(self, blocks: object) -> None:
        if not isinstance(blocks, list):
            return
        normalized = [block for block in blocks if isinstance(block, Block)]
        self._session.replace_blocks(normalized)
        self._sync_runtime_state_from_session()
        if self._project_root is None:
            return
        try:
            self._session.persist()
        except Exception:
            return

        self._secondary_windows_controller.sync_project_blocks(blocks=self._blocks, project_root=self._project_root)
        self._sync_secondary_window_refs()
        self._refresh_project_workspace()

    def _seed_workspace_structure_defaults(
        self,
        project_path: Path,
        *,
        storage: ProjectStorageService | None = None,
    ) -> None:
        self._project_structure_service.seed_workspace_structure_defaults(project_path, storage=storage)

    def _ensure_workspace_structure_on_open(self, project_path: Path, blocks: list[Block]) -> list[Block]:
        return self._project_structure_service.ensure_workspace_structure_on_open(project_path, blocks)

    def _migrate_legacy_project_tree_to_block_paths(self, project_path: Path, blocks: list[Block]) -> bool:
        return self._project_structure_service.migrate_legacy_project_tree_to_block_paths(project_path, blocks)

    def _load_legacy_project_free_tree(self, project_path: Path):
        return self._project_structure_service.load_legacy_project_free_tree(project_path)

    @staticmethod
    def _legacy_tree_from_payload(data: dict):
        return ProjectStructureService.legacy_tree_from_payload(data)

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
    """Bootstrap and execute the Qt application main window."""

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
