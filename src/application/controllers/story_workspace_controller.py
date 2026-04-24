from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from application.services import BlockDeletionService, ContainerContentService, ImportRequest
from application.session import ProjectSession
from application.workspaces import BlockWorkspaceService, StoryWorkspaceService
from domain import ValidationError

if TYPE_CHECKING:
    from UI.Frames import StoryWorkspacePanel


class StoryWorkspaceController:
    """UI orchestration for story workspace actions."""

    def __init__(
        self,
        *,
        panel: StoryWorkspacePanel,
        session: ProjectSession,
        content_service: ContainerContentService,
        block_deletion_service: BlockDeletionService,
        block_workspace_service: BlockWorkspaceService,
        story_workspace_service: StoryWorkspaceService,
        persist_blocks: Callable[[object], None],
    ) -> None:
        self._panel = panel
        self._session = session
        self._content_service = content_service
        self._block_deletion_service = block_deletion_service
        self._block_workspace_service = block_workspace_service
        self._story_workspace_service = story_workspace_service
        self._persist_blocks = persist_blocks

    def create_note(self, container_id: str) -> None:
        try:
            result = self._content_service.create_note(self._session, container_id=str(container_id or "").strip())
        except ValidationError as exc:
            self._panel.set_message(str(exc))
            return
        except ValueError as exc:
            self._panel.set_message(str(exc))
            return
        except Exception:
            self._panel.set_message("Note creation failed.")
            return
        self._persist_blocks(self._session.blocks)
        self._panel.select_block(result.affected_block_ids[-1], container_id=result.container_id)
        self._panel.set_message(result.message)

    def update_block(self, payload: dict) -> None:
        if self._session.project_root is None:
            self._panel.set_message("Open a project first.")
            return
        try:
            block = self._block_workspace_service.update_block_from_payload(self._session.blocks, payload)
        except ValueError as exc:
            self._panel.set_message(str(exc))
            return
        except Exception:
            self._panel.set_message("Block update failed.")
            return
        self._persist_blocks(self._session.blocks)
        self._panel.set_message(f"Block saved: {block.name or block.id}")

    def update_shot(self, payload: dict) -> None:
        if self._session.project_root is None:
            self._panel.set_message("Open a project first.")
            return
        try:
            shot = self._story_workspace_service.update_shot_from_payload(self._session.blocks, payload)
        except ValueError as exc:
            self._panel.set_message(str(exc))
            return
        except Exception:
            self._panel.set_message("Shot update failed.")
            return
        self._persist_blocks(self._session.blocks)
        self._panel.set_message(f"Shot saved: {shot.name or shot.id}")

    def import_blocks(
        self,
        container_id: str,
        file_paths: object,
        *,
        target_block_id: str = "",
        graph_position: tuple[float, float] | None = None,
    ) -> None:
        if not isinstance(file_paths, list):
            self._panel.set_message("No file provided.")
            return
        try:
            result = self._content_service.import_files(
                self._session,
                ImportRequest(
                    container_id=str(container_id or "").strip(),
                    file_paths=list(file_paths),
                    target_block_id=str(target_block_id or "").strip(),
                    graph_drop=graph_position,
                    source_tag="workspace_graph_drop" if graph_position is not None else "workspace_toolbar",
                ),
            )
        except ValidationError as exc:
            self._panel.set_message(str(exc))
            return
        except ValueError as exc:
            self._panel.set_message(str(exc))
            return
        except Exception:
            self._panel.set_message("Block import failed.")
            return
        self._persist_blocks(self._session.blocks)
        if not result.affected_block_ids:
            self._panel.set_message("No file imported.")
            return
        self._panel.select_block(result.affected_block_ids[-1], container_id=result.container_id)
        self._panel.set_message(result.message)

    def delete_block(self, block_id: str) -> None:
        if self._session.project_root is None:
            self._panel.set_message("Open a project first.")
            return
        try:
            result = self._block_deletion_service.delete(self._session.blocks, block_id=str(block_id or "").strip())
        except ValueError as exc:
            self._panel.set_message(str(exc))
            return
        except Exception:
            self._panel.set_message("Block deletion failed.")
            return
        self._persist_blocks(self._session.blocks)
        self._panel.set_message(f"Deleted {len(result.deleted_ids)} block(s): {result.deleted_names[0]}")
