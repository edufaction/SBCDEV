from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from domain import Block
from UI.Widgets import BlockPropertyWidget, WorkspaceFrameWidget, WorkspaceTreePanelWidget
from UI.themes import initialize_widget_primitives


class CharacterWorkspacePanel(QWidget):
    """Character workspace panel composed in a reusable frame layout."""

    relative_path_changed = Signal(str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._frame = WorkspaceFrameWidget(self)
        self._tree_panel = WorkspaceTreePanelWidget(
            workspace_role="characters_root",
            root_block_id="blk_characters_root",
            title="CHARACTERS TREE",
            parent=self._frame,
        )
        self._tree_panel.set_header_visible(False)
        self._property_widget = BlockPropertyWidget(self._frame)
        self._property_widget.relative_path_changed.connect(self.relative_path_changed.emit)
        self._workzone_placeholder = QWidget(self._frame)

        top_bar = QWidget(self._frame)
        top_bar.setProperty("panelAlt", True)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(9, 9, 9, 9)
        top_layout.setSpacing(9)
        self._toolbar_label = QLabel("CHARACTERS TOOLBAR AREA", top_bar)
        self._toolbar_label.setProperty("section", True)
        top_layout.addWidget(self._toolbar_label, 0, Qt.AlignLeft)
        top_layout.addStretch(1)

        bottom_bar = QWidget(self._frame)
        bottom_bar.setProperty("panelAlt", True)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(9, 9, 9, 9)
        bottom_layout.setSpacing(9)
        self._message_label = QLabel("Character workspace ready.", bottom_bar)
        self._message_label.setProperty("muted", True)
        self._message_label.setProperty("technical", True)
        bottom_layout.addWidget(self._message_label, 0, Qt.AlignLeft)
        bottom_layout.addStretch(1)

        self._frame.set_top_widget(top_bar)
        self._frame.set_bottom_widget(bottom_bar)
        self._frame.set_left_widget(self._tree_panel)
        self._frame.set_workzone_widget(self._workzone_placeholder)
        self._frame.set_workzone_panel_enabled(False)
        self._frame.set_right_widget(self._property_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._frame, 1)

        self._tree_panel.block_selected.connect(self._on_tree_block_selected)
        initialize_widget_primitives(self)

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None) -> None:
        self._tree_panel.set_blocks(blocks, project_root=project_root)
        self._property_widget.set_block(None)

    def set_message(self, message: str) -> None:
        self._message_label.setText(message.strip())

    def set_block_relative_path(self, *, block_id: str, container_id: str, relative_path: str) -> bool:
        return self._tree_panel.set_block_relative_path(
            block_id=block_id,
            container_id=container_id,
            relative_path=relative_path,
        )

    def _on_tree_block_selected(self, block: Block | None, container_id: str) -> None:
        normalized_container_id = container_id.strip() or None
        self._property_widget.set_block(block, container_id=normalized_container_id)
