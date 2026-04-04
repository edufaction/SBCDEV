from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    project_root = Path(__file__).resolve().parent
    src_dir = project_root / "src"
    if not src_dir.is_dir():
        return
    src_path = str(src_dir)
    if src_path in sys.path:
        return
    sys.path.insert(0, src_path)


_ensure_src_on_path()

