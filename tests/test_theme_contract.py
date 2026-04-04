import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from UI.themes import THEME_NAMES, load_qss_template, theme_tokens


def _qss_placeholders(qss: str) -> set[str]:
    tokens = set(re.findall(r"@([A-Za-z0-9_]+)", qss))
    tokens.discard("font_size_px")
    return tokens


def test_qss_placeholders_exist_in_every_theme() -> None:
    placeholders = _qss_placeholders(load_qss_template())
    assert placeholders

    for theme_name in THEME_NAMES:
        tokens = theme_tokens(theme_name)
        missing = sorted(placeholders - set(tokens))
        assert not missing, f"Missing tokens for theme '{theme_name}': {missing}"


def test_theme_token_schemas_are_consistent_across_themes() -> None:
    dark_schema = set(theme_tokens("dark"))
    assert dark_schema

    for theme_name in THEME_NAMES:
        assert set(theme_tokens(theme_name)) == dark_schema
