from __future__ import annotations

import os
from pathlib import Path

from infrastructure.storage import StorageRoots, resolve_storage_roots


class SettingsWorkspaceService:
    """Settings workspace orchestration helpers."""

    def apply_projects_root(self, projects_root: Path) -> StorageRoots:
        normalized = projects_root.expanduser().resolve()
        os.environ["SBC2_PROJECTS_DIR"] = str(normalized)
        return resolve_storage_roots()
