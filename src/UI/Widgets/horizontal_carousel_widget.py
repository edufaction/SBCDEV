from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from domain import Block, BlockType
from UI.Widgets.empty_state_widget import EmptyStateWidget
from UI.Widgets.thumbnail_utils import extract_video_preview, load_image_safe, resolve_block_asset_path
from UI.themes import initialize_widget_primitives

CARD_WIDTH = 260
CARD_IMAGE_HEIGHT = 156
CARD_HEIGHT = CARD_IMAGE_HEIGHT + 18
CARD_HORIZONTAL_MARGINS = 18  # left + right (9 + 9)
CARD_IMAGE_WIDTH = CARD_WIDTH - CARD_HORIZONTAL_MARGINS


class _CarouselCardWidget(QFrame):
    clicked = Signal(object)
    double_clicked = Signal(object)

    def __init__(self, block: Block, *, thumbnail: QPixmap | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._block = block
        self._source_thumbnail = thumbnail
        self.setProperty("carouselItem", True)
        self.setFrameShape(QFrame.NoFrame)
        self.setFrameShadow(QFrame.Plain)
        self.setLineWidth(0)
        self.setFixedWidth(CARD_WIDTH)
        self.setFixedHeight(CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setFixedSize(CARD_IMAGE_WIDTH, CARD_IMAGE_HEIGHT)
        self._image_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._image_label.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(0)
        layout.addWidget(self._image_label, 1, Qt.AlignCenter)

        if thumbnail is None or thumbnail.isNull():
            self._image_label.setText("No thumbnail")
        else:
            self._apply_cover_thumbnail()

    @property
    def block(self) -> Block:
        return self._block

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_cover_thumbnail()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._block)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self._block)
        super().mouseDoubleClickEvent(event)

    def _apply_cover_thumbnail(self) -> None:
        thumbnail = self._source_thumbnail
        if thumbnail is None or thumbnail.isNull():
            return

        target = self._image_label.size()
        if target.width() <= 0 or target.height() <= 0:
            return

        scaled = thumbnail.scaled(
            target,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        x = max(0, (scaled.width() - target.width()) // 2)
        y = max(0, (scaled.height() - target.height()) // 2)
        cropped = scaled.copy(x, y, target.width(), target.height())
        self._image_label.setText("")
        self._image_label.setPixmap(cropped)


class HorizontalCarouselWidget(QWidget):
    """Horizontal carousel for image/video blocks using thumbnail previews."""

    block_selected = Signal(object)
    block_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._cards: list[_CarouselCardWidget] = []
        self._current_block_id: str | None = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(CARD_HEIGHT)

        self._prev_button = QPushButton("<", self)
        self._prev_button.setProperty("ghost", True)
        self._prev_button.setFixedWidth(32)
        self._prev_button.clicked.connect(self._scroll_left)

        self._next_button = QPushButton(">", self)
        self._next_button.setProperty("ghost", True)
        self._next_button.setFixedWidth(32)
        self._next_button.clicked.connect(self._scroll_right)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setFixedHeight(CARD_HEIGHT)
        self._scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._content = QWidget(self)
        self._row = QHBoxLayout(self._content)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(9)
        self._row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._scroll_area.setWidget(self._content)
        self._scroll_area.horizontalScrollBar().valueChanged.connect(self._refresh_nav_state)

        self._carousel_shell = QWidget(self)
        shell_layout = QHBoxLayout(self._carousel_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(9)
        shell_layout.addWidget(self._prev_button, 0)
        shell_layout.addWidget(self._scroll_area, 1)
        shell_layout.addWidget(self._next_button, 0)

        self._empty_state = EmptyStateWidget(
            "No image/video blocks",
            description="Add IMAGE or VIDEO blocks in the project to feed the carousel.",
            parent=self,
        )

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._empty_state)
        self._stack.addWidget(self._carousel_shell)

        initialize_widget_primitives(self)
        self._refresh_nav_state()

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self._project_root = project_root
        eligible = [block for block in blocks if block.type in {BlockType.IMAGE, BlockType.VIDEO}]
        self._rebuild(eligible)

    def _rebuild(self, blocks: list[Block]) -> None:
        self._clear_cards()
        if not blocks:
            self._stack.setCurrentWidget(self._empty_state)
            self._refresh_nav_state()
            return

        self._stack.setCurrentWidget(self._carousel_shell)
        for block in blocks:
            card = _CarouselCardWidget(block, thumbnail=self._thumbnail_for_block(block, self._project_root), parent=self._content)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self.block_activated.emit)
            self._cards.append(card)
            self._row.addWidget(card)

        self._row.addStretch(1)
        self._select_card(blocks[0].id)
        self._refresh_nav_state()

    def _clear_cards(self) -> None:
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._cards.clear()
        self._current_block_id = None

    def _thumbnail_for_block(self, block: Block, project_root: Path | None) -> QPixmap | None:
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

    def _on_card_clicked(self, block: Block) -> None:
        self._select_card(block.id)
        self.block_selected.emit(block)

    def _select_card(self, block_id: str) -> None:
        self._current_block_id = block_id
        for card in self._cards:
            is_selected = card.block.id == block_id
            card.set_selected(is_selected)
            if is_selected:
                self._scroll_area.ensureWidgetVisible(card, 18, 0)

    def _scroll_left(self) -> None:
        bar = self._scroll_area.horizontalScrollBar()
        bar.setValue(max(bar.minimum(), bar.value() - max(220, self._scroll_area.viewport().width() // 2)))

    def _scroll_right(self) -> None:
        bar = self._scroll_area.horizontalScrollBar()
        bar.setValue(min(bar.maximum(), bar.value() + max(220, self._scroll_area.viewport().width() // 2)))

    def _refresh_nav_state(self) -> None:
        if self._stack.currentWidget() is self._empty_state:
            self._prev_button.setEnabled(False)
            self._next_button.setEnabled(False)
            return
        bar = self._scroll_area.horizontalScrollBar()
        self._prev_button.setEnabled(bar.value() > bar.minimum())
        self._next_button.setEnabled(bar.value() < bar.maximum())
