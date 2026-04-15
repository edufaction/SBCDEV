from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from domain import Block, BlockType
from UI.Widgets import BlockPropertyWidget, WorkspaceFrameWidget, WorkspaceGraphWidget, WorkspaceTreePanelWidget
from UI.themes import initialize_widget_primitives


class StoryWorkspacePanel(QWidget):
    """Story workspace panel composed in a reusable frame layout."""

    relative_path_changed = Signal(str, str, str)
    block_update_requested = Signal(dict)
    graph_link_create_requested = Signal(str, str, str, str, str)
    graph_link_delete_requested = Signal(str, str, str, str, str)
    graph_block_move_requested = Signal(str, str, float, float)
    graph_layout_initialize_requested = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._frame = WorkspaceFrameWidget(self)
        self._tree_panel = WorkspaceTreePanelWidget(
            workspace_role="story_root",
            root_block_id="blk_story_root",
            title="STORY TREE",
            parent=self._frame,
        )
        self._tree_panel.set_header_visible(False)
        self._property_widget = BlockPropertyWidget(self._frame)
        self._property_widget.relative_path_changed.connect(self.relative_path_changed.emit)
        self._property_widget.property_change_requested.connect(self.block_update_requested.emit)
        self._graph_widget = WorkspaceGraphWidget(self._frame)
        self._blocks: list[Block] = []
        self._blocks_by_id: dict[str, Block] = {}
        self._selected_property_container_id = ""

        top_bar = QWidget(self._frame)
        top_bar.setProperty("panelAlt", True)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(9, 9, 9, 9)
        top_layout.setSpacing(9)
        self._toolbar_label = QLabel("STORY TOOLBAR AREA", top_bar)
        self._toolbar_label.setProperty("section", True)
        top_layout.addWidget(self._toolbar_label, 0, Qt.AlignLeft)
        top_layout.addStretch(1)

        bottom_bar = QWidget(self._frame)
        bottom_bar.setProperty("panelAlt", True)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(9, 9, 9, 9)
        bottom_layout.setSpacing(9)
        self._message_label = QLabel("Story workspace ready.", bottom_bar)
        self._message_label.setProperty("muted", True)
        self._message_label.setProperty("technical", True)
        bottom_layout.addWidget(self._message_label, 0, Qt.AlignLeft)
        bottom_layout.addStretch(1)

        self._frame.set_top_widget(top_bar)
        self._frame.set_bottom_widget(bottom_bar)
        self._frame.set_left_widget(self._tree_panel)
        self._frame.set_workzone_widget(self._graph_widget)
        self._frame.set_workzone_panel_enabled(True)
        self._frame.set_right_widget(self._property_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._frame, 1)

        self._tree_panel.block_selected.connect(self._on_tree_block_selected)
        self._graph_widget.node_selected.connect(self._on_graph_node_selected)
        self._graph_widget.link_create_requested.connect(self.graph_link_create_requested.emit)
        self._graph_widget.link_delete_requested.connect(self.graph_link_delete_requested.emit)
        self._graph_widget.graph_block_move_requested.connect(self.graph_block_move_requested.emit)
        self._graph_widget.graph_layout_initialize_requested.connect(self.graph_layout_initialize_requested.emit)
        initialize_widget_primitives(self)

    def set_blocks(
        self,
        blocks: list[Block],
        *,
        project_root: Path | None,
        active_container_id: str | None = None,
    ) -> None:
        self._blocks = list(blocks)
        self._blocks_by_id = {block.id: block for block in self._blocks}
        self._tree_panel.set_blocks(blocks, project_root=project_root)
        self._graph_widget.set_blocks(blocks, project_root=project_root)
        preferred_container_id = self._resolve_preferred_container_id(active_container_id)
        self._graph_widget.set_active_container(preferred_container_id or self._default_graph_container_id())
        self._property_widget.set_block(None)

    def set_message(self, message: str) -> None:
        self._message_label.setText(message.strip())

    def current_block_id(self) -> str | None:
        return self._property_widget.current_block_id()

    def current_tree_block_id(self) -> str | None:
        return self._tree_panel.selected_block_id()

    def current_property_container_id(self) -> str | None:
        normalized = self._selected_property_container_id.strip()
        return normalized or None

    def select_block(self, block_id: str, *, container_id: str | None = None) -> bool:
        normalized = str(block_id or "").strip()
        if not normalized:
            return False
        if self._tree_panel.select_block(normalized):
            return True
        return self.inspect_block(normalized, container_id=container_id)

    def select_tree_block(self, block_id: str) -> bool:
        normalized = str(block_id or "").strip()
        if not normalized:
            return False
        return self._tree_panel.select_block(normalized)

    def inspect_block(self, block_id: str, *, container_id: str | None = None) -> bool:
        normalized = str(block_id or "").strip()
        if not normalized:
            return False
        block = self._blocks_by_id.get(normalized)
        if block is None:
            return False
        property_container_id = self._resolve_property_container_id(block, container_id)
        self._selected_property_container_id = property_container_id
        self._property_widget.set_block(block, container_id=property_container_id or None)
        return True

    def set_block_relative_path(self, *, block_id: str, container_id: str, relative_path: str) -> bool:
        return self._tree_panel.set_block_relative_path(
            block_id=block_id,
            container_id=container_id,
            relative_path=relative_path,
        )

    def _on_tree_block_selected(self, block: Block | None, container_id: str) -> None:
        normalized_container_id = container_id.strip() or None
        property_container_id = self._resolve_property_container_id(block, normalized_container_id)
        self._selected_property_container_id = property_container_id
        self._property_widget.set_block(block, container_id=property_container_id or None)
        self._graph_widget.set_active_container(
            self._graph_container_for_selection(block=block, container_id=normalized_container_id)
        )

    def _on_graph_node_selected(self, block_id: str) -> None:
        block = self._blocks_by_id.get(str(block_id).strip())
        active_container_id = self._graph_widget.active_container_id().strip() or None
        property_container_id = self._resolve_property_container_id(block, active_container_id)
        self._selected_property_container_id = property_container_id
        self._property_widget.set_block(block, container_id=property_container_id or None)

    def _default_graph_container_id(self) -> str:
        candidate = self._blocks_by_id.get("blk_story_root")
        if candidate is not None and candidate.type == BlockType.CONTAINER:
            return candidate.id
        for block in self._blocks:
            if block.type != BlockType.CONTAINER:
                continue
            role = str(block.content.get("workspace_role", "") or "").strip().lower()
            if role == "story_root":
                return block.id
        return ""

    def _resolve_preferred_container_id(self, container_id: str | None) -> str:
        normalized = str(container_id or "").strip()
        if not normalized:
            return ""
        candidate = self._blocks_by_id.get(normalized)
        if candidate is None or candidate.type != BlockType.CONTAINER:
            return ""
        return candidate.id

    def _graph_container_for_selection(self, *, block: Block | None, container_id: str | None) -> str:
        if block is not None and block.type == BlockType.CONTAINER:
            return block.id

        candidate_id = str(container_id or "").strip()
        if candidate_id:
            candidate = self._blocks_by_id.get(candidate_id)
            if candidate is not None and candidate.type == BlockType.CONTAINER:
                return candidate.id

        if block is not None:
            for key in block.container_paths.keys():
                normalized = str(key).strip()
                if not normalized:
                    continue
                candidate = self._blocks_by_id.get(normalized)
                if candidate is not None and candidate.type == BlockType.CONTAINER:
                    return candidate.id

        return self._default_graph_container_id()

    def _resolve_property_container_id(self, block: Block | None, container_id: str | None) -> str:
        if block is None:
            return ""

        candidate_id = str(container_id or "").strip()
        if candidate_id and candidate_id != block.id:
            candidate = self._blocks_by_id.get(candidate_id)
            if candidate is not None and candidate.type == BlockType.CONTAINER:
                return candidate.id

        stored_id = self._selected_property_container_id.strip()
        if stored_id and stored_id != block.id:
            candidate = self._blocks_by_id.get(stored_id)
            if candidate is not None and candidate.type == BlockType.CONTAINER and stored_id in block.container_paths:
                return candidate.id

        container_ids = [
            normalized
            for raw in block.container_paths.keys()
            if (normalized := str(raw).strip()) and normalized != block.id
        ]
        if len(container_ids) == 1:
            return container_ids[0]
        return ""
