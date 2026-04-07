from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from domain import Block, BlockType
from UI.Widgets.filter_bar_widget import FilterBarWidget
from UI.Widgets.free_tree_widget import FreeTreeWidget
from UI.Widgets.panel_header_widget import PanelHeaderWidget
from UI.Widgets.search_bar_widget import SearchBarWidget
from UI.themes import initialize_widget_primitives


class WorkspaceTreePanelWidget(QWidget):
    """Read-only FreeTree panel scoped to one workspace root, with filters."""

    block_selected = Signal(object, str)

    def __init__(
        self,
        *,
        workspace_role: str,
        title: str,
        root_block_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._workspace_role = workspace_role.strip().lower()
        self._root_block_id = (root_block_id or "").strip()
        self._blocks: list[Block] = []
        self._project_root: Path | None = None

        self._header = PanelHeaderWidget(title, parent=self)
        self._filter_bar = FilterBarWidget(self)
        self._tag_search = SearchBarWidget(self, placeholder="Filter by tag")
        self._type_combo = QComboBox(self)
        self._type_combo.setProperty("commandBar", True)
        self._type_combo.setMinimumWidth(140)
        self._type_combo.addItem("ALL TYPES", "")
        self._filter_bar.set_search_widget(self._tag_search, stretch=2)
        self._filter_bar.add_filter_widget(self._type_combo, stretch=1)

        self._status_label = QLabel("", self)
        self._status_label.setProperty("technical", True)
        self._status_label.setProperty("muted", True)

        self._tree_widget = FreeTreeWidget(self)
        self._tree_widget.set_interactive(False)
        self._tree_widget.set_header_visible(False)
        self._tree_widget.set_actions_visible(False)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._filter_bar)
        root_layout.addWidget(self._status_label)
        root_layout.addWidget(self._tree_widget, 1)

        self._tree_widget.block_selected.connect(self.block_selected.emit)
        self._tag_search.text_changed.connect(lambda *_: self._apply_filters())
        self._type_combo.currentIndexChanged.connect(lambda *_: self._apply_filters())

        initialize_widget_primitives(self)
        self._apply_filters()

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None) -> None:
        self._blocks = list(blocks)
        self._project_root = project_root
        self._refresh_type_choices()
        self._apply_filters()

    def set_header_visible(self, visible: bool) -> None:
        self._header.setVisible(bool(visible))

    def set_block_relative_path(self, *, block_id: str, container_id: str, relative_path: str) -> bool:
        changed = self._tree_widget.set_block_relative_path(block_id, container_id, relative_path)
        if changed:
            self._apply_filters()
        return changed

    def _apply_filters(self) -> None:
        root, workspace_blocks = self._workspace_slice()
        if root is None:
            self._status_label.setText(f"Workspace root '{self._workspace_role}' not found.")
            self._tree_widget.set_blocks([], project_root=self._project_root)
            return

        filtered = self._filtered_blocks(root=root, workspace_blocks=workspace_blocks)
        self._tree_widget.set_blocks(filtered, project_root=self._project_root)

        non_root_count = len([block for block in filtered if block.id != root.id])
        if non_root_count == 0 and self._has_active_filters():
            self._status_label.setText("No block matches current filters.")
            return
        self._status_label.setText(f"{non_root_count} block(s) in current view.")

    def _workspace_slice(self) -> tuple[Block | None, list[Block]]:
        root = self._find_workspace_root(self._blocks)
        if root is None:
            return None, []

        by_id = {block.id: block for block in self._blocks}
        allowed_ids = {root.id}
        pending = [child_id for child_id in root.contains if child_id in by_id]
        while pending:
            current_id = pending.pop()
            if current_id in allowed_ids:
                continue
            allowed_ids.add(current_id)
            current = by_id.get(current_id)
            if current is None:
                continue
            pending.extend(child_id for child_id in current.contains if child_id in by_id)

        ordered = [block for block in self._blocks if block.id in allowed_ids]
        return root, ordered

    def _filtered_blocks(self, *, root: Block, workspace_blocks: list[Block]) -> list[Block]:
        selected_type = str(self._type_combo.currentData() or "").strip().lower()
        tag_filter = self._tag_search.text().strip().lower()
        if not selected_type and not tag_filter:
            return workspace_blocks

        by_id = {block.id: block for block in workspace_blocks}
        parent_by_child: dict[str, str] = {}
        for block in workspace_blocks:
            if block.type != BlockType.CONTAINER:
                continue
            for child_id in block.contains:
                if child_id in by_id and child_id not in parent_by_child:
                    parent_by_child[child_id] = block.id

        include_ids: set[str] = {root.id}

        def add_with_ancestors(block_id: str) -> None:
            cursor = block_id
            seen: set[str] = set()
            while cursor and cursor not in seen:
                seen.add(cursor)
                include_ids.add(cursor)
                cursor = parent_by_child.get(cursor, "")

        def matches(block: Block) -> bool:
            if selected_type and block.type.value != selected_type:
                return False
            if tag_filter:
                lowered_tags = [str(tag).strip().lower() for tag in block.tags]
                if not any(tag_filter in tag for tag in lowered_tags):
                    return False
            return True

        for block in workspace_blocks:
            if block.id == root.id:
                continue
            if matches(block):
                add_with_ancestors(block.id)

        return [block for block in workspace_blocks if block.id in include_ids]

    def _refresh_type_choices(self) -> None:
        root, workspace_blocks = self._workspace_slice()
        _ = root
        previous = str(self._type_combo.currentData() or "")
        available = sorted({block.type.value for block in workspace_blocks if block.id})

        self._type_combo.blockSignals(True)
        self._type_combo.clear()
        self._type_combo.addItem("ALL TYPES", "")
        for value in available:
            self._type_combo.addItem(value.upper(), value)
        restore_index = self._type_combo.findData(previous)
        self._type_combo.setCurrentIndex(restore_index if restore_index >= 0 else 0)
        self._type_combo.blockSignals(False)

    def _find_workspace_root(self, blocks: list[Block]) -> Block | None:
        by_id = {block.id: block for block in blocks}
        for block in blocks:
            if block.type != BlockType.CONTAINER or block.profile != "workspace_root":
                continue
            role = str(block.content.get("workspace_role", "") or "").strip().lower()
            if role == self._workspace_role:
                return block
        if self._root_block_id:
            candidate = by_id.get(self._root_block_id)
            if candidate is not None and candidate.type == BlockType.CONTAINER:
                return candidate
        return None

    def _has_active_filters(self) -> bool:
        return bool(str(self._type_combo.currentData() or "").strip() or self._tag_search.text().strip())
