from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from UI.themes.theme import FONT_SIZE_DEFAULT, theme_tokens

SBC2_THEME_QSS_DIR = Path(__file__).resolve().parent / "qss"
_QSS_PART_GLOB = "*.qss"


def render_qss_template(qss_text: str, tokens: dict[str, str]) -> str:
    rendered = qss_text
    # Replace longer tokens first to avoid partial collisions
    # e.g. @bg_panel before @bg_panel_alt.
    for key in sorted(tokens.keys(), key=len, reverse=True):
        rendered = rendered.replace(f"@{key}", tokens[key])
    return rendered


def _read_qss_parts(parts: list[Path]) -> str:
    chunks = [path.read_text(encoding="utf-8").strip() for path in parts]
    return "\n\n".join(chunk for chunk in chunks if chunk)


def _read_qss_dir(path: Path) -> str:
    qss_parts = sorted(path.glob(_QSS_PART_GLOB))
    return _read_qss_parts(qss_parts)


def load_qss_template(path: str | Path | None = None) -> str:
    if path is None:
        if SBC2_THEME_QSS_DIR.exists():
            rendered = _read_qss_dir(SBC2_THEME_QSS_DIR)
            if rendered:
                return rendered
        raise FileNotFoundError(f"QSS directory is empty or missing: {SBC2_THEME_QSS_DIR}")

    path_obj = Path(str(path))
    if path_obj.is_dir():
        return _read_qss_dir(path_obj)
    return path_obj.read_text(encoding="utf-8")


def _as_css_font_family(name: str) -> str:
    return "'" + name.replace("'", "\\'") + "'"


def _pick_available_family(candidates: list[str], installed: set[str], fallback: str) -> str:
    for name in candidates:
        if name and name in installed:
            return name
    return fallback


def _resolve_runtime_font_tokens(app: QApplication, tokens: dict[str, str]) -> dict[str, str]:
    resolved = dict(tokens)
    installed = set(QFontDatabase.families())
    app_default = app.font().family() or "Sans Serif"
    mono_default = QFontDatabase.systemFont(QFontDatabase.FixedFont).family() or app_default

    body_family = _pick_available_family(
        [
            "Inter",
            "SF Pro Text",
            "Segoe UI",
            "Helvetica Neue",
            "Noto Sans",
            "Arial",
            app_default,
        ],
        installed,
        app_default,
    )
    display_family = _pick_available_family(
        ["Space Grotesk", "Inter", "SF Pro Display", body_family, app_default],
        installed,
        body_family,
    )
    mono_family = _pick_available_family(
        ["JetBrains Mono", "SF Mono", "Menlo", "Consolas", "Monaco", "Courier New", mono_default],
        installed,
        mono_default,
    )

    resolved["font_family_body"] = f"{_as_css_font_family(body_family)}, sans-serif"
    if display_family != body_family:
        resolved["font_family_display"] = (
            f"{_as_css_font_family(display_family)}, {_as_css_font_family(body_family)}, sans-serif"
        )
    else:
        resolved["font_family_display"] = f"{_as_css_font_family(body_family)}, sans-serif"
    resolved["font_family_mono"] = f"{_as_css_font_family(mono_family)}, monospace"
    return resolved


def _apply_palette(app: QApplication, tokens: dict[str, str]) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(tokens["surface_dim"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens["on_surface"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(tokens["surface_container_lowest"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["surface_container"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens["surface_container"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens["on_surface"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(tokens["on_surface"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(tokens["surface_container"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["on_surface"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(tokens["on_surface"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens["selection"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens["on_surface"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens["on_surface_muted"]))

    disabled_text = QColor(tokens["on_surface_muted"])
    disabled_button = QColor(tokens["surface_container_low"])
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, disabled_button)
    app.setPalette(palette)


def apply_theme(
    app: QApplication,
    *,
    theme_name: str = "dark",
    font_size: int = FONT_SIZE_DEFAULT,
    qss_path: str | Path | None = None,
) -> None:
    app.setStyle("Fusion")
    qss_template = load_qss_template(qss_path)
    tokens = theme_tokens(theme_name)
    tokens = _resolve_runtime_font_tokens(app, tokens)
    tokens["font_size_px"] = f"{int(font_size)}px"
    app.setProperty("sbc2_theme_name", theme_name)
    app.setProperty("sbc2_theme_tokens", dict(tokens))
    app.setProperty("sbc2_theme_apply_in_progress", True)
    try:
        _apply_palette(app, tokens)
        app.setStyleSheet(render_qss_template(qss_template, tokens))
    finally:
        app.setProperty("sbc2_theme_apply_in_progress", False)


def active_theme_tokens_ref(
    app: QApplication | None = None, *, fallback_theme_name: str = "dark"
) -> dict[str, str]:
    current_app = app or QApplication.instance()
    if current_app is not None:
        raw_tokens = current_app.property("sbc2_theme_tokens")
        if isinstance(raw_tokens, dict):
            return raw_tokens
    return theme_tokens(fallback_theme_name)


def active_theme_tokens(app: QApplication | None = None, *, fallback_theme_name: str = "dark") -> dict[str, str]:
    return dict(active_theme_tokens_ref(app, fallback_theme_name=fallback_theme_name))


def active_theme_name(app: QApplication | None = None, *, fallback_theme_name: str = "dark") -> str:
    current_app = app or QApplication.instance()
    if current_app is not None:
        raw_name = current_app.property("sbc2_theme_name")
        if isinstance(raw_name, str) and raw_name.strip():
            return raw_name
    return fallback_theme_name
