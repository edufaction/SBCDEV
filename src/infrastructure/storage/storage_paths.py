from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageRoots:
    projects_root: Path
    user_libraries_root: Path
    application_libraries_root: Path


def resolve_storage_roots(*, ensure_exists: bool = True) -> StorageRoots:
    base_data_root = _resolve_base_data_root()
    projects_root = _env_path("SBC2_PROJECTS_DIR") or base_data_root
    user_libraries_root = _env_path("SBC2_USER_LIBRARIES_DIR") or (projects_root / "LIBRARIES" / "USER")
    application_libraries_root = _env_path("SBC2_APPLICATION_LIBRARIES_DIR") or (
        base_data_root / "LIBRARIES" / "APPLICATION"
    )

    if ensure_exists:
        projects_root.mkdir(parents=True, exist_ok=True)
        user_libraries_root.mkdir(parents=True, exist_ok=True)
        application_libraries_root.mkdir(parents=True, exist_ok=True)

    return StorageRoots(
        projects_root=projects_root.resolve(),
        user_libraries_root=user_libraries_root.resolve(),
        application_libraries_root=application_libraries_root.resolve(),
    )


def _resolve_base_data_root() -> Path:
    env_root = _env_path("SBC2_DATA_PROJECT_DIR")
    if env_root is not None:
        return env_root

    module_path = Path(__file__).resolve()
    local_candidates = [
        module_path.parents[2] / "DataProject",  # src/DataProject
        module_path.parents[3] / "DataProject",  # repo-root/DataProject
    ]
    for candidate in local_candidates:
        if candidate.exists():
            return candidate

    try:
        import platformdirs
    except Exception:
        return local_candidates[-1]

    return platformdirs.user_data_path("SBC2", "AIMovieAssistant") / "DataProject"


def _env_path(key: str) -> Path | None:
    raw = os.getenv(key, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()
