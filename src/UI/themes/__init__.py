"""Theme system for SBC2 UI."""

from .theme import FONT_SIZE_DEFAULT, FONT_SIZES, THEME_NAMES, theme_tokens
from .theme_loader import (
    SBC2_THEME_QSS_DIR,
    SBC2_THEME_QSS_PATH,
    active_theme_name,
    active_theme_tokens,
    active_theme_tokens_ref,
    apply_theme,
    load_qss_template,
    render_qss_template,
)
from .type_tokens import resolve_type_color, type_badge_label, type_token_key
from .widget_primitives import initialize_widget_primitives, install_widget_primitives

__all__ = [
    "FONT_SIZE_DEFAULT",
    "FONT_SIZES",
    "THEME_NAMES",
    "theme_tokens",
    "SBC2_THEME_QSS_DIR",
    "SBC2_THEME_QSS_PATH",
    "active_theme_name",
    "active_theme_tokens",
    "active_theme_tokens_ref",
    "apply_theme",
    "load_qss_template",
    "render_qss_template",
    "type_token_key",
    "type_badge_label",
    "resolve_type_color",
    "initialize_widget_primitives",
    "install_widget_primitives",
]
