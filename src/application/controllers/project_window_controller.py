from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from application.session import ProjectSession
from application.workspaces import ProjectWorkspaceService
from domain import Block

if TYPE_CHECKING:
    from UI.Frames import CharacterWorkspacePanel, LibraryWorkspacePanel, ProjectWorkspacePanel, StoryWorkspacePanel


class ProjectWindowController:
    """Coordinates project lifecycle and global workspace refresh."""

    def __init__(
        self,
        *,
        session: ProjectSession,
        project_workspace_service: ProjectWorkspaceService,
        project_workspace_panel: ProjectWorkspacePanel,
        character_workspace_panel: CharacterWorkspacePanel,
        story_workspace_panel: StoryWorkspacePanel,
        library_workspace_panel: LibraryWorkspacePanel,
        update_workspace_footer: Callable[[], None],
        close_secondary_windows: Callable[[], None],
        save_last_project_path: Callable[[Path | None], None],
        ensure_workspace_structure_on_open: Callable[[Path, list[Block]], list[Block]],
        merge_mounted_libraries: Callable[[Path, list[Block]], list[Block]],
        load_blocks_safely: Callable[[Path], list[Block] | None],
        refresh_dashboard_stats: Callable[[], None],
        get_user_libraries_root: Callable[[], Path],
        get_application_libraries_root: Callable[[], Path],
    ) -> None:
        self._session = session
        self._project_workspace_service = project_workspace_service
        self._project_workspace_panel = project_workspace_panel
        self._character_workspace_panel = character_workspace_panel
        self._story_workspace_panel = story_workspace_panel
        self._library_workspace_panel = library_workspace_panel
        self._update_workspace_footer = update_workspace_footer
        self._close_secondary_windows = close_secondary_windows
        self._save_last_project_path = save_last_project_path
        self._ensure_workspace_structure_on_open = ensure_workspace_structure_on_open
        self._merge_mounted_libraries = merge_mounted_libraries
        self._load_blocks_safely = load_blocks_safely
        self._refresh_dashboard_stats = refresh_dashboard_stats
        self._get_user_libraries_root = get_user_libraries_root
        self._get_application_libraries_root = get_application_libraries_root

    def refresh_workspace(self) -> None:
        project_root = self._session.project_root
        blocks = self._session.blocks
        character_active_container_id = self._character_workspace_panel._graph_widget.active_container_id()
        story_active_container_id = self._story_workspace_panel._graph_widget.active_container_id()
        character_tree_block_id = self._character_workspace_panel.current_tree_block_id() or ""
        character_selected_block_id = self._character_workspace_panel.current_block_id() or ""
        character_property_container_id = self._character_workspace_panel.current_property_container_id()
        story_tree_block_id = self._story_workspace_panel.current_tree_block_id() or ""
        story_selected_block_id = self._story_workspace_panel.current_block_id() or ""
        story_property_container_id = self._story_workspace_panel.current_property_container_id()

        self._project_workspace_panel.set_project_metadata(
            project_path=project_root,
            metadata=self._project_workspace_service.project_metadata_view(
                project_root=project_root,
                blocks=blocks,
            ),
        )
        self._character_workspace_panel.set_blocks(
            blocks,
            project_root=project_root,
            active_container_id=character_active_container_id,
        )
        self._story_workspace_panel.set_blocks(
            blocks,
            project_root=project_root,
            active_container_id=story_active_container_id,
        )
        if character_tree_block_id:
            self._character_workspace_panel.select_tree_block(character_tree_block_id)
        if character_selected_block_id:
            self._character_workspace_panel.inspect_block(
                character_selected_block_id,
                container_id=character_property_container_id,
            )
        if story_tree_block_id:
            self._story_workspace_panel.select_tree_block(story_tree_block_id)
        if story_selected_block_id:
            self._story_workspace_panel.inspect_block(
                story_selected_block_id,
                container_id=story_property_container_id,
            )
        self._library_workspace_panel.set_context(
            project_root=project_root,
            user_libraries_root=self._get_user_libraries_root(),
            application_libraries_root=self._get_application_libraries_root(),
        )
        self._refresh_dashboard_stats()

    def load_project(self, project_path: Path) -> bool:
        resolved_path = project_path.expanduser().resolve()
        blocks = self._load_blocks_safely(resolved_path)
        if blocks is None:
            return False
        blocks = self._ensure_workspace_structure_on_open(resolved_path, blocks)
        blocks = self._merge_mounted_libraries(resolved_path, blocks)
        self._session.set_state(project_root=resolved_path, blocks=blocks)
        self._save_last_project_path(resolved_path)
        self._update_workspace_footer()
        self.refresh_workspace()
        self._close_secondary_windows()
        return True

    def close_current_project(self) -> None:
        if self._session.project_root is None and not self._session.blocks:
            self._save_last_project_path(None)
            return
        self._session.clear()
        self._save_last_project_path(None)
        self._update_workspace_footer()
        self.refresh_workspace()
        self._project_workspace_panel.set_save_feedback("")
        self._close_secondary_windows()
