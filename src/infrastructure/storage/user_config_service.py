from __future__ import annotations

"""Persistence helper for user-scoped SBC2 settings.

The service stores lightweight preferences in a JSON file located in the
platform user config directory (or an override file through
``SBC2_USER_CONFIG_FILE``). It is intentionally minimal and resilient:

- invalid/missing JSON yields safe defaults,
- writes are atomic through a temporary file + replace,
- stored paths are normalized to absolute resolved paths.
"""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class UserConfigService:
    """Read/write user-level application settings.

    This service is used for preferences that are independent from a specific
    project workspace, for example:

    - last opened project path,
    - preferred root folder where projects are discovered.
    """

    def __init__(self, *, config_file: Path | None = None) -> None:
        """Initialize a config service.

        Args:
            config_file: Optional explicit config file location. When omitted,
                the default resolved location is used.
        """

        self._config_file = config_file or self.resolve_config_file()

    @staticmethod
    def resolve_config_dir() -> Path:
        """Return the user config directory for SBC2.

        Resolution strategy:
            1. ``platformdirs`` user config path when available,
            2. ``~/.sbc2`` fallback when the dependency is unavailable.
        """

        try:
            import platformdirs
        except Exception:
            return Path.home() / ".sbc2"
        return Path(platformdirs.user_config_path("SBC2", "AIMovieAssistant"))

    @classmethod
    def resolve_config_file(cls) -> Path:
        """Return the config file path used by this service.

        Priority:
            1. ``SBC2_USER_CONFIG_FILE`` environment variable,
            2. default ``user_config.json`` in :meth:`resolve_config_dir`.
        """

        env_file = os.getenv("SBC2_USER_CONFIG_FILE", "").strip()
        if env_file:
            return Path(env_file).expanduser().resolve()
        return cls.resolve_config_dir() / "user_config.json"

    def load(self) -> dict:
        """Load the raw config payload.

        Returns:
            A dictionary payload. Returns an empty dict if the file does not
            exist, cannot be parsed, or does not contain a JSON object.
        """

        if not self._config_file.exists():
            return {}
        try:
            payload = json.loads(self._config_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def save(self, payload: dict) -> None:
        """Persist a full config payload atomically.

        The write uses a temporary file in the same directory followed by an
        atomic ``replace`` to avoid partial writes on crashes/interruption.

        Args:
            payload: JSON-serializable mapping to persist.
        """

        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self._config_file.parent, delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(self._config_file)

    def load_last_project_path(self) -> Path | None:
        """Return the most recently opened project path, if any."""

        payload = self.load()
        raw = str(payload.get("last_project_path", "") or "").strip()
        if not raw:
            return None
        return Path(raw).expanduser().resolve()

    def save_last_project_path(self, project_path: Path | None) -> None:
        """Persist or clear the most recently opened project path.

        Args:
            project_path: Resolved path to store, or ``None`` to remove the
                setting.
        """

        payload = self.load()
        if project_path is None:
            payload.pop("last_project_path", None)
        else:
            payload["last_project_path"] = str(project_path.expanduser().resolve())
        self.save(payload)

    def load_projects_root_path(self) -> Path | None:
        """Return the preferred root directory where projects are listed.

        This preference is used by the *Open Project* workflow to remember the
        last selected projects directory across sessions.
        """

        payload = self.load()
        raw = str(payload.get("projects_root_path", "") or "").strip()
        if not raw:
            return None
        return Path(raw).expanduser().resolve()

    def save_projects_root_path(self, projects_root: Path | None) -> None:
        """Persist or clear the preferred projects root directory.

        Args:
            projects_root: Directory to store, or ``None`` to clear the
                preference.
        """

        payload = self.load()
        if projects_root is None:
            payload.pop("projects_root_path", None)
        else:
            payload["projects_root_path"] = str(projects_root.expanduser().resolve())
        self.save(payload)
