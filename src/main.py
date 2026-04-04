from __future__ import annotations

import sys


def main() -> int:
    try:
        from UI.windows import run_main_window
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "PySide6 is not available in this Python environment.\n"
                f"Interpreter: {sys.executable}\n"
                "Use the project venv interpreter, for example:\n"
                "'.venv/bin/python' src/main.py"
            )
            return 1
        raise

    run_main_window()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
