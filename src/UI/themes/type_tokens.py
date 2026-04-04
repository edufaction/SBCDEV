from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtGui import QColor

from domain import BlockType
from UI.themes.theme import theme_tokens
from UI.themes.theme_loader import active_theme_name, active_theme_tokens_ref


TYPE_FALLBACK_COLORS: dict[BlockType, str] = {
    BlockType.EMPTY: "#6B7280",
    BlockType.CONTAINER: "#5A6B88",
    BlockType.IMAGE: "#5B8BDE",
    BlockType.VIDEO: "#D86B6B",
    BlockType.AUDIO: "#4AA88F",
    BlockType.TEXT: "#6D7894",
    BlockType.PROMPT: "#D29447",
}

TYPE_BADGES: dict[BlockType, str] = {
    BlockType.EMPTY: "EMPTY",
    BlockType.CONTAINER: "CONTAINER",
    BlockType.IMAGE: "IMAGE",
    BlockType.VIDEO: "VIDEO",
    BlockType.AUDIO: "AUDIO",
    BlockType.TEXT: "TEXT",
    BlockType.PROMPT: "PROMPT",
}


def type_token_key(block_type: BlockType) -> str:
    return f"type_{block_type.value}"


def type_badge_label(block_type: BlockType) -> str:
    return TYPE_BADGES.get(block_type, block_type.value.upper())


def resolve_type_color(
    block_type: BlockType,
    *,
    tokens: Mapping[str, str] | None = None,
    theme_name: str | None = None,
) -> QColor:
    active_tokens = tokens or active_theme_tokens_ref()
    token_key = type_token_key(block_type)

    color = active_tokens.get(token_key)
    if color:
        return QColor(color)

    resolved_theme_name = theme_name or active_theme_name()
    themed_color = theme_tokens(resolved_theme_name).get(token_key)
    if themed_color:
        return QColor(themed_color)

    return QColor(TYPE_FALLBACK_COLORS[block_type])
