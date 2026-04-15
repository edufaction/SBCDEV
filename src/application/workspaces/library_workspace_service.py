from __future__ import annotations

from pathlib import Path

from domain import Block
from infrastructure.storage import LibraryStorageService, ProjectStorageService


class LibraryWorkspaceService:
    """Workspace-level orchestration for mounted library actions."""

    def __init__(
        self,
        *,
        project_storage: ProjectStorageService | None = None,
        library_storage: LibraryStorageService | None = None,
    ) -> None:
        self._project_storage = project_storage or ProjectStorageService()
        self._library_storage = library_storage or LibraryStorageService()

    def list_mounted_libraries(self, project_path: Path) -> list[dict]:
        return self._project_storage.list_mounted_libraries(project_path)

    def mount_library(
        self,
        project_path: Path,
        *,
        library_path: str | Path,
        label: str = "",
        enabled: bool = True,
        read_only: bool = True,
    ) -> dict:
        return self._project_storage.add_mounted_library(
            project_path,
            library_path=library_path,
            label=label,
            enabled=enabled,
            read_only=read_only,
        )

    def unmount_library(
        self,
        project_path: Path,
        *,
        mount_id: str | None = None,
        library_path: str | Path | None = None,
    ) -> list[dict]:
        return self._project_storage.remove_mounted_library(
            project_path,
            mount_id=mount_id,
            library_path=library_path,
        )

    def load_library_blocks(self, library_path: Path) -> list[Block]:
        return self._library_storage.load_blocks(library_path)

    def create_library(self, library_path: Path, *, name: str) -> Path:
        self._library_storage.create_library(library_path, name)
        return library_path

    def load_library_metadata(self, library_path: Path) -> dict:
        return self._library_storage.load_workspace_metadata(library_path)

    def discover_libraries(self, roots: list[Path]) -> list[Path]:
        discovered: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            if not root.exists():
                continue
            for metadata_file in root.rglob("project.json"):
                library_path = metadata_file.parent.resolve()
                key = str(library_path)
                if key in seen:
                    continue
                seen.add(key)
                discovered.append(library_path)
        return sorted(discovered, key=lambda path: path.name.lower())
