from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from UI.themes.theme import FONT_SIZE_DEFAULT, theme_tokens

SBC2_THEME_QSS_PATH = Path(__file__).resolve().parent / "app.qss"
SBC2_THEME_QSS_DIR = Path(__file__).resolve().parent / "qss"


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


def load_qss_template(path: str | Path | None = None) -> str:
    if path is None:
        if SBC2_THEME_QSS_DIR.exists():
            qss_parts = sorted(SBC2_THEME_QSS_DIR.glob("*.qss"))
            if qss_parts:
                return _read_qss_parts(qss_parts)
        if SBC2_THEME_QSS_PATH.exists():
            return SBC2_THEME_QSS_PATH.read_text(encoding="utf-8")
        raise FileNotFoundError(f"QSS not found: {SBC2_THEME_QSS_PATH}")

    if isinstance(path, Path):
        if path.is_dir():
            qss_parts = sorted(path.glob("*.qss"))
            return _read_qss_parts(qss_parts)
        return path.read_text(encoding="utf-8")
    path_obj = Path(str(path))
    if path_obj.is_dir():
        qss_parts = sorted(path_obj.glob("*.qss"))
        return _read_qss_parts(qss_parts)
    return path_obj.read_text(encoding="utf-8")


def _as_css_font_family(name: str) -> str:
    return "'" + name.replace("'", "\\'") + "'"


def _pick_available_family(candidates: list[str], installed: set[str], fallback: str) -> str:
    for name in candidates:
        if name and name in installed:
            return name
    return fallback


def _hex_to_rgba(hex_color: str, alpha_255: int) -> str:
    value = (hex_color or "").strip()
    if len(value) == 7 and value.startswith("#"):
        try:
            r = int(value[1:3], 16)
            g = int(value[3:5], 16)
            b = int(value[5:7], 16)
            return f"rgba({r},{g},{b},{alpha_255})"
        except ValueError:
            return ""
    return ""


def _resolve_runtime_alpha_tokens(tokens: dict[str, str]) -> dict[str, str]:
    resolved = dict(tokens)
    primary = resolved.get("primary", "")
    for key, alpha in (("primary_alpha_05", 13), ("primary_alpha_15", 38), ("primary_alpha_25", 64)):
        rgba = _hex_to_rgba(primary, alpha)
        if rgba:
            resolved[key] = rgba
    return resolved


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
    tokens = _resolve_runtime_alpha_tokens(tokens)
    tokens = _resolve_runtime_font_tokens(app, tokens)
    tokens["font_size_px"] = f"{int(font_size)}px"
    app.setProperty("sbc2_theme_name", theme_name)
    app.setProperty("sbc2_theme_tokens", dict(tokens))
    app.setProperty("sbc2_theme_apply_in_progress", True)
    try:
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
