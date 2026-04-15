import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import QApplication

from UI.themes import SBC2_THEME_QSS_DIR, apply_theme, load_qss_template, render_qss_template, theme_tokens


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_render_qss_template_replaces_long_tokens_first() -> None:
    qss = "A:@bg_panel_alt B:@bg_panel"
    rendered = render_qss_template(qss, {"bg_panel": "#111111", "bg_panel_alt": "#222222"})
    assert rendered == "A:#222222 B:#111111"


def test_load_qss_template_default_path_exists() -> None:
    text = load_qss_template()
    assert isinstance(text, str)
    assert len(text) > 20
    assert Path(SBC2_THEME_QSS_DIR).exists()


def test_apply_theme_sets_app_stylesheet_and_tokens() -> None:
    app = _app()
    apply_theme(app, theme_name="dark", font_size=13)
    stylesheet = app.styleSheet()
    tokens = app.property("sbc2_theme_tokens")
    theme_name = app.property("sbc2_theme_name")

    assert isinstance(stylesheet, str)
    assert len(stylesheet) > 20
    assert isinstance(tokens, dict)
    assert theme_name == "dark"
    assert tokens.get("font_size_px") == "13px"
    assert "@bg_main" not in stylesheet


def test_theme_tokens_expose_content_type_base_colors() -> None:
    tokens = theme_tokens("dark")
    for key in (
        "type_empty",
        "type_container",
        "type_image",
        "type_video",
        "type_audio",
        "type_text",
        "type_prompt",
        "type_badge_text",
    ):
        assert key in tokens
        assert isinstance(tokens[key], str)
        assert tokens[key].startswith("#")


def test_theme_tokens_expose_digital_architect_surface_and_brand_tokens() -> None:
    tokens = theme_tokens("dark")
    for key in (
        "surface_dim",
        "surface_container_low",
        "surface_container",
        "surface_container_high",
        "surface_container_highest",
        "surface_container_lowest",
        "on_surface",
        "on_surface_variant",
        "primary",
        "secondary",
        "tertiary",
        "secondary_container",
        "on_secondary_container",
        "error_dim",
        "font_family_body",
        "font_family_display",
        "font_family_mono",
        "spacing_2",
        "spacing_4",
        "spacing_6",
        "rounded_sm",
        "rounded_md",
        "rounded_full",
    ):
        assert key in tokens
        assert isinstance(tokens[key], str)
        assert tokens[key]
