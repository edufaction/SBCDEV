from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from domain import Block
from UI.Widgets.empty_state_widget import EmptyStateWidget
from UI.Widgets.inspector_section_widget import InspectorSectionWidget
from UI.Widgets.panel_header_widget import PanelHeaderWidget
from UI.themes import initialize_widget_primitives


class BlockPropertyWidget(QWidget):
    """Right-side property inspector for a selected block."""

    relative_path_changed = Signal(str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._current_block_id: str | None = None
        self._current_container_id: str | None = None
        self._updating_path_ui = False

        self._header = PanelHeaderWidget("BLOCK PROPERTIES", parent=self)
        self._header_label = self._header.title_label
        self._title_label = QLabel("No block selected", self)
        self._title_label.setProperty("title", True)
        self._title_label.setWordWrap(True)
        self._empty_state = EmptyStateWidget(
            "No block selected",
            description="Click a block in the list to display its properties.",
            parent=self,
        )
        # Compatibility alias retained.
        self._hint_label = self._empty_state

        details_widget = QWidget(self)
        details_layout = QFormLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)
        details_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)

        self._value_labels: dict[str, QLabel] = {}
        for key in ("id", "type", "profile", "domain", "access", "source", "tags", "contains", "inputs", "shared"):
            label = QLabel("-", details_widget)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setWordWrap(True)
            if key in {"id", "domain", "access", "source"}:
                label.setProperty("technical", True)
            details_layout.addRow(f"{key.upper()}:", label)
            self._value_labels[key] = label

        self._content_preview = QPlainTextEdit(self)
        self._content_preview.setReadOnly(True)
        self._content_preview.setMinimumHeight(160)

        path_editor_holder = QWidget(self)
        path_editor_layout = QHBoxLayout(path_editor_holder)
        path_editor_layout.setContentsMargins(0, 0, 0, 0)
        path_editor_layout.setSpacing(8)
        self._relative_path_edit = QLineEdit(path_editor_holder)
        self._relative_path_edit.setPlaceholderText("Relative path in container (e.g. Principaux/Heros/Mechants)")
        self._relative_path_apply_button = QPushButton("Apply", path_editor_holder)
        self._relative_path_apply_button.setProperty("ghost", True)
        self._relative_path_apply_button.setFixedHeight(30)
        path_editor_layout.addWidget(self._relative_path_edit, 1)
        path_editor_layout.addWidget(self._relative_path_apply_button, 0)

        self._details_section = InspectorSectionWidget("DETAILS", self)
        self._details_section.set_content_widget(details_widget)
        self._path_section = InspectorSectionWidget("CONTAINER PATH", self)
        self._path_section.set_content_widget(path_editor_holder)
        self._content_section = InspectorSectionWidget("CONTENT", self)
        self._content_section.set_content_widget(self._content_preview)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._title_label)
        root_layout.addWidget(self._empty_state)
        root_layout.addWidget(self._details_section)
        root_layout.addWidget(self._path_section)
        root_layout.addWidget(self._content_section, 1)

        self._relative_path_apply_button.clicked.connect(self._emit_relative_path_change)
        self._relative_path_edit.editingFinished.connect(self._emit_relative_path_change)

        initialize_widget_primitives(self)

    def current_block_id(self) -> str | None:
        return self._current_block_id

    def set_block(self, block: Block | None, *, container_id: str | None = None) -> None:
        self._current_block_id = block.id if block is not None else None
        self._current_container_id = None
        if block is None:
            self._title_label.setText("No block selected")
            self._empty_state.setVisible(True)
            self._details_section.setEnabled(False)
            self._path_section.setEnabled(False)
            self._content_section.setEnabled(False)
            for label in self._value_labels.values():
                label.setText("-")
            self._updating_path_ui = True
            self._relative_path_edit.setText("")
            self._relative_path_edit.setEnabled(False)
            self._relative_path_apply_button.setEnabled(False)
            self._updating_path_ui = False
            self._content_preview.setPlainText("")
            return

        self._title_label.setText(block.name or block.id)
        self._empty_state.setVisible(False)
        self._details_section.setEnabled(True)
        self._content_section.setEnabled(True)
        self._value_labels["id"].setText(block.id)
        self._value_labels["type"].setText(block.type.value)
        self._value_labels["profile"].setText(block.profile or "-")
        self._value_labels["domain"].setText(block.domain.value)
        self._value_labels["access"].setText(block.access_mode.value.upper())
        source_label = "-"
        provenance = block.provenance if isinstance(block.provenance, dict) else {}
        source_block_id = str(provenance.get("source_block_id", "") or "").strip()
        source_block_name = str(provenance.get("source_block_name", "") or "").strip()
        mount_id = str(provenance.get("mount_id", "") or "").strip()
        if source_block_id:
            source_label = source_block_name or source_block_id
            if mount_id:
                source_label = f"{source_label} (mount={mount_id})"
        self._value_labels["source"].setText(source_label)
        self._value_labels["tags"].setText(", ".join(block.tags) if block.tags else "-")
        self._value_labels["contains"].setText(", ".join(block.contains) if block.contains else "-")
        self._value_labels["inputs"].setText(str(len(block.inputs)))
        self._value_labels["shared"].setText("yes" if block.shared else "no")
        self._refresh_relative_path_editor(block, container_id=container_id)

        content_text = ""
        if block.content:
            try:
                content_text = json.dumps(block.content, indent=2, sort_keys=True, ensure_ascii=False)
            except TypeError:
                content_text = str(block.content)
        self._content_preview.setPlainText(content_text)

    def _refresh_relative_path_editor(self, block: Block, *, container_id: str | None) -> None:
        resolved_container_id = (container_id or "").strip() or self._infer_single_container_id(block)
        self._current_container_id = resolved_container_id or None
        editable = bool(self._current_container_id) and block.is_editable()

        self._path_section.setEnabled(True)
        self._updating_path_ui = True
        self._relative_path_edit.setEnabled(editable)
        self._relative_path_apply_button.setEnabled(editable)
        if editable and self._current_container_id is not None:
            current_value = str(block.container_paths.get(self._current_container_id, "") or "")
            self._relative_path_edit.setText(current_value)
            self._relative_path_edit.setPlaceholderText("Relative path in container (e.g. Principaux/Heros/Mechants)")
        else:
            self._relative_path_edit.setText("")
            if block.is_link():
                self._relative_path_edit.setPlaceholderText("Read-only block (LINK)")
            else:
                self._relative_path_edit.setPlaceholderText("Select a block inside one container to edit its path")
        self._updating_path_ui = False

    @staticmethod
    def _infer_single_container_id(block: Block) -> str:
        if not block.container_paths:
            return ""
        keys = [str(key).strip() for key in block.container_paths.keys() if str(key).strip()]
        if len(keys) == 1:
            return keys[0]
        return ""

    def _emit_relative_path_change(self) -> None:
        if self._updating_path_ui:
            return
        block_id = (self._current_block_id or "").strip()
        container_id = (self._current_container_id or "").strip()
        if not block_id or not container_id:
            return
        relative_path = self._normalize_relative_path(self._relative_path_edit.text())
        self.relative_path_changed.emit(block_id, container_id, relative_path)

    @staticmethod
    def _normalize_relative_path(value: str) -> str:
        text = str(value or "").replace("\\", "/")
        parts = [part.strip() for part in text.split("/") if part.strip()]
        cleaned = [part for part in parts if part not in {".", ".."}]
        return "/".join(cleaned)
