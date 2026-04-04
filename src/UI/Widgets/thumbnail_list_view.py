from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QCursor, QDrag
from PySide6.QtWidgets import QListView

from domain import Block
from UI.Widgets.thumbnail_model import ThumbnailListModel
from UI.Widgets.thumbnail_delegate import ThumbnailDelegate
from UI.themes import initialize_widget_primitives


class ThumbnailListView(QListView):
    """List view displaying blocks using a lightweight MVC delegate."""

    def __init__(
        self,
        parent=None,
        *,
        on_block_click: Callable[[Block], None] | None = None,
        on_block_double_click: Callable[[Block], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_block_click = on_block_click
        self._on_block_double_click = on_block_double_click

        self._model = ThumbnailListModel(self)
        self.setModel(self._model)
        
        self._delegate = ThumbnailDelegate(self)
        self.setItemDelegate(self._delegate)

        self.setUniformItemSizes(True)
        self.setSpacing(8)
        self.setAlternatingRowColors(False)
        self.setWordWrap(True)
        self.setSelectionMode(QListView.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QListView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        
        self.clicked.connect(self._handle_clicked)
        self.doubleClicked.connect(self._handle_double_clicked)
        
        initialize_widget_primitives(self)

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self._model.set_blocks(blocks, project_root=project_root)
        initialize_widget_primitives(self)

    def set_block_handlers(
        self,
        *,
        on_block_click: Callable[[Block], None] | None = None,
        on_block_double_click: Callable[[Block], None] | None = None,
    ) -> None:
        self._on_block_click = on_block_click
        self._on_block_double_click = on_block_double_click

    def _handle_clicked(self, index: QModelIndex) -> None:
        block = self._model.block_at(index)
        if block and self._on_block_click is not None:
            self._on_block_click(block)

    def _handle_double_clicked(self, index: QModelIndex) -> None:
        block = self._model.block_at(index)
        if block and self._on_block_double_click is not None:
            self._on_block_double_click(block)

    def startDrag(self, supported_actions: Qt.DropActions) -> None:  # noqa: N802 (Qt naming)
        indexes = self.selectedIndexes()
        if not indexes:
            current = self.currentIndex()
            if current.isValid():
                indexes = [current]
        if not indexes:
            hover_index = self.indexAt(self.viewport().mapFromGlobal(QCursor.pos()))
            if hover_index.isValid():
                indexes = [hover_index]
        if not indexes:
            return

        mime = self._model.mimeData(indexes)
        if mime is None:
            return

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction if supported_actions & Qt.CopyAction else supported_actions)
