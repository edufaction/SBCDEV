from __future__ import annotations

from copy import deepcopy

FONT_SIZES = [11, 12, 13, 14, 15, 16]
FONT_SIZE_DEFAULT = 12

_SHARED_TOKENS: dict[str, str] = {
    # Typography defaults. Runtime resolution may replace these with installed families.
    "font_family_body": "'Inter', 'Segoe UI', 'SF Pro Text', sans-serif",
    "font_family_display": "'Space Grotesk', 'Inter', 'Segoe UI', sans-serif",
    "font_family_mono": "'JetBrains Mono', 'Inter', 'SF Mono', monospace",
    # Spacing and radius.
    "spacing_1": "2px",
    "spacing_2": "4px",
    "spacing_3": "6px",
    "spacing_4": "9px",
    "spacing_5": "12px",
    "spacing_6": "14px",
    "spacing_8": "28px",
    "spacing_16": "56px",
    "rounded_sm": "2px",
    "rounded_md": "6px",
    "rounded_full": "9999px",
    # Status and block type colors.
    "success": "#40c057",
    "success_dim": "#2d8a42",
    "warning": "#f59f00",
    "warning_dim": "#c47e00",
    "error_dim": "#d73357",
    # Danger / destructive action — consistent across all themes.
    "danger": "#e05252",
    "danger_dim": "#c43a3a",
    "on_danger": "#ffffff",
    # Block type badge colors.
    "type_empty": "#6b7280",
    "type_container": "#5a6b88",
    "type_image": "#4f7fd1",
    "type_video": "#c85c5c",
    "type_audio": "#3f9a84",
    "type_text": "#68738f",
    "type_prompt": "#c68a3f",
    "type_badge_text": "#ffffff",
}

_PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "surface_dim": "#0d1014",
        "surface": "#0d1014",
        "surface_container_lowest": "#0b0e12",
        "surface_container_low": "#12161b",
        "surface_container": "#181d23",
        "surface_container_high": "#20262d",
        "surface_container_highest": "#28303a",
        "surface_variant": "#303846",
        "on_surface": "#f3f5f8",
        "on_surface_variant": "#a7afba",
        "on_surface_muted": "#7c8591",
        "primary": "#6777DF",
        "primary_hover": "#8caef2",
        "primary_dim": "#5b78bc",
        "secondary": "#5ea7a0",
        "secondary_dim": "#487f7a",
        "tertiary": "#9bb7ef",
        "tertiary_container": "#2a456e",
        "secondary_container": "#213a3a",
        "on_secondary_container": "#dcf3f1",
        "on_primary_fixed": "#081019",
        "outline": "#56606d",
        "outline_variant": "#434c57",
        "outline_20": "rgba(86,96,109,51)",
        "outline_ghost": "rgba(67,76,87,38)",
        "selection": "#2f466e",
    },
    "dim": {
        "surface_dim": "#111521",
        "surface": "#111521",
        "surface_container_lowest": "#0c1018",
        "surface_container_low": "#171c29",
        "surface_container": "#1d2432",
        "surface_container_high": "#252d3c",
        "surface_container_highest": "#2d3647",
        "surface_variant": "#354055",
        "on_surface": "#eef2fb",
        "on_surface_variant": "#aeb7cb",
        "on_surface_muted": "#808aa0",
        "primary": "#86a5ea",
        "primary_hover": "#96b2f2",
        "primary_dim": "#6480bd",
        "secondary": "#67aaa4",
        "secondary_dim": "#4d837e",
        "tertiary": "#a6bdf0",
        "tertiary_container": "#314c72",
        "secondary_container": "#294040",
        "on_secondary_container": "#e0f3f2",
        "on_primary_fixed": "#081019",
        "outline": "#5f6b81",
        "outline_variant": "#495366",
        "outline_20": "rgba(95,107,129,51)",
        "outline_ghost": "rgba(73,83,102,38)",
        "selection": "#38507a",
    },
    "light": {
        "surface_dim": "#eef1f5",
        "surface": "#eef1f5",
        "surface_container_lowest": "#e7ebf0",
        "surface_container_low": "#f3f5f8",
        "surface_container": "#ffffff",
        "surface_container_high": "#f8f9fb",
        "surface_container_highest": "#ffffff",
        "surface_variant": "#e4e8ee",
        "on_surface": "#20242b",
        "on_surface_variant": "#5a6472",
        "on_surface_muted": "#767f8c",
        "primary": "#5f81c7",
        "primary_hover": "#7193da",
        "primary_dim": "#4968a9",
        "secondary": "#4d8f8b",
        "secondary_dim": "#3a6d6a",
        "tertiary": "#7f9fe0",
        "tertiary_container": "#d9e4fb",
        "secondary_container": "#dbeceb",
        "on_secondary_container": "#233a39",
        "on_primary_fixed": "#ffffff",
        "outline": "#b0b8c4",
        "outline_variant": "#c2c8d1",
        "outline_20": "rgba(95,103,117,51)",
        "outline_ghost": "rgba(95,103,117,38)",
        "selection": "#d6e0f2",
    },
}


def _hex_to_rgba(hex_color: str, alpha_255: int) -> str:
    value = (hex_color or "").strip()
    if len(value) != 7 or not value.startswith("#"):
        return ""
    try:
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
    except ValueError:
        return ""
    return f"rgba({red},{green},{blue},{alpha_255})"


def _build_theme_tokens(name: str) -> dict[str, str]:
    palette = _PALETTES.get(name, _PALETTES["dark"])
    tokens = dict(_SHARED_TOKENS)
    tokens.update(palette)

    primary = tokens["primary"]
    tokens["primary_alpha_05"] = _hex_to_rgba(primary, 13) or "rgba(0,0,0,13)"
    tokens["primary_alpha_15"] = _hex_to_rgba(primary, 38) or "rgba(0,0,0,38)"
    tokens["primary_alpha_25"] = _hex_to_rgba(primary, 64) or "rgba(0,0,0,64)"

    # Danger alpha variants for hover/pressed states.
    danger = tokens["danger"]
    tokens["danger_alpha_15"] = _hex_to_rgba(danger, 38) or "rgba(224,82,82,38)"
    tokens["danger_alpha_25"] = _hex_to_rgba(danger, 64) or "rgba(224,82,82,64)"

    # Semantic aliases used to simplify future QSS without breaking current code.
    tokens["bg_app"] = tokens["surface_dim"]
    tokens["bg_panel"] = tokens["surface_container"]
    tokens["bg_panel_alt"] = tokens["surface_container_high"]
    tokens["bg_field"] = tokens["surface_container_highest"]
    tokens["text"] = tokens["on_surface"]
    tokens["text_muted"] = tokens["on_surface_variant"]
    tokens["text_tech"] = tokens["on_surface_variant"]
    tokens["border"] = tokens["outline"]
    tokens["border_soft"] = tokens["outline_20"]
    tokens["accent"] = tokens["secondary"]
    return tokens


THEME_NAMES = list(_PALETTES.keys())
_THEME_TOKENS = {name: _build_theme_tokens(name) for name in THEME_NAMES}


def theme_tokens(name: str) -> dict[str, str]:
    return deepcopy(_THEME_TOKENS.get(name, _THEME_TOKENS["dark"]))
