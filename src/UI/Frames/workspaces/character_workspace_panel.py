from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from application import CharacterWorkspaceService
from domain import Block, BlockType
from UI.Widgets import (
    BlockPropertyWidget,
    WorkspaceFrameWidget,
    WorkspaceGraphWidget,
    WorkspaceToolbarWidget,
    WorkspaceTreePanelWidget,
)
from UI.themes import active_theme_tokens_ref, initialize_widget_primitives

_ICONS_DIR = Path(__file__).resolve().parents[3] / "icons"


class CharacterWorkspacePanel(QWidget):
    """Character workspace panel composed in a reusable frame layout."""

    relative_path_changed = Signal(str, str, str)
    block_update_requested = Signal(dict)
    graph_link_create_requested = Signal(str, str, str, str, str)
    graph_link_delete_requested = Signal(str, str, str, str, str)
    graph_block_move_requested = Signal(str, str, float, float)
    graph_block_resize_requested = Signal(str, str, float, float)
    graph_layout_initialize_requested = Signal(str, object)
    graph_files_drop_requested = Signal(str, str, object, float, float)
    character_create_requested = Signal(str)
    character_update_requested = Signal(dict)
    note_create_requested = Signal(str)
    block_files_add_requested = Signal(str, object)
    placeholder_block_create_requested = Signal(str)
    block_delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._character_service = CharacterWorkspaceService()

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
        self._property_widget.property_change_requested.connect(self.block_update_requested.emit)
        self._graph_widget = WorkspaceGraphWidget(self._frame)
        self._blocks: list[Block] = []
        self._blocks_by_id: dict[str, Block] = {}
        self._selected_character_id = ""
        self._selected_property_container_id = ""

        top_bar = WorkspaceToolbarWidget("CHARACTER TOOLS", parent=self._frame)
        self._create_character_button = self._create_toolbar_button(
            top_bar,
            icon_name="story_world_users_plus.svg",
            tooltip="Create a new character",
            style_property="primary",
        )
        self._create_note_button = self._create_toolbar_button(
            top_bar,
            icon_name="project_notes.svg",
            tooltip="Create a new note in the active container",
        )
        self._add_block_button = self._create_toolbar_button(
            top_bar,
            icon_name="project_file_plus.svg",
            tooltip="Add a block to the active character form",
        )
        self._add_block_button.setPopupMode(QToolButton.InstantPopup)
        self._add_block_menu = QMenu(self._add_block_button)
        self._import_files_action = QAction("Import From Disk", self._add_block_menu)
        self._placeholder_action = QAction("Add Empty Placeholder", self._add_block_menu)
        self._add_block_menu.addAction(self._import_files_action)
        self._add_block_menu.addAction(self._placeholder_action)
        self._add_block_button.setMenu(self._add_block_menu)
        self._character_name_edit = QLineEdit(top_bar)
        self._character_name_edit.setPlaceholderText("Selected character name")
        self._character_tags_edit = QLineEdit(top_bar)
        self._character_tags_edit.setPlaceholderText("Tags (comma separated)")
        self._save_character_button = self._create_toolbar_button(
            top_bar,
            icon_name="project_file_check.svg",
            tooltip="Save the selected character",
        )
        self._delete_block_button = self._create_toolbar_button(
            top_bar,
            icon_name="actions_trash_x.svg",
            tooltip="Delete the selected block",
            style_property="danger",
        )
        self._character_summary_label = QLabel("0 character(s)", top_bar)
        self._character_summary_label.setProperty("muted", True)
        self._character_summary_label.setProperty("technical", True)
        top_bar.set_leading_widgets(
            [
                self._create_character_button,
                self._create_note_button,
                self._add_block_button,
                self._character_name_edit,
                self._character_tags_edit,
                self._save_character_button,
                self._delete_block_button,
            ]
        )
        top_bar.set_trailing_widgets([self._character_summary_label])

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
        self._graph_widget.graph_block_resize_requested.connect(self.graph_block_resize_requested.emit)
        self._graph_widget.graph_layout_initialize_requested.connect(self.graph_layout_initialize_requested.emit)
        self._graph_widget.graph_files_drop_requested.connect(self.graph_files_drop_requested.emit)
        self._graph_widget.block_update_requested.connect(self.block_update_requested.emit)
        self._create_character_button.clicked.connect(self._prompt_create_character)
        self._create_note_button.clicked.connect(self._emit_note_create_request)
        self._import_files_action.triggered.connect(self._prompt_add_block_files)
        self._placeholder_action.triggered.connect(self._emit_placeholder_block_create_request)
        self._save_character_button.clicked.connect(self._emit_character_update)
        self._delete_block_button.clicked.connect(self._emit_delete_block_request)
        initialize_widget_primitives(self)
        self._set_character_editor_enabled(False)
        self._refresh_toolbar_action_state()

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
        self._refresh_character_toolbar()
        self._refresh_toolbar_action_state()

    def set_message(self, message: str) -> None:
        self._message_label.setText(message.strip())

    def confirm_block_deletion(self, *, block_name: str, descendant_names: list[str]) -> bool:
        message = f"Delete '{block_name}'?"
        if descendant_names:
            lines = "\n".join(f"- {name}" for name in descendant_names)
            message = f"{message}\n\nContained block(s) that will also be deleted:\n{lines}"
        answer = QMessageBox.question(
            self,
            "Confirm Block Deletion",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

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
        self._graph_widget.set_active_block(block.id)
        self._load_character_editor(block)
        self._refresh_toolbar_action_state()
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
        self._graph_widget.set_active_block(block.id if block is not None else "")
        self._load_character_editor(block)
        self._refresh_toolbar_action_state()

    def _on_graph_node_selected(self, block_id: str) -> None:
        block = self._blocks_by_id.get(str(block_id).strip())
        active_container_id = self._graph_widget.active_container_id().strip() or None
        property_container_id = self._resolve_property_container_id(block, active_container_id)
        self._selected_property_container_id = property_container_id
        self._property_widget.set_block(block, container_id=property_container_id or None)
        self._graph_widget.set_active_block(block.id if block is not None else "")
        self._load_character_editor(block)
        self._refresh_toolbar_action_state()

    def _prompt_create_character(self) -> None:
        character_name, accepted = QInputDialog.getText(self, "New Character", "Character name:")
        if not accepted:
            return
        resolved_name = character_name.strip()
        if not resolved_name:
            return
        self.character_create_requested.emit(resolved_name)

    def _emit_character_update(self) -> None:
        character = self._selected_character()
        if character is None:
            return
        payload = {
            "character_id": character.id,
            "name": self._character_name_edit.text().strip(),
            "description": character.description,
            "functional_name": character.functional_name,
            "comment": character.comment,
            "tags": self._parse_tags(self._character_tags_edit.text()),
        }
        self.character_update_requested.emit(payload)

    def _emit_note_create_request(self) -> None:
        container_id = self._graph_widget.active_container_id().strip() or self._default_graph_container_id()
        if not container_id:
            self.set_message("Select a container first.")
            return
        self.note_create_requested.emit(container_id)

    def _prompt_add_block_files(self) -> None:
        container = self._active_container()
        if container is None or not self._can_add_non_container_blocks(container):
            self.set_message("Select a character form to add blocks.")
            return
        file_paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Import Blocks Into Character Form",
            "",
            "All Supported Files (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.mp4 *.mov *.m4v *.avi *.mkv *.webm *.wav *.mp3 *.aac *.m4a *.flac *.ogg *.txt *.md *.markdown *.json *.yaml *.yml *.prompt);;All Files (*)",
        )
        if not file_paths:
            return
        self.block_files_add_requested.emit(container.id, list(file_paths))

    def _emit_placeholder_block_create_request(self) -> None:
        container = self._active_container()
        if container is None or not self._can_add_non_container_blocks(container):
            self.set_message("Select a character form to add blocks.")
            return
        self.placeholder_block_create_requested.emit(container.id)

    def _emit_delete_block_request(self) -> None:
        block = self._selected_deletable_block()
        if block is None:
            self.set_message("Select a deletable block first.")
            return
        descendants = self._collect_descendant_names(block.id)
        if not self.confirm_block_deletion(block_name=block.name or block.id, descendant_names=descendants):
            return
        self.block_delete_requested.emit(block.id)

    def _refresh_character_toolbar(self) -> None:
        characters = self._character_service.list_characters(self._blocks)
        preview = ", ".join(character.name or character.id for character in characters[:3])
        suffix = "..." if len(characters) > 3 else ""
        summary = f"{len(characters)} character(s)"
        if preview:
            summary = f"{summary} | {preview}{suffix}"
        self._character_summary_label.setText(summary)
        selected = self._selected_character()
        self._load_character_editor(selected)
        self._refresh_toolbar_action_state()

    def _load_character_editor(self, block: Block | None) -> None:
        character = self._resolve_character_from_block(block)
        self._selected_character_id = character.id if character is not None else ""
        self._set_character_editor_enabled(character is not None)
        if character is None:
            self._character_name_edit.setText("")
            self._character_tags_edit.setText("")
            return
        self._character_name_edit.setText(character.name or "")
        self._character_tags_edit.setText(", ".join(character.tags))

    def _selected_character(self) -> Block | None:
        target = self._selected_character_id.strip()
        if not target:
            return None
        block = self._blocks_by_id.get(target)
        if block is None or block.type != BlockType.CONTAINER or block.profile != "character":
            return None
        return block

    def _resolve_character_from_block(self, block: Block | None) -> Block | None:
        if block is None:
            return None
        if block.type == BlockType.CONTAINER and block.profile == "character":
            return block
        if block.profile == "character_form":
            for candidate in self._blocks:
                if candidate.type != BlockType.CONTAINER or candidate.profile != "character":
                    continue
                if block.id in candidate.contains:
                    return candidate
        return None

    def _set_character_editor_enabled(self, enabled: bool) -> None:
        self._character_name_edit.setEnabled(enabled)
        self._character_tags_edit.setEnabled(enabled)
        self._save_character_button.setEnabled(enabled)

    def _refresh_toolbar_action_state(self) -> None:
        container = self._active_container()
        can_add = self._can_add_non_container_blocks(container)
        deletable_block = self._selected_deletable_block()
        self._add_block_button.setEnabled(can_add)
        self._delete_block_button.setEnabled(deletable_block is not None)
        if can_add:
            self._add_block_button.setToolTip("Import a media block or add an empty placeholder to the current character form.")
        else:
            self._add_block_button.setToolTip("Select a CHARACTER FORM container to add blocks.")
        if deletable_block is not None:
            self._delete_block_button.setToolTip(f"Delete '{deletable_block.name or deletable_block.id}'.")
        else:
            self._delete_block_button.setToolTip("Select a non-root block to delete.")

    def _active_container(self) -> Block | None:
        container_id = self._graph_widget.active_container_id().strip()
        candidate = self._blocks_by_id.get(container_id)
        if candidate is None or candidate.type != BlockType.CONTAINER:
            return None
        return candidate

    @staticmethod
    def _icon_for(path: Path, color_hex: str) -> QIcon:
        if not path.exists():
            return QIcon()
        renderer = QSvgRenderer(str(path))
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
        return icon

    def _create_toolbar_button(
        self,
        parent: QWidget,
        *,
        icon_name: str,
        tooltip: str,
        style_property: str | None = None,
    ) -> QToolButton:
        button = QToolButton(parent)
        button.setText("")
        button.setProperty("iconOnly", True)
        if style_property:
            button.setProperty(style_property, True)
        else:
            button.setProperty("ghost", True)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setIcon(self._icon_for(_ICONS_DIR / icon_name, self._button_icon_color(style_property)))
        button.setIconSize(QSize(16, 16))
        button.setMinimumSize(QSize(30, 30))
        return button

    @staticmethod
    def _button_icon_color(style_property: str | None) -> str:
        tokens = active_theme_tokens_ref()
        if style_property == "primary":
            return tokens.get("on_primary_fixed", "#081019")
        if style_property == "danger":
            return tokens.get("danger", "#e05252")
        return tokens.get("on_surface", "#f3f5f8")

    @staticmethod
    def _can_add_non_container_blocks(container: Block | None) -> bool:
        if container is None:
            return False
        return container.profile == "character_form"

    def _selected_deletable_block(self) -> Block | None:
        candidate_id = str(self.current_block_id() or self.current_tree_block_id() or "").strip()
        if not candidate_id:
            return None
        candidate = self._blocks_by_id.get(candidate_id)
        if candidate is None:
            return None
        if candidate.type == BlockType.CONTAINER and candidate.profile == "workspace_root":
            return None
        return candidate

    def _collect_descendant_names(self, root_block_id: str) -> list[str]:
        root = self._blocks_by_id.get(root_block_id)
        if root is None or root.type != BlockType.CONTAINER:
            return []
        descendants: list[str] = []
        pending = list(reversed(root.contains))
        seen: set[str] = set()
        while pending:
            current_id = pending.pop()
            if current_id in seen:
                continue
            seen.add(current_id)
            current = self._blocks_by_id.get(current_id)
            if current is None:
                continue
            descendants.append(current.name or current.id)
            if current.type == BlockType.CONTAINER and current.contains:
                pending.extend(reversed(current.contains))
        return descendants

    @staticmethod
    def _parse_tags(text: str) -> list[str]:
        return [item.strip() for item in str(text or "").split(",") if item.strip()]

    def _default_graph_container_id(self) -> str:
        candidate = self._blocks_by_id.get("blk_characters_root")
        if candidate is not None and candidate.type == BlockType.CONTAINER:
            return candidate.id
        for block in self._blocks:
            if block.type != BlockType.CONTAINER:
                continue
            role = block.as_container().workspace_role
            if role == "characters_root":
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
