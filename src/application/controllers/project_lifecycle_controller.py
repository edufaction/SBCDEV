from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from application.controllers.project_window_controller import ProjectWindowController
from application.workspaces import SettingsWorkspaceService
from infrastructure.storage import ProjectStorageService, StorageRoots


class ProjectLifecycleController:
    """Handles project creation/open flows and projects-root selection."""

    def __init__(
        self,
        *,
        project_window_controller: ProjectWindowController,
        settings_workspace_service: SettingsWorkspaceService,
        storage: ProjectStorageService | None = None,
        get_storage_roots,
        set_storage_roots,
        save_projects_root_path,
        set_storage_paths,
        prompt_new_project_name,
        prompt_project_choice,
        prompt_projects_root,
        show_open_project_info,
        seed_workspace_structure_defaults,
    ) -> None:
        self._project_window_controller = project_window_controller
        self._settings_workspace_service = settings_workspace_service
        self._storage = storage or ProjectStorageService()
        self._get_storage_roots = get_storage_roots
        self._set_storage_roots = set_storage_roots
        self._save_projects_root_path = save_projects_root_path
        self._set_storage_paths = set_storage_paths
        self._prompt_new_project_name = prompt_new_project_name
        self._prompt_project_choice = prompt_project_choice
        self._prompt_projects_root = prompt_projects_root
        self._show_open_project_info = show_open_project_info
        self._seed_workspace_structure_defaults = seed_workspace_structure_defaults

    def create_new_project(self) -> None:
        name, accepted = self._prompt_new_project_name()
        if not accepted:
            return
        base_name = str(name or "").strip() or "NOUVEAU_PROJET"
        if base_name.lower().endswith(".sbcprj"):
            base_name = base_name[:-7]
        safe_name = self._sanitize_project_folder_name(base_name)
        project_dir_name = self._with_project_dir_suffix(safe_name)
        project_path = self._get_storage_roots().projects_root / project_dir_name
        if project_path.exists():
            project_path = self._unique_project_path(project_dir_name)
        self._storage.create_project(project_path, base_name)
        self._seed_workspace_structure_defaults(project_path, storage=self._storage)
        metadata = self._storage.load_project_metadata(project_path)
        if not str(metadata.get("author_name", "") or "").strip():
            metadata["author_name"] = os.getenv("USER", "").strip() or os.getenv("USERNAME", "").strip()
            self._storage.save_project_metadata(project_path, metadata)
        self._project_window_controller.load_project(project_path)

    def open_project_from_dialog(self) -> None:
        projects = self._list_sbc_project_directories()
        if not projects:
            selected_root = self.select_projects_root_from_dialog()
            if selected_root is None:
                return
            self.update_projects_root(selected_root, persist=True)
            projects = self._list_sbc_project_directories()

        if not projects:
            self._show_open_project_info(
                "Open Project",
                f"No '.sbcprj' project found in:\n{self._get_storage_roots().projects_root}",
            )
            return

        selected_name, accepted = self._prompt_project_choice([path.name for path in projects])
        if not accepted or not selected_name:
            return
        selected_path = next((path for path in projects if path.name == selected_name), None)
        if selected_path is None:
            return
        self._project_window_controller.load_project(selected_path)

    def select_projects_root_from_dialog(self) -> Path | None:
        selected = self._prompt_projects_root(str(self._get_storage_roots().projects_root))
        if not selected:
            return None
        return Path(selected).expanduser().resolve()

    def update_projects_root(self, projects_root: Path, *, persist: bool) -> None:
        storage_roots = self._settings_workspace_service.apply_projects_root(projects_root)
        self._set_storage_roots(storage_roots)
        if persist:
            self._save_projects_root_path(storage_roots.projects_root)
        self._set_storage_paths(storage_roots)

    def _list_sbc_project_directories(self) -> list[Path]:
        root = self._get_storage_roots().projects_root
        if not root.exists():
            return []
        projects = [
            candidate
            for candidate in root.iterdir()
            if candidate.is_dir() and candidate.name.lower().endswith(".sbcprj")
        ]
        return sorted(projects, key=lambda item: item.name.lower())

    def _unique_project_path(self, base_name: str) -> Path:
        stem = base_name.strip()
        if stem.lower().endswith(".sbcprj"):
            stem = stem[:-7]
        stem = stem.strip("_") or f"project_{uuid4().hex[:6]}"
        counter = 1
        while True:
            candidate_name = self._with_project_dir_suffix(f"{stem}_{counter}")
            candidate = self._get_storage_roots().projects_root / candidate_name
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _sanitize_project_folder_name(name: str) -> str:
        sanitized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name)
        sanitized = sanitized.strip("_")
        return sanitized or f"project_{uuid4().hex[:6]}"

    @staticmethod
    def _with_project_dir_suffix(name: str) -> str:
        normalized = name.strip()
        if normalized.lower().endswith(".sbcprj"):
            normalized = normalized[:-7]
        normalized = normalized.strip("_") or f"project_{uuid4().hex[:6]}"
        return f"{normalized}.sbcprj"
