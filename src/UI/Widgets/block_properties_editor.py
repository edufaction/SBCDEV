from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHeaderView, QLineEdit, QStyledItemDelegate, QTextEdit, QTreeView, QVBoxLayout, QWidget

from domain import Block, InputConnection
from UI.themes import active_theme_tokens_ref, initialize_widget_primitives

ROLE_FIELD_KEY = Qt.UserRole + 610
ROLE_EDITOR_KIND = Qt.UserRole + 611
ROLE_MULTILINE = Qt.UserRole + 612
ROLE_EDITABLE_VALUE = Qt.UserRole + 613

_ICONS_DIR = Path(__file__).resolve().parents[2] / "icons"
_GROUP_ICON_NAMES: dict[str, str] = {
    "general": "project_file_description.svg",
    "text": "actions_text_plus.svg",
    "prompt": "story_world_message_star.svg",
    "context": "project_folder_root.svg",
    "relations": "actions_link_plus.svg",
    "content": "graph_data_file_chart.svg",
}


@dataclass(frozen=True)
class PropertyGroupSpec:
    id: str
    label: str
    order: int
    expanded: bool = True


@dataclass(frozen=True)
class PropertyFieldSpec:
    key: str
    label: str
    group: str
    editable: bool = False
    multiline: bool = False
    editor_kind: str = "line"


GROUP_SPECS: tuple[PropertyGroupSpec, ...] = (
    PropertyGroupSpec(id="general", label="General", order=10),
    PropertyGroupSpec(id="text", label="Text", order=20),
    PropertyGroupSpec(id="prompt", label="Prompt", order=30),
    PropertyGroupSpec(id="context", label="Context", order=40),
    PropertyGroupSpec(id="relations", label="Relations", order=50),
    PropertyGroupSpec(id="content", label="Content", order=60),
)

FIELD_SPECS: tuple[PropertyFieldSpec, ...] = (
    PropertyFieldSpec(key="name", label="Name", group="general", editable=True),
    PropertyFieldSpec(key="id", label="Id", group="general"),
    PropertyFieldSpec(key="type", label="Type", group="general"),
    PropertyFieldSpec(key="profile", label="Profile", group="general"),
    PropertyFieldSpec(key="domain", label="Domain", group="general"),
    PropertyFieldSpec(key="access_mode", label="Access", group="general"),
    PropertyFieldSpec(key="shared", label="Shared", group="general"),
    PropertyFieldSpec(key="functional_name", label="Functional Name", group="general", editable=True),
    PropertyFieldSpec(key="description", label="Description", group="text", editable=True, multiline=True, editor_kind="multiline"),
    PropertyFieldSpec(key="comment", label="Comment", group="text", editable=True, multiline=True, editor_kind="multiline"),
    PropertyFieldSpec(key="prompt_ref", label="Prompt Ref", group="prompt", editable=True, multiline=True, editor_kind="multiline"),
    PropertyFieldSpec(
        key="prompt_generated",
        label="Prompt Generated",
        group="prompt",
        editable=True,
        multiline=True,
        editor_kind="multiline",
    ),
    PropertyFieldSpec(key="container_path", label="Container Path", group="context", editable=True),
    PropertyFieldSpec(key="source", label="Source", group="context"),
    PropertyFieldSpec(key="provenance", label="Provenance", group="context", multiline=True),
    PropertyFieldSpec(key="tags", label="Tags", group="relations", editable=True),
    PropertyFieldSpec(key="contains", label="Contains", group="relations", multiline=True),
    PropertyFieldSpec(key="inputs", label="Inputs", group="relations", multiline=True),
    PropertyFieldSpec(key="content_json", label="JSON Preview", group="content", multiline=True),
)

FIELD_SPECS_BY_KEY = {field.key: field for field in FIELD_SPECS}


class PropertyValueDelegate(QStyledItemDelegate):
    """Lightweight delegate for inline editing in the properties tree."""

    def __init__(self, theme_tokens: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme_tokens = dict(theme_tokens)

    def createEditor(self, parent, option, index):  # noqa: N802 (Qt naming)
        if index.column() != 1:
            return None
        if not bool(index.flags() & Qt.ItemIsEditable):
            return None
        editor_kind = str(index.data(ROLE_EDITOR_KIND) or "line")
        editor_style = (
            "padding: 6px 8px;"
            f"background-color: {self._theme_tokens.get('surface_container_highest', '#28303a')};"
            f"color: {self._theme_tokens.get('on_surface', '#f3f5f8')};"
            f"border: 1px solid {self._theme_tokens.get('primary', '#6777DF')};"
            "border-radius: 8px;"
        )
        if editor_kind == "multiline":
            editor = QTextEdit(parent)
            editor.setAcceptRichText(False)
            editor.setTabChangesFocus(True)
            editor.setMinimumHeight(92)
            editor.setStyleSheet(editor_style)
            return editor
        editor = QLineEdit(parent)
        editor.setMinimumHeight(34)
        editor.setTextMargins(8, 4, 8, 4)
        editor.setStyleSheet(editor_style)
        return editor

    def setEditorData(self, editor, index) -> None:  # noqa: N802 (Qt naming)
        value = str(index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or "")
        if isinstance(editor, QTextEdit):
            editor.setPlainText(value)
            return
        if isinstance(editor, QLineEdit):
            editor.setText(value)
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index) -> None:  # noqa: N802 (Qt naming)
        if isinstance(editor, QTextEdit):
            model.setData(index, editor.toPlainText(), Qt.EditRole)
            return
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.EditRole)
            return
        super().setModelData(editor, model, index)

    def sizeHint(self, option, index):  # noqa: N802 (Qt naming)
        base = super().sizeHint(option, index)
        minimum_height = 34 if bool(index.data(ROLE_EDITABLE_VALUE)) else 28
        if index.column() != 1 or not bool(index.data(ROLE_MULTILINE)):
            return QSize(base.width(), max(base.height(), minimum_height))
        text = str(index.data(Qt.DisplayRole) or "")
        line_count = min(8, max(3, text.count("\n") + 1))
        return QSize(base.width(), max(base.height(), 38 + ((line_count - 1) * 18)))

    def updateEditorGeometry(self, editor, option, index) -> None:  # noqa: N802 (Qt naming)
        rect = option.rect.adjusted(4, 4, -4, -4)
        if bool(index.data(ROLE_MULTILINE)):
            rect.setHeight(max(rect.height(), 88))
        else:
            rect.setHeight(max(rect.height(), 32))
        editor.setGeometry(rect)


class BlockPropertiesEditor(QWidget):
    """Tree-based editor for one selected block."""

    property_change_requested = Signal(dict)
    relative_path_changed = Signal(str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._theme_tokens = dict(active_theme_tokens_ref())
        self._current_block: Block | None = None
        self._current_block_id: str | None = None
        self._current_container_id: str | None = None
        self._rebuilding_model = False
        self._items_by_key: dict[str, QStandardItem] = {}
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._readonly_value_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self._readonly_value_font.setPointSize(max(10, self._readonly_value_font.pointSize()))
        self._readonly_value_font.setStyleHint(QFont.Monospace)
        self._readonly_value_font.setFixedPitch(True)
        self._editable_value_font = QFont(self.font())
        self._editable_value_font.setWeight(QFont.DemiBold)

        self._tree_view = QTreeView(self)
        self._tree_view.setRootIsDecorated(True)
        self._tree_view.setAlternatingRowColors(False)
        self._tree_view.setWordWrap(True)
        self._tree_view.setUniformRowHeights(False)
        self._tree_view.setIconSize(QSize(16, 16))
        self._tree_view.setIndentation(14)
        self._tree_view.setEditTriggers(
            QTreeView.DoubleClicked | QTreeView.EditKeyPressed | QTreeView.SelectedClicked
        )
        self._tree_view.setSelectionBehavior(QTreeView.SelectRows)
        self._tree_view.setSelectionMode(QTreeView.SingleSelection)
        self._tree_view.header().setStretchLastSection(True)
        self._tree_view.header().setMinimumSectionSize(120)
        self._tree_view.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tree_view.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tree_view.header().resizeSection(0, 180)

        self._model = QStandardItemModel(0, 2, self)
        self._model.setHorizontalHeaderLabels(["Property", "Value"])
        self._model.itemChanged.connect(self._on_item_changed)
        self._tree_view.setModel(self._model)
        self._tree_view.setItemDelegateForColumn(1, PropertyValueDelegate(self._theme_tokens, self._tree_view))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._tree_view, 1)

        initialize_widget_primitives(self)

    def current_block_id(self) -> str | None:
        return self._current_block_id

    def set_block(self, block: Block | None, *, container_id: str | None = None) -> None:
        self._current_block = block
        self._current_block_id = block.id if block is not None else None
        self._current_container_id = str(container_id or "").strip() or self._infer_single_container_id(block)
        self._rebuild_model()

    def _rebuild_model(self) -> None:
        self._rebuilding_model = True
        self._items_by_key.clear()
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["Property", "Value"])

        if self._current_block is None:
            self._rebuilding_model = False
            return

        group_items: dict[str, QStandardItem] = {}
        for group in sorted(GROUP_SPECS, key=lambda item: item.order):
            label_item = QStandardItem(group.label)
            value_item = QStandardItem("")
            label_item.setEditable(False)
            value_item.setEditable(False)
            label_item.setSelectable(False)
            value_item.setSelectable(False)
            icon = self._group_icon(group.id)
            if not icon.isNull():
                label_item.setIcon(icon)
            self._model.appendRow([label_item, value_item])
            group_items[group.id] = label_item

        for field in FIELD_SPECS:
            block = self._current_block
            value_text = self._display_value_for_field(block, field.key)
            label_item = QStandardItem(field.label)
            value_item = QStandardItem(value_text)
            label_item.setEditable(False)
            label_item.setData(field.key, ROLE_FIELD_KEY)
            value_item.setData(field.key, ROLE_FIELD_KEY)
            value_item.setData(field.editor_kind, ROLE_EDITOR_KIND)
            value_item.setData(field.multiline, ROLE_MULTILINE)
            editable = self._is_field_editable(block, field.key)
            value_item.setData(editable, ROLE_EDITABLE_VALUE)
            value_item.setEditable(editable)
            if editable:
                value_item.setForeground(QColor(self._theme_tokens.get("primary_hover", "#8caef2")))
                value_item.setFont(self._editable_value_font)
                value_item.setToolTip("Double-click to edit.")
            else:
                value_item.setForeground(QColor(self._theme_tokens.get("on_surface_variant", "#a7afba")))
                value_item.setFont(self._readonly_value_font)
            if field.key == "container_path" and not editable:
                value_item.setToolTip(self._container_path_tooltip(block))
            group_items[field.group].appendRow([label_item, value_item])
            self._items_by_key[field.key] = value_item

        self._rebuilding_model = False
        for row in range(self._model.rowCount()):
            self._tree_view.expand(self._model.index(row, 0))

    def _on_item_changed(self, item: QStandardItem) -> None:
        if self._rebuilding_model or self._current_block is None:
            return
        if item.column() != 1:
            return
        key = str(item.data(ROLE_FIELD_KEY) or "").strip()
        if not key:
            return
        if key == "container_path":
            self._emit_relative_path_change(item)
            return
        if not self._is_field_editable(self._current_block, key):
            return

        payload_value = self._payload_value_for_field(key, item.text())
        current_value = self._current_payload_value(self._current_block, key)
        if payload_value == current_value:
            self._reset_item_text(item, self._display_value_for_field(self._current_block, key))
            return

        self._reset_item_text(item, self._display_text_for_payload_value(key, payload_value))
        self.property_change_requested.emit({"block_id": self._current_block.id, key: payload_value})

    def _emit_relative_path_change(self, item: QStandardItem) -> None:
        block = self._current_block
        if block is None:
            return
        block_id = block.id.strip()
        container_id = str(self._current_container_id or "").strip()
        if not block_id or not container_id:
            self._reset_item_text(item, self._display_value_for_field(block, "container_path"))
            return
        relative_path = self._normalize_relative_path(item.text())
        current_path = self._normalize_relative_path(str(block.container_paths.get(container_id, "") or ""))
        if relative_path == current_path:
            self._reset_item_text(item, current_path)
            return
        self._reset_item_text(item, relative_path)
        self.relative_path_changed.emit(block_id, container_id, relative_path)

    def _reset_item_text(self, item: QStandardItem, text: str) -> None:
        self._rebuilding_model = True
        item.setText(text)
        self._rebuilding_model = False

    def _display_value_for_field(self, block: Block, key: str) -> str:
        if key == "name":
            return block.name or ""
        if key == "id":
            return block.id
        if key == "type":
            return block.type.value
        if key == "profile":
            return block.profile or "-"
        if key == "domain":
            return block.domain.value
        if key == "access_mode":
            return block.access_mode.value.upper()
        if key == "shared":
            return "yes" if block.shared else "no"
        if key == "functional_name":
            return block.functional_name or ""
        if key == "description":
            return block.description or ""
        if key == "comment":
            return block.comment or ""
        if key == "prompt_ref":
            return block.prompt_ref or ""
        if key == "prompt_generated":
            return block.prompt_generated or ""
        if key == "container_path":
            container_id = str(self._current_container_id or "").strip()
            if not container_id:
                return ""
            return str(block.container_paths.get(container_id, "") or "")
        if key == "source":
            return self._source_label(block)
        if key == "provenance":
            return self._json_preview(block.provenance)
        if key == "tags":
            return ", ".join(block.tags)
        if key == "contains":
            return "\n".join(block.contains) if block.contains else "-"
        if key == "inputs":
            return self._inputs_label(block.inputs)
        if key == "content_json":
            return self._json_preview(block.content)
        return ""

    def _display_text_for_payload_value(self, key: str, value: object) -> str:
        if key == "tags" and isinstance(value, list):
            return ", ".join(value)
        return str(value or "")

    def _payload_value_for_field(self, key: str, raw_text: str) -> object:
        if key == "tags":
            return self._parse_tags(raw_text)
        return str(raw_text or "").strip()

    def _current_payload_value(self, block: Block, key: str) -> object:
        if key == "name":
            return block.name.strip()
        if key == "functional_name":
            return block.functional_name.strip()
        if key == "description":
            return block.description.strip()
        if key == "comment":
            return block.comment.strip()
        if key == "prompt_ref":
            return block.prompt_ref.strip()
        if key == "prompt_generated":
            return block.prompt_generated.strip()
        if key == "tags":
            return list(block.tags)
        return ""

    def _is_field_editable(self, block: Block, key: str) -> bool:
        spec = FIELD_SPECS_BY_KEY.get(key)
        if spec is None or not spec.editable:
            return False
        if not block.is_editable():
            return False
        if key == "container_path":
            return bool(str(self._current_container_id or "").strip())
        return True

    @staticmethod
    def _source_label(block: Block) -> str:
        provenance = block.provenance if isinstance(block.provenance, dict) else {}
        source_block_id = str(provenance.get("source_block_id", "") or "").strip()
        source_block_name = str(provenance.get("source_block_name", "") or "").strip()
        mount_id = str(provenance.get("mount_id", "") or "").strip()
        if not source_block_id:
            return "-"
        source_label = source_block_name or source_block_id
        if mount_id:
            return f"{source_label} (mount={mount_id})"
        return source_label

    @staticmethod
    def _inputs_label(inputs: list[InputConnection]) -> str:
        if not inputs:
            return "-"
        lines: list[str] = []
        for item in inputs:
            suffix = f" [{item.name}]" if item.name else ""
            lines.append(f"{item.port.value.upper()} <= {item.source_block_id}{suffix}")
        return "\n".join(lines)

    @staticmethod
    def _json_preview(value: object) -> str:
        if not value:
            return "-"
        try:
            return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
        except TypeError:
            return str(value)

    def _container_path_tooltip(self, block: Block) -> str:
        if block.is_link():
            return "Read-only block (LINK)."
        return "Select a block inside one container to edit its path."

    @staticmethod
    def _parse_tags(raw_text: str) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw_tag in str(raw_text or "").split(","):
            value = raw_tag.strip()
            if not value:
                continue
            normalized = value.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(value)
        return cleaned

    @staticmethod
    def _normalize_relative_path(value: str) -> str:
        text = str(value or "").replace("\\", "/")
        parts = [part.strip() for part in text.split("/") if part.strip()]
        cleaned = [part for part in parts if part not in {".", ".."}]
        return "/".join(cleaned)

    def _group_icon(self, group_id: str) -> QIcon:
        icon_name = _GROUP_ICON_NAMES.get(group_id, "")
        if not icon_name:
            return QIcon()
        color_hex = self._theme_tokens.get("on_surface_variant", self._theme_tokens.get("on_surface", "#f3f5f8"))
        return self._icon_for(icon_name, color_hex)

    def _icon_for(self, filename: str, color_hex: str) -> QIcon:
        key = (filename, color_hex)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        icon_path = _ICONS_DIR / filename
        if not icon_path.exists():
            return QIcon()

        renderer = QSvgRenderer(str(icon_path))
        if not renderer.isValid():
            return QIcon()

        icon = QIcon()
        tint = QColor(color_hex)
        for size in (16, 18, 20, 24):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            icon.addPixmap(pixmap)

        self._icon_cache[key] = icon
        return icon

    @staticmethod
    def _infer_single_container_id(block: Block | None) -> str | None:
        if block is None or not block.container_paths:
            return None
        keys = [str(key).strip() for key in block.container_paths.keys() if str(key).strip()]
        if len(keys) == 1:
            return keys[0]
        return None
