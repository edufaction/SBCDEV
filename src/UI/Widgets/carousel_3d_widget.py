from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QEasingCurve, QPointF, QRectF, Qt, Signal, QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtGui import QColor, QFontMetrics, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from domain import Block, BlockType
from UI.Widgets.empty_state_widget import EmptyStateWidget
from UI.Widgets.thumbnail_utils import extract_video_preview, load_image_safe, resolve_block_asset_path
from UI.themes import active_theme_tokens_ref, initialize_widget_primitives, resolve_type_color

_CARD_WIDTH = 260.0
_CARD_HEIGHT = 170.0
_PREVIEW_MARGIN = 10.0
_TITLE_HEIGHT = 28.0


class _Carousel3DCardItem(QGraphicsObject):
    """Animated card item used by the 3D carousel scene."""

    clicked = Signal(object)
    double_clicked = Signal(object)

    def __init__(
        self,
        *,
        block: Block,
        pixmap: QPixmap | None,
        theme_tokens: dict[str, str],
        parent: QGraphicsObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._block = block
        self._pixmap = pixmap
        self._theme_tokens = dict(theme_tokens)
        self._selected = False
        self._rect = QRectF(0.0, 0.0, _CARD_WIDTH, _CARD_HEIGHT)

        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setTransformOriginPoint(self._rect.center())
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        self._shadow = QGraphicsDropShadowEffect()
        self.setGraphicsEffect(self._shadow)
        self._apply_shadow()

    @property
    def block(self) -> Block:
        return self._block

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._rect

    def set_selected(self, selected: bool) -> None:
        next_value = bool(selected)
        if self._selected == next_value:
            return
        self._selected = next_value
        self._apply_shadow()
        self.update()

    def set_theme_tokens(self, theme_tokens: dict[str, str]) -> None:
        self._theme_tokens = dict(theme_tokens)
        self._apply_shadow()
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._block)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self._block)
        super().mouseDoubleClickEvent(event)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ANN001
        del option, widget

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        tokens = self._theme_tokens
        rect = self._rect

        card_color = QColor(tokens.get("surface_container_high", "#1d2024"))
        if self._selected:
            card_color = QColor(tokens.get("surface_container_highest", "#23262a"))

        border_color = QColor(tokens.get("outline_variant", "#46484b"))
        if self._selected:
            border_color = QColor(tokens.get("primary", "#8dacff"))

        painter.setPen(QPen(border_color, 1.4 if self._selected else 1.0))
        painter.setBrush(card_color)
        painter.drawRoundedRect(rect, 14.0, 14.0)

        preview_rect = QRectF(
            rect.x() + _PREVIEW_MARGIN,
            rect.y() + _PREVIEW_MARGIN,
            rect.width() - (_PREVIEW_MARGIN * 2.0),
            rect.height() - _TITLE_HEIGHT - (_PREVIEW_MARGIN * 1.5),
        )

        clip_path = QPainterPath()
        clip_path.addRoundedRect(preview_rect, 10.0, 10.0)
        painter.save()
        painter.setClipPath(clip_path)

        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                int(preview_rect.width()),
                int(preview_rect.height()),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            x = preview_rect.x() + (preview_rect.width() - scaled.width()) / 2.0
            y = preview_rect.y() + (preview_rect.height() - scaled.height()) / 2.0
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            fallback = resolve_type_color(self._block.type, tokens=tokens)
            painter.fillRect(preview_rect, fallback)

        painter.restore()

        title_rect = QRectF(
            rect.x() + _PREVIEW_MARGIN,
            rect.bottom() - _TITLE_HEIGHT,
            rect.width() - (_PREVIEW_MARGIN * 2.0),
            _TITLE_HEIGHT - 4.0,
        )
        painter.setPen(QColor(tokens.get("on_surface", "#f9f9fd")))
        metrics = QFontMetrics(painter.font())
        title_text = self._block.name or self._block.id
        elided = metrics.elidedText(title_text, Qt.ElideRight, int(title_rect.width()))
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

    def _apply_shadow(self) -> None:
        tokens = self._theme_tokens
        if self._selected:
            self._shadow.setBlurRadius(28)
            self._shadow.setOffset(0.0, 8.0)
            self._shadow.setColor(QColor(tokens.get("primary_alpha_25", "rgba(141,172,255,64)")))
            return

        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0.0, 5.0)
        self._shadow.setColor(QColor(tokens.get("outline_20", "rgba(90,93,98,51)")))


class _Carousel3DView(QGraphicsView):
    """Graphics view implementing pseudo-3D carousel layout and animation."""

    block_selected = Signal(object)
    block_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._cards: list[_Carousel3DCardItem] = []
        self._current_index = 0
        self._theme_tokens = dict(active_theme_tokens_ref())
        self._animation_group: QParallelAnimationGroup | None = None

        self.card_spacing = 210.0
        self.side_y_offset = 14.0
        self.base_scale = 1.0
        self.scale_decay = 0.15
        self.opacity_decay = 0.24
        self.min_scale = 0.58
        self.min_opacity = 0.24
        self.animation_duration = 260

        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignCenter)

        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)

        self._refresh_theme()

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self._clear_cards()
        for block in blocks:
            pixmap = self._thumbnail_for_block(block, project_root)
            card = _Carousel3DCardItem(block=block, pixmap=pixmap, theme_tokens=self._theme_tokens)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self.block_activated.emit)
            self._scene.addItem(card)
            self._cards.append(card)

        self._current_index = 0
        self.update_layout(animated=False, emit_signal=True)

    def selected_block(self) -> Block | None:
        if not self._cards:
            return None
        return self._cards[self._current_index].block

    def center_on_block_id(self, block_id: str, *, animated: bool = False) -> None:
        for index, card in enumerate(self._cards):
            if card.block.id != block_id:
                continue
            self.center_on_index(index, animated=animated)
            return

    def center_on_index(self, index: int, *, animated: bool = True) -> None:
        if not self._cards:
            return
        self._current_index = index % len(self._cards)
        self.update_layout(animated=animated, emit_signal=True)

    def next_item(self) -> None:
        if not self._cards:
            return
        self._current_index = (self._current_index + 1) % len(self._cards)
        self.update_layout(animated=True, emit_signal=True)

    def previous_item(self) -> None:
        if not self._cards:
            return
        self._current_index = (self._current_index - 1) % len(self._cards)
        self.update_layout(animated=True, emit_signal=True)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.setSceneRect(-self.width() / 2.0, -self.height() / 2.0, self.width(), self.height())
        self.update_layout(animated=False, emit_signal=False)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.angleDelta().y() < 0:
            self.next_item()
            return
        self.previous_item()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Right, Qt.Key_Down):
            self.next_item()
            return
        if event.key() in (Qt.Key_Left, Qt.Key_Up):
            self.previous_item()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in {QEvent.StyleChange, QEvent.PaletteChange, QEvent.FontChange}:
            self._refresh_theme()
            self.update_layout(animated=False, emit_signal=False)

    def update_layout(self, *, animated: bool, emit_signal: bool) -> None:
        if not self._cards:
            return

        if self._animation_group is not None and self._animation_group.state() == QParallelAnimationGroup.Running:
            self._animation_group.stop()
            self._animation_group = None

        group = QParallelAnimationGroup(self) if animated else None
        count = len(self._cards)

        for index, card in enumerate(self._cards):
            offset = self._circular_offset(index, self._current_index, count)
            # Positions are expressed as top-left item coordinates. Offset by half
            # card size so the selected card is visually centered in the viewport.
            x = (-_CARD_WIDTH / 2.0) + (offset * self.card_spacing)
            y = (-_CARD_HEIGHT / 2.0) + (abs(offset) * self.side_y_offset)
            scale = max(self.min_scale, self.base_scale - abs(offset) * self.scale_decay)
            opacity = max(self.min_opacity, 1.0 - abs(offset) * self.opacity_decay)
            z_value = 100 - abs(offset)
            rotation = 0.0
            if offset < 0:
                rotation = max(-22.0, offset * 7.0)
            elif offset > 0:
                rotation = min(22.0, offset * 7.0)

            card.set_selected(offset == 0)
            card.setZValue(float(z_value))

            if group is None:
                card.setPos(QPointF(x, y))
                card.setScale(scale)
                card.setOpacity(opacity)
                card.setRotation(rotation)
                continue

            self._add_animation(group, card, b"pos", QPointF(x, y))
            self._add_animation(group, card, b"scale", scale)
            self._add_animation(group, card, b"opacity", opacity)
            self._add_animation(group, card, b"rotation", rotation)

        if group is not None:
            self._animation_group = group
            group.finished.connect(self._clear_animation_group)
            group.start()

        if emit_signal:
            selected = self.selected_block()
            if selected is not None:
                self.block_selected.emit(selected)

    def _clear_cards(self) -> None:
        self._scene.clear()
        self._cards.clear()
        self._current_index = 0

    def _on_card_clicked(self, block: Block) -> None:
        for index, card in enumerate(self._cards):
            if card.block.id != block.id:
                continue
            self.center_on_index(index, animated=True)
            return

    @staticmethod
    def _thumbnail_for_block(block: Block, project_root: Path | None) -> QPixmap | None:
        asset_path = resolve_block_asset_path(block, project_root)
        if asset_path is None:
            return None

        image: QImage | None
        if block.type == BlockType.VIDEO:
            preview_path = extract_video_preview(asset_path, project_root=project_root)
            if preview_path is None:
                return None
            image = load_image_safe(preview_path)
        else:
            image = load_image_safe(asset_path)

        if image is None or image.isNull():
            return None
        return QPixmap.fromImage(image)

    @staticmethod
    def _add_animation(group: QParallelAnimationGroup, item: QGraphicsObject, prop: bytes, end_value) -> None:  # noqa: ANN001
        animation = QPropertyAnimation(item, prop)
        animation.setDuration(260)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setEndValue(end_value)
        group.addAnimation(animation)

    @staticmethod
    def _circular_offset(index: int, current: int, count: int) -> int:
        offset = index - current
        if offset > count / 2:
            offset -= count
        elif offset < -count / 2:
            offset += count
        return offset

    def _refresh_theme(self) -> None:
        self._theme_tokens = dict(active_theme_tokens_ref())
        self.setBackgroundBrush(QColor(self._theme_tokens.get("surface_dim", "#0c0e11")))
        for card in self._cards:
            card.set_theme_tokens(self._theme_tokens)
        self.viewport().update()

    def _clear_animation_group(self) -> None:
        self._animation_group = None


class Carousel3DWidget(QWidget):
    """High-level reusable 3D carousel widget for image/video blocks."""

    block_selected = Signal(object)
    block_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(280)

        self._view = _Carousel3DView(self)
        self._view.block_selected.connect(self.block_selected.emit)
        self._view.block_activated.connect(self.block_activated.emit)

        self._empty_state = EmptyStateWidget(
            "No image blocks",
            description="Add IMAGE blocks in the project to choose a visual.",
            parent=self,
        )

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._empty_state)
        self._stack.addWidget(self._view)

        initialize_widget_primitives(self)

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        eligible = [block for block in blocks if block.type in {BlockType.IMAGE, BlockType.VIDEO}]
        if not eligible:
            self._stack.setCurrentWidget(self._empty_state)
            self._view.set_blocks([], project_root=project_root)
            return

        self._stack.setCurrentWidget(self._view)
        self._view.set_blocks(eligible, project_root=project_root)

    def set_selected_block_id(self, block_id: str | None, *, animated: bool = False) -> None:
        if not block_id:
            return
        self._view.center_on_block_id(block_id, animated=animated)

    def selected_block(self) -> Block | None:
        return self._view.selected_block()

    def next_item(self) -> None:
        self._view.next_item()

    def previous_item(self) -> None:
        self._view.previous_item()
