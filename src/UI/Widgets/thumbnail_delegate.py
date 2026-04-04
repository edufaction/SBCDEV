from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPalette
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from domain import Block, BlockType
from UI.themes import active_theme_tokens_ref, resolve_type_color, type_badge_label
from UI.Widgets.thumbnail_model import BLOCK_ROLE, PIXMAP_ROLE

MEDIA_ASPECT_WIDTH = 16
MEDIA_ASPECT_HEIGHT = 9
HORIZONTAL_GAP = 8
MIN_DETAILS_WIDTH = 140
MIN_MEDIA_WIDTH = 160


def _fit_rect_to_aspect(bounds: QRect, *, width_ratio: int, height_ratio: int) -> QRect:
    if bounds.width() <= 0 or bounds.height() <= 0:
        return QRect(bounds)

    target_width = bounds.width()
    target_height = max(1, round(target_width * height_ratio / width_ratio))
    if target_height > bounds.height():
        target_height = bounds.height()
        target_width = max(1, round(target_height * width_ratio / height_ratio))

    x = bounds.x() + (bounds.width() - target_width) // 2
    y = bounds.y() + (bounds.height() - target_height) // 2
    return QRect(x, y, target_width, target_height)


def _contrast_text_color(background: QColor) -> QColor:
    luma = (0.299 * background.red()) + (0.587 * background.green()) + (0.114 * background.blue())
    return QColor("#111827") if luma > 150 else QColor("#F8FAFC")


class ThumbnailDelegate(QStyledItemDelegate):
    """Native QPainter delegate matching ThumbnailWidget's visuals for O(1) rendering footprint."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._theme_tokens = active_theme_tokens_ref()

    def _current_theme_tokens(self) -> dict[str, str]:
        tokens = active_theme_tokens_ref()
        if tokens is not self._theme_tokens:
            self._theme_tokens = tokens
        return self._theme_tokens

    def paint(self, painter: QPainter, option, index) -> None:
        block: Block = index.data(BLOCK_ROLE)
        if not block:
            super().paint(painter, option, index)
            return

        tokens = self._current_theme_tokens()
        pixmap = index.data(PIXMAP_ROLE)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw selected state container
        rect = option.rect
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, option.palette.highlight())

        # Padding setup
        content_rect = rect.adjusted(8, 8, -8, -8)
        
        # Horizontal Split: 2/3 media, 1/3 details.
        max_canvas_width = max(MIN_MEDIA_WIDTH, content_rect.width() - HORIZONTAL_GAP - MIN_DETAILS_WIDTH)
        canvas_width = min(max_canvas_width, max(MIN_MEDIA_WIDTH, (content_rect.width() * 2) // 3))
        canvas_rect = QRect(content_rect.x(), content_rect.y(), canvas_width, content_rect.height())
        details_rect = QRect(
            canvas_rect.x() + canvas_rect.width() + HORIZONTAL_GAP,
            content_rect.y(),
            content_rect.width() - canvas_width - HORIZONTAL_GAP,
            content_rect.height()
        )

        # 1. Draw Canvas (Image or type fallback)
        self._paint_canvas(painter, block, pixmap, canvas_rect, tokens)

        # 2. Draw details
        self._paint_details(painter, block, option, details_rect, tokens)

        painter.restore()

    def _paint_canvas(self, painter: QPainter, block: Block, pixmap, rect: QRect, tokens: dict[str, str]) -> None:
        base_color = resolve_type_color(block.type, tokens=tokens)
        border_color = QColor(tokens.get("outline_20", "#3b3f47"))
        panel_alt_color = QColor(tokens.get("surface_container_high", "#2b2e35"))
        badge_color = QColor(tokens.get("type_badge_text", "#f8fafc"))
        text_color = _contrast_text_color(base_color)

        inner_rect = rect.adjusted(1, 1, -1, -1)
        
        # Background
        painter.setBrush(base_color if pixmap is None else panel_alt_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(inner_rect, 10, 10)

        # Foreground
        if pixmap is not None:
            fit_rect = _fit_rect_to_aspect(
                inner_rect.adjusted(6, 6, -6, -6),
                width_ratio=MEDIA_ASPECT_WIDTH,
                height_ratio=MEDIA_ASPECT_HEIGHT,
            )
            scaled = pixmap.scaled(fit_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = fit_rect.x() + (fit_rect.width() - scaled.width()) // 2
            y = fit_rect.y() + (fit_rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        elif block.type in {BlockType.TEXT, BlockType.PROMPT}:
            painter.setPen(text_color)
            preview_text = self._text_preview(block)
            text_rect = _fit_rect_to_aspect(
                inner_rect.adjusted(12, 10, -12, -10),
                width_ratio=MEDIA_ASPECT_WIDTH,
                height_ratio=MEDIA_ASPECT_HEIGHT,
            )
            painter.drawText(text_rect, Qt.TextWordWrap | Qt.AlignTop | Qt.AlignLeft, preview_text)
        else:
            painter.setPen(text_color)
            painter.drawText(inner_rect, Qt.AlignCenter, type_badge_label(block.type))

        # Top-Right Badge
        painter.setPen(badge_color)
        painter.drawText(inner_rect.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignRight, type_badge_label(block.type))

    def _paint_details(self, painter: QPainter, block: Block, option, rect: QRect, tokens: dict[str, str]) -> None:
        badge_bg = resolve_type_color(block.type, tokens=tokens)
        badge_text_color = QColor(tokens.get("type_badge_text", _contrast_text_color(badge_bg).name()))
        border_color = QColor(tokens.get("outline_20", "#3b3f47"))
        
        main_text_color = option.palette.color(QPalette.HighlightedText) if option.state & QStyle.State_Selected else option.palette.color(QPalette.Text)
        muted_color = (
            option.palette.color(QPalette.HighlightedText)
            if option.state & QStyle.State_Selected
            else QColor(tokens.get("on_surface_muted", "#9ca3af"))
        )
        
        # Draw Type Badge
        badge_text = type_badge_label(block.type)
        fm = option.fontMetrics
        badge_width = max(96, fm.horizontalAdvance(badge_text) + 16)
        badge_rect = QRect(rect.x(), rect.y(), badge_width, 22)
        
        painter.setBrush(badge_bg)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(badge_rect, 10, 10)
        
        bold_font = painter.font()
        bold_font.setBold(True)
        bold_font.setPointSize(max(8, bold_font.pointSize() - 1))
        painter.setFont(bold_font)
        painter.setPen(badge_text_color)
        painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

        # Title
        painter.setFont(option.font)
        painter.setPen(main_text_color)
        title_rect = QRect(rect.x(), badge_rect.bottom() + 8, rect.width(), fm.height() * 2)
        title_text = block.name or block.id
        # Simple word wrap bounding
        painter.drawText(title_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, title_text)

        # Meta
        painter.setPen(muted_color)
        meta_rect = QRect(rect.x(), title_rect.bottom() + 4, rect.width(), fm.height())
        meta_parts = [block.type.value, block.profile]
        if block.is_link():
            meta_parts.append("LINK")
        meta_text = "  |  ".join(meta_parts)
        painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignTop, meta_text)

    def _text_preview(self, block: Block) -> str:
        for key in ("text", "prompt_generated", "prompt_ref", "description", "label"):
            value = block.content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return type_badge_label(block.type)

    def sizeHint(self, option, index) -> QSize:
        return QSize(420, 180)
