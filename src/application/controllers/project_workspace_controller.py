from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QDialog

from application.session import ProjectSession
from application.workspaces import ProjectWorkspaceService
from infrastructure.storage import ProjectStorageService


class ProjectWorkspaceController:
    """Handles project workspace actions such as metadata save and preview selection."""

    def __init__(
        self,
        *,
        session: ProjectSession,
        project_workspace_service: ProjectWorkspaceService,
        storage: ProjectStorageService | None = None,
        refresh_workspace: Callable[[], None],
        set_feedback: Callable[[str], None],
        visual_picker_dialog_cls,
        dialog_parent,
    ) -> None:
        self._session = session
        self._project_workspace_service = project_workspace_service
        self._storage = storage or ProjectStorageService()
        self._refresh_workspace = refresh_workspace
        self._set_feedback = set_feedback
        self._visual_picker_dialog_cls = visual_picker_dialog_cls
        self._dialog_parent = dialog_parent

    def save_project_metadata(self, payload: dict) -> None:
        project_root = self._session.project_root
        if project_root is None:
            return
        try:
            metadata = self._storage.load_project_metadata(project_root)
        except Exception:
            metadata = {}
        metadata = self._project_workspace_service.merge_metadata_payload(metadata, payload)
        try:
            self._storage.save_project_metadata(project_root, metadata)
        except Exception:
            self._set_feedback("Save failed")
            return
        self._refresh_workspace()
        self._set_feedback("Saved")

    def select_project_visual(self) -> None:
        project_root = self._session.project_root
        if project_root is None:
            return

        image_blocks = self._project_workspace_service.image_blocks(self._session.blocks, project_root)
        if not image_blocks:
            self._set_feedback("No image block available")
            return

        try:
            metadata = self._storage.load_project_metadata(project_root)
        except Exception:
            metadata = {}
        current_preview_path = str(metadata.get("preview_image_path", "") or "")
        initial_selected_block_id = self._project_workspace_service.find_block_id_for_preview_path(
            project_root=project_root,
            preview_path=current_preview_path,
            image_blocks=image_blocks,
        )

        dialog = self._visual_picker_dialog_cls(
            blocks=image_blocks,
            project_root=project_root,
            initial_selected_block_id=initial_selected_block_id,
            parent=self._dialog_parent,
        )
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        selected_block = dialog.selected_block()
        if selected_block is None:
            return

        selected_path = self._project_workspace_service.resolve_block_asset_path(selected_block, project_root)
        if selected_path is None or not selected_path.exists():
            self._set_feedback("Selected image not found")
            return

        metadata["preview_image_path"] = self._project_workspace_service.serialize_preview_path(
            project_root=project_root,
            resolved_path=selected_path,
        )
        try:
            self._storage.save_project_metadata(project_root, metadata)
        except Exception:
            self._set_feedback("Save failed")
            return

        self._refresh_workspace()
        self._set_feedback("Project visual updated")
