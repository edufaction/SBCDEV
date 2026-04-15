from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from domain import Block
from UI.Widgets.block_properties_editor import BlockPropertiesEditor
from UI.Widgets.empty_state_widget import EmptyStateWidget
from UI.Widgets.panel_header_widget import PanelHeaderWidget
from UI.themes import initialize_widget_primitives


class BlockPropertyWidget(QWidget):
    """Compatibility wrapper around the tree-based block properties editor."""

    relative_path_changed = Signal(str, str, str)
    property_change_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._header = PanelHeaderWidget("BLOCK PROPERTIES", parent=self)
        self._header_label = self._header.title_label
        self._title_label = QLabel("No block selected", self)
        self._title_label.setProperty("title", True)
        self._title_label.setWordWrap(True)
        self._empty_state = EmptyStateWidget(
            "No block selected",
            description="Click a block to display and edit its properties.",
            parent=self,
        )
        self._hint_label = self._empty_state
        self._editor = BlockPropertiesEditor(self)
        self._editor.relative_path_changed.connect(self.relative_path_changed.emit)
        self._editor.property_change_requested.connect(self.property_change_requested.emit)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._title_label)
        root_layout.addWidget(self._empty_state)
        root_layout.addWidget(self._editor, 1)

        initialize_widget_primitives(self)
        self._sync_state(has_block=False)

    def current_block_id(self) -> str | None:
        return self._editor.current_block_id()

    def set_block(self, block: Block | None, *, container_id: str | None = None) -> None:
        self._editor.set_block(block, container_id=container_id)
        if block is None:
            self._title_label.setText("No block selected")
            self._sync_state(has_block=False)
            return
        self._title_label.setText(block.name or block.id)
        self._sync_state(has_block=True)

    def _sync_state(self, *, has_block: bool) -> None:
        self._empty_state.setVisible(not has_block)
        self._editor.setVisible(has_block)
