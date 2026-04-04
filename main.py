from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _src_dir() -> Path:
    return _project_root() / "src"


def _ensure_src_on_path() -> None:
    src_path = str(_src_dir())
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def _load_src_main_callable():
    src_main_path = _src_dir() / "main.py"
    spec = importlib.util.spec_from_file_location("_sbc2_src_main", src_main_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load entrypoint: {src_main_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app_main = getattr(module, "main", None)
    if app_main is None:
        raise RuntimeError(f"Entrypoint function 'main' not found in: {src_main_path}")
    return app_main


def main() -> int:
    _ensure_src_on_path()
    app_main = _load_src_main_callable()
    return int(app_main())


if __name__ == "__main__":
    raise SystemExit(main())
