from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from infrastructure.storage import resolve_storage_roots


def resolve_data_project_dir() -> Path:
    return resolve_storage_roots().projects_root


def resolve_app_icon_path() -> Path | None:
    app_icons_root = Path(__file__).resolve().parents[1] / "AppIcons"
    candidate_dirs = [app_icons_root / "Base", app_icons_root]

    if sys.platform == "darwin":
        preferred = ("icon.icns", "icon.png", "512x512.png", "app.png", "icon.ico")
    elif os.name == "nt":
        preferred = ("icon.ico", "icon.png", "256x256.png", "app.png")
    else:
        preferred = ("icon.png", "512x512.png", "256x256.png", "app.png", "icon.ico")

    for icons_dir in candidate_dirs:
        if not icons_dir.exists():
            continue
        for filename in preferred:
            candidate = icons_dir / filename
            if candidate.exists():
                return candidate
    return None


def load_app_icon():
    from PySide6.QtGui import QIcon

    icon_path = resolve_app_icon_path()
    if icon_path is None:
        return None

    icon = QIcon(str(icon_path))
    if icon.isNull():
        return None
    return icon


def open_with_system_default_app(path: Path) -> bool:
    if not path.exists():
        return False

    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False
