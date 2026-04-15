from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from application import StoryShotService
from domain import Block
from UI.Widgets.empty_state_widget import EmptyStateWidget
from UI.Widgets.inspector_section_widget import InspectorSectionWidget
from UI.Widgets.panel_header_widget import PanelHeaderWidget
from UI.themes import initialize_widget_primitives

ROLE_BLOCK_ID = Qt.UserRole + 480


class StoryShotWorkspaceWidget(QWidget):
    """Story planner workspace focused on shot creation and shot metadata edit."""

    shot_selected = Signal(str)
    shot_update_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._service = StoryShotService()
        self._blocks: list[Block] = []
        self._selected_shot_id = ""

        self._header = PanelHeaderWidget(
            "STORY SHOTS",
            subtitle="Create and organize shot containers used by Story planning.",
            parent=self,
        )

        self._status_label = QLabel("", self)
        self._status_label.setProperty("technical", True)
        self._status_label.setProperty("muted", True)

        self._shots_list = QListWidget(self)
        self._shots_list.setSelectionMode(QListWidget.SingleSelection)

        self._empty_state = EmptyStateWidget(
            "No shots yet",
            description="Create your first shot to start structuring the Story planner.",
            parent=self,
        )

        inspector_body = QWidget(self)
        inspector_form = QFormLayout(inspector_body)
        inspector_form.setContentsMargins(0, 0, 0, 0)
        inspector_form.setSpacing(8)
        inspector_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        self._shot_name_edit = QLineEdit(inspector_body)
        self._shot_functional_name_edit = QLineEdit(inspector_body)
        self._shot_functional_name_edit.setPlaceholderText("shot_opening_alley")
        self._shot_tags_edit = QLineEdit(inspector_body)
        self._shot_tags_edit.setPlaceholderText("story, shot, intro")
        self._shot_description_edit = QTextEdit(inspector_body)
        self._shot_description_edit.setMinimumHeight(100)
        self._shot_comment_edit = QTextEdit(inspector_body)
        self._shot_comment_edit.setMinimumHeight(70)
        inspector_form.addRow("Name:", self._shot_name_edit)
        inspector_form.addRow("Functional:", self._shot_functional_name_edit)
        inspector_form.addRow("Tags:", self._shot_tags_edit)
        inspector_form.addRow("Description:", self._shot_description_edit)
        inspector_form.addRow("Comment:", self._shot_comment_edit)

        self._save_button = QPushButton("Save Shot", self)
        self._save_button.setProperty("primary", True)
        inspector_section_widget = QWidget(self)
        inspector_section_layout = QVBoxLayout(inspector_section_widget)
        inspector_section_layout.setContentsMargins(0, 0, 0, 0)
        inspector_section_layout.setSpacing(9)
        inspector_section_layout.addWidget(inspector_body)
        inspector_section_layout.addWidget(self._save_button, 0, Qt.AlignRight)

        self._inspector_section = InspectorSectionWidget("SHOT INSPECTOR", self)
        self._inspector_section.set_content_widget(inspector_section_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._status_label)
        root_layout.addWidget(self._empty_state)
        root_layout.addWidget(self._shots_list, 1)
        root_layout.addWidget(self._inspector_section)

        self._shots_list.itemSelectionChanged.connect(self._handle_selection_changed)
        self._save_button.clicked.connect(self._emit_update_shot)

        initialize_widget_primitives(self)
        self._set_editor_enabled(False)
        self._refresh_view()

    def set_blocks(self, blocks: list[Block]) -> None:
        self._blocks = list(blocks)
        self._refresh_view()

    def set_feedback(self, message: str) -> None:
        self._status_label.setText(message.strip())

    def _handle_selection_changed(self) -> None:
        item = self._shots_list.currentItem()
        if item is None:
            self._selected_shot_id = ""
            self._set_editor_enabled(False)
            self._load_editor_from_selected()
            return
        block_id = str(item.data(ROLE_BLOCK_ID) or "").strip()
        self._selected_shot_id = block_id
        self._set_editor_enabled(bool(block_id))
        self._load_editor_from_selected()
        if block_id:
            self.shot_selected.emit(block_id)

    def _emit_update_shot(self) -> None:
        if not self._selected_shot_id:
            return
        payload = {
            "shot_id": self._selected_shot_id,
            "name": self._shot_name_edit.text().strip(),
            "functional_name": self._shot_functional_name_edit.text().strip(),
            "description": self._shot_description_edit.toPlainText().strip(),
            "comment": self._shot_comment_edit.toPlainText().strip(),
            "tags": self._parse_tags(self._shot_tags_edit.text()),
        }
        self.shot_update_requested.emit(payload)

    def _refresh_view(self) -> None:
        shots = self._service.list_shots(self._blocks)
        current_selected = self._selected_shot_id

        self._shots_list.clear()
        selected_exists = False
        for shot in shots:
            label = shot.name or shot.id
            item = QListWidgetItem(label)
            item.setData(ROLE_BLOCK_ID, shot.id)
            item.setToolTip(shot.id)
            self._shots_list.addItem(item)
            if shot.id == current_selected:
                selected_exists = True

        has_shots = bool(shots)
        self._empty_state.setVisible(not has_shots)
        self._shots_list.setVisible(has_shots)

        has_story_root = self._has_story_root()
        if not has_story_root:
            self._status_label.setText("Story root not found in this project.")
        elif not self._status_label.text().strip():
            self._status_label.setText(f"{len(shots)} shot(s)")

        if selected_exists:
            self._select_shot_in_list(current_selected)
        elif shots:
            self._shots_list.setCurrentRow(0)
        else:
            self._selected_shot_id = ""
            self._set_editor_enabled(False)
            self._load_editor_from_selected()

    def _load_editor_from_selected(self) -> None:
        shot = self._selected_shot()
        if shot is None:
            self._shot_name_edit.setText("")
            self._shot_functional_name_edit.setText("")
            self._shot_tags_edit.setText("")
            self._shot_description_edit.setPlainText("")
            self._shot_comment_edit.setPlainText("")
            return
        self._shot_name_edit.setText(shot.name or "")
        self._shot_functional_name_edit.setText(shot.functional_name or "")
        self._shot_tags_edit.setText(", ".join(shot.tags))
        self._shot_description_edit.setPlainText(shot.description or "")
        self._shot_comment_edit.setPlainText(shot.comment or "")

    def _selected_shot(self) -> Block | None:
        if not self._selected_shot_id:
            return None
        for block in self._blocks:
            if block.id == self._selected_shot_id and block.profile == "shot":
                return block
        return None

    def _select_shot_in_list(self, shot_id: str) -> None:
        for index in range(self._shots_list.count()):
            item = self._shots_list.item(index)
            if item is None:
                continue
            block_id = str(item.data(ROLE_BLOCK_ID) or "").strip()
            if block_id == shot_id:
                self._shots_list.setCurrentItem(item)
                return

    def _set_editor_enabled(self, enabled: bool) -> None:
        self._inspector_section.setEnabled(enabled)
        self._shot_name_edit.setEnabled(enabled)
        self._shot_functional_name_edit.setEnabled(enabled)
        self._shot_tags_edit.setEnabled(enabled)
        self._shot_description_edit.setEnabled(enabled)
        self._shot_comment_edit.setEnabled(enabled)
        self._save_button.setEnabled(enabled)

    def _has_story_root(self) -> bool:
        for block in self._blocks:
            if block.profile != "workspace_root":
                continue
            role = block.as_container().workspace_role
            if role == "story_root":
                return True
        return any(block.id == "blk_story_root" for block in self._blocks)

    @staticmethod
    def _parse_tags(text: str) -> list[str]:
        parts = [item.strip() for item in str(text or "").split(",")]
        return [item for item in parts if item]
