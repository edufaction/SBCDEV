from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from UI.Widgets import EmptyStateWidget, InfoStatTileWidget


@dataclass(slots=True)
class WorkspaceShellParts:
    dashboard_stats_frame: QFrame
    dashboard_stats_title: QLabel
    dashboard_stats_grid_widget: QWidget
    dashboard_stats_grid: QGridLayout
    dashboard_stat_tiles: dict[str, InfoStatTileWidget]
    workspace_dashboard_page: QWidget
    workspace_asset_library_page: QWidget
    workspace_character_studio_page: QWidget
    workspace_ai_presets_page: QWidget
    workspace_tools_page: QWidget
    workspace_settings_page: QWidget
    workspace_story_page: QWidget
    workspace_project_page: QWidget
    workspace_support_page: QWidget
    ai_presets_empty_state: EmptyStateWidget
    projects_page_empty_state: EmptyStateWidget
    support_empty_state: EmptyStateWidget
    workspace_stack: QStackedWidget
    workspace_panel: QWidget


class WorkspaceShellBuilder:
    def __init__(self, parent: QWidget) -> None:
        self._parent = parent

    def build(
        self,
        *,
        workspace_header: QLabel,
        workspace_footer: QLabel,
        workspace_actions_frame: QFrame,
        workspace_action_buttons: list[QWidget],
        project_workspace_panel: QWidget,
        library_workspace_panel: QWidget,
        character_workspace_panel: QWidget,
        settings_workspace_panel: QWidget,
        story_workspace_panel: QWidget,
    ) -> WorkspaceShellParts:
        dashboard_stats_frame = QFrame(self._parent)
        dashboard_stats_frame.setProperty("panelAlt", True)
        dashboard_stats_layout = QVBoxLayout(dashboard_stats_frame)
        dashboard_stats_layout.setContentsMargins(9, 9, 9, 9)
        dashboard_stats_layout.setSpacing(9)

        dashboard_stats_title = QLabel("PROJECT STATS", dashboard_stats_frame)
        dashboard_stats_title.setProperty("section", True)
        dashboard_stats_grid_widget = QWidget(dashboard_stats_frame)
        dashboard_stats_grid = QGridLayout(dashboard_stats_grid_widget)
        dashboard_stats_grid.setContentsMargins(0, 0, 0, 0)
        dashboard_stats_grid.setHorizontalSpacing(9)
        dashboard_stats_grid.setVerticalSpacing(9)
        dashboard_stat_tiles = self._build_dashboard_stat_tiles(dashboard_stats_grid_widget, dashboard_stats_grid)
        dashboard_stats_layout.addWidget(dashboard_stats_title)
        dashboard_stats_layout.addWidget(dashboard_stats_grid_widget)

        actions_layout = QHBoxLayout(workspace_actions_frame)
        actions_layout.setContentsMargins(9, 9, 9, 9)
        actions_layout.setSpacing(9)
        for button in workspace_action_buttons:
            actions_layout.addWidget(button, 0, Qt.AlignLeft)
        actions_layout.addStretch(1)

        workspace_dashboard_page = self._wrap_page(project_workspace_panel, footer=dashboard_stats_frame)
        workspace_asset_library_page = self._wrap_page(library_workspace_panel)
        workspace_character_studio_page = self._wrap_page(character_workspace_panel)

        workspace_ai_presets_page = QWidget(self._parent)
        ai_presets_layout = self._new_page_layout(workspace_ai_presets_page)
        ai_presets_empty_state = EmptyStateWidget(
            "AI PRESETS",
            description="Aucune vue active pour le moment.",
            parent=workspace_ai_presets_page,
        )
        ai_presets_layout.addWidget(ai_presets_empty_state, 1)

        workspace_tools_page = QWidget(self._parent)
        tools_layout = self._new_page_layout(workspace_tools_page)
        tools_layout.addWidget(workspace_actions_frame)
        tools_layout.addStretch(1)

        workspace_settings_page = self._wrap_page(settings_workspace_panel)
        workspace_story_page = self._wrap_page(story_workspace_panel)

        workspace_project_page = QWidget(self._parent)
        project_layout = self._new_page_layout(workspace_project_page)
        projects_page_empty_state = EmptyStateWidget(
            "PROJETS",
            description="Cet espace sera dédié à la gestion de tous les projets.",
            parent=workspace_project_page,
        )
        project_layout.addWidget(projects_page_empty_state, 1)

        workspace_support_page = QWidget(self._parent)
        support_layout = self._new_page_layout(workspace_support_page)
        support_empty_state = EmptyStateWidget(
            "SUPPORT",
            description="Aucune vue active pour le moment.",
            parent=workspace_support_page,
        )
        support_layout.addWidget(support_empty_state, 1)

        workspace_stack = QStackedWidget(self._parent)
        for page in (
            workspace_dashboard_page,
            workspace_asset_library_page,
            workspace_character_studio_page,
            workspace_ai_presets_page,
            workspace_tools_page,
            workspace_settings_page,
            workspace_story_page,
            workspace_project_page,
            workspace_support_page,
        ):
            workspace_stack.addWidget(page)
        workspace_stack.setCurrentWidget(workspace_dashboard_page)

        workspace_panel = QWidget(self._parent)
        workspace_panel.setProperty("panel", True)
        workspace_layout = QVBoxLayout(workspace_panel)
        workspace_layout.setContentsMargins(14, 14, 14, 14)
        workspace_layout.setSpacing(9)
        workspace_layout.addWidget(workspace_header)
        workspace_layout.addWidget(workspace_stack, 1)
        workspace_layout.addWidget(workspace_footer)

        return WorkspaceShellParts(
            dashboard_stats_frame=dashboard_stats_frame,
            dashboard_stats_title=dashboard_stats_title,
            dashboard_stats_grid_widget=dashboard_stats_grid_widget,
            dashboard_stats_grid=dashboard_stats_grid,
            dashboard_stat_tiles=dashboard_stat_tiles,
            workspace_dashboard_page=workspace_dashboard_page,
            workspace_asset_library_page=workspace_asset_library_page,
            workspace_character_studio_page=workspace_character_studio_page,
            workspace_ai_presets_page=workspace_ai_presets_page,
            workspace_tools_page=workspace_tools_page,
            workspace_settings_page=workspace_settings_page,
            workspace_story_page=workspace_story_page,
            workspace_project_page=workspace_project_page,
            workspace_support_page=workspace_support_page,
            ai_presets_empty_state=ai_presets_empty_state,
            projects_page_empty_state=projects_page_empty_state,
            support_empty_state=support_empty_state,
            workspace_stack=workspace_stack,
            workspace_panel=workspace_panel,
        )

    @staticmethod
    def _new_page_layout(page: QWidget) -> QVBoxLayout:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        return layout

    def _wrap_page(self, primary: QWidget, *, footer: QWidget | None = None) -> QWidget:
        page = QWidget(self._parent)
        layout = self._new_page_layout(page)
        layout.addWidget(primary, 1)
        if footer is not None:
            layout.addWidget(footer, 0)
        return page

    @staticmethod
    def _build_dashboard_stat_tiles(
        parent: QWidget,
        grid: QGridLayout,
    ) -> dict[str, InfoStatTileWidget]:
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
        tiles: dict[str, InfoStatTileWidget] = {}
        for index, (key, title, icon_name) in enumerate(specs):
            tile = InfoStatTileWidget(title, icon_name=icon_name, value=0, parent=parent)
            row = index // columns
            col = index % columns
            grid.addWidget(tile, row, col)
            grid.setColumnStretch(col, 1)
            tiles[key] = tile
        return tiles
