from __future__ import annotations

"""Resolution of storage root directories used by SBC2.

This module centralizes where projects and libraries are located on disk.
The resolver intentionally supports multiple layers so the same codebase can
run in local dev, tests, and packaged app contexts without code changes:

1. explicit environment overrides,
2. local repository-friendly defaults,
3. platform user-data fallback.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageRoots:
    """Concrete roots used by persistence services.

    Attributes:
        projects_root: Root folder where ``*.sbcprj`` workspaces are created and
            discovered.
        user_libraries_root: User-managed external libraries root.
        application_libraries_root: Application-provided libraries root.
    """

    projects_root: Path
    user_libraries_root: Path
    application_libraries_root: Path


def resolve_storage_roots(*, ensure_exists: bool = True) -> StorageRoots:
    """Resolve effective storage roots for the current runtime.

    Args:
        ensure_exists: When ``True``, create resolved directories if they do not
            exist yet.

    Returns:
        A :class:`StorageRoots` object with absolute resolved paths.

    Resolution policy:
        - ``SBC2_PROJECTS_DIR`` overrides projects root,
        - ``SBC2_USER_LIBRARIES_DIR`` overrides user libraries root,
        - ``SBC2_APPLICATION_LIBRARIES_DIR`` overrides app libraries root,
        - otherwise defaults derive from the data root.
    """

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
    """Resolve the base ``DataProject`` directory.

    Priority order:
        1. ``SBC2_DATA_PROJECT_DIR`` environment variable,
        2. local project-relative ``DataProject`` candidates,
        3. platform user-data fallback via ``platformdirs``.
    """

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
    """Return a normalized path from an environment variable.

    Args:
        key: Environment variable name.

    Returns:
        ``None`` when unset/empty, otherwise an absolute resolved path.
    """

    raw = os.getenv(key, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()
