from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from domain import Block
from UI.Widgets.thumbnail_widget import ThumbnailWidget
from UI.themes import initialize_widget_primitives


class AssetGridWidget(QScrollArea):
    """Grid collection view built from reusable ThumbnailWidget cards."""

    item_clicked = Signal(object)
    item_activated = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        on_block_click: Callable[[Block], None] | None = None,
        on_block_double_click: Callable[[Block], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_block_click = on_block_click
        self._on_block_double_click = on_block_double_click
        self._blocks: list[Block] = []
        self._project_root: Path | None = None

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)

        self._content = QWidget(self)
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(9, 9, 9, 9)
        self._grid.setSpacing(9)
        self.setWidget(self._content)

        initialize_widget_primitives(self)

    def set_block_handlers(
        self,
        *,
        on_block_click: Callable[[Block], None] | None = None,
        on_block_double_click: Callable[[Block], None] | None = None,
    ) -> None:
        self._on_block_click = on_block_click
        self._on_block_double_click = on_block_double_click

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self._blocks = list(blocks)
        self._project_root = project_root
        self._rebuild_grid()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._rebuild_grid()

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _column_count(self) -> int:
        viewport_width = max(1, self.viewport().width())
        card_min_width = 320
        return max(1, viewport_width // card_min_width)

    def _rebuild_grid(self) -> None:
        self._clear_grid()
        if not self._blocks:
            return

        columns = self._column_count()
        for index, block in enumerate(self._blocks):
            row = index // columns
            col = index % columns
            card = ThumbnailWidget(
                block,
                project_root=self._project_root,
                on_click=self._emit_click,
                on_double_click=self._emit_double_click,
                drag_enabled=True,
                parent=self._content,
            )
            card.setMinimumHeight(180)
            self._grid.addWidget(card, row, col)

        for col in range(columns):
            self._grid.setColumnStretch(col, 1)

    def _emit_click(self, block: Block) -> None:
        self.item_clicked.emit(block)
        if self._on_block_click is not None:
            self._on_block_click(block)

    def _emit_double_click(self, block: Block) -> None:
        self.item_activated.emit(block)
        if self._on_block_double_click is not None:
            self._on_block_double_click(block)
