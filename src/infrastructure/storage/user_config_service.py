from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class UserConfigService:
    """Persist user-level application settings."""

    def __init__(self, *, config_file: Path | None = None) -> None:
        self._config_file = config_file or self.resolve_config_file()

    @staticmethod
    def resolve_config_dir() -> Path:
        try:
            import platformdirs
        except Exception:
            return Path.home() / ".sbc2"
        return Path(platformdirs.user_config_path("SBC2", "AIMovieAssistant"))

    @classmethod
    def resolve_config_file(cls) -> Path:
        env_file = os.getenv("SBC2_USER_CONFIG_FILE", "").strip()
        if env_file:
            return Path(env_file).expanduser().resolve()
        return cls.resolve_config_dir() / "user_config.json"

    def load(self) -> dict:
        if not self._config_file.exists():
            return {}
        try:
            payload = json.loads(self._config_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def save(self, payload: dict) -> None:
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self._config_file.parent, delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(self._config_file)

    def load_last_project_path(self) -> Path | None:
        payload = self.load()
        raw = str(payload.get("last_project_path", "") or "").strip()
        if not raw:
            return None
        return Path(raw).expanduser().resolve()

    def save_last_project_path(self, project_path: Path | None) -> None:
        payload = self.load()
        if project_path is None:
            payload.pop("last_project_path", None)
        else:
            payload["last_project_path"] = str(project_path.expanduser().resolve())
        self.save(payload)
