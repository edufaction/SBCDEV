from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QMainWindow, QSplitter

from domain import Block, FreeTree
from UI.Widgets import BlockPropertyWidget, FreeTreeWidget, PanelContainerWidget
from UI.themes import initialize_widget_primitives
from UI.windows.window_helpers import load_app_icon


class FreeTreeWindow(QMainWindow):
    """Window hosting the FreeTree widget for all project blocks."""

    tree_changed = Signal(object)
    blocks_changed = Signal(object)

    def __init__(
        self,
        *,
        blocks: list[Block] | None = None,
        persisted_tree: FreeTree | None = None,
        project_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("SBC2 - Free Tree")
        icon = load_app_icon()
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(880, 680)
        self.setMinimumSize(640, 420)

        if blocks is None:
            blocks = []
        self._free_tree_widget = FreeTreeWidget(self)
        self._property_widget = BlockPropertyWidget(self)
        self._content_splitter = QSplitter(Qt.Horizontal, self)
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.addWidget(self._free_tree_widget)
        self._content_splitter.addWidget(self._property_widget)
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 2)
        self._content_splitter.setSizes([560, 320])
        self._free_tree_widget.set_blocks(blocks, persisted_tree=persisted_tree, project_root=project_root)
        self._free_tree_widget.tree_changed.connect(self.tree_changed.emit)
        self._free_tree_widget.blocks_changed.connect(self.blocks_changed.emit)
        self._free_tree_widget.block_selected.connect(self._on_block_selected)
        self._property_widget.relative_path_changed.connect(self._on_relative_path_changed)

        self._panel = PanelContainerWidget(self)
        self._panel.set_body_widget(self._content_splitter)
        self.setCentralWidget(self._panel)
        initialize_widget_primitives(self)

    def current_tree(self) -> FreeTree:
        return self._free_tree_widget.current_tree()

    def _on_block_selected(self, block: Block | None, container_id: str) -> None:
        normalized_container_id = container_id.strip() or None
        self._property_widget.set_block(block, container_id=normalized_container_id)

    def _on_relative_path_changed(self, block_id: str, container_id: str, relative_path: str) -> None:
        self._free_tree_widget.set_block_relative_path(block_id, container_id, relative_path)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.tree_changed.emit(self.current_tree())
        super().closeEvent(event)
