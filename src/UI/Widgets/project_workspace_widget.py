from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from domain import BlockType
from UI.Widgets.media_preview_widget import MediaPreviewWidget
from UI.Widgets.panel_header_widget import PanelHeaderWidget
from UI.themes import initialize_widget_primitives


class ProjectWorkspaceWidget(QWidget):
    """Project workspace with actions and project metadata panel."""

    new_project_requested = Signal()
    open_project_requested = Signal()
    close_project_requested = Signal()
    project_tree_requested = Signal()
    select_visual_requested = Signal()
    save_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._project_path: Path | None = None
        self._preview_image_path_raw = ""

        self._header = PanelHeaderWidget(
            "PROJECT WORKSPACE",
            subtitle="Manage project identity, ownership, and summary.",
            parent=self,
        )
        # Compatibility aliases retained for existing tests/callers.
        self._header_label = self._header.title_label
        self._subtitle_label = self._header.subtitle_label

        self._actions_frame = QFrame(self)
        self._actions_frame.setProperty("panel", True)
        actions_layout = QHBoxLayout(self._actions_frame)
        actions_layout.setContentsMargins(9, 9, 9, 9)
        actions_layout.setSpacing(9)
        self._new_project_button = QPushButton("NEW PROJECT", self._actions_frame)
        self._new_project_button.setProperty("primary", True)
        self._open_project_button = QPushButton("OPEN PROJECT", self._actions_frame)
        self._open_project_button.setProperty("ghost", True)
        self._close_project_button = QPushButton("CLOSE PROJECT", self._actions_frame)
        self._close_project_button.setProperty("ghost", True)
        self._project_tree_button = QPushButton("PROJECT TREE", self._actions_frame)
        self._project_tree_button.setProperty("primary", True)
        self._select_visual_button = QPushButton("SELECT VISUAL", self._actions_frame)
        self._select_visual_button.setProperty("ghost", True)
        actions_layout.addWidget(self._new_project_button)
        actions_layout.addWidget(self._open_project_button)
        actions_layout.addWidget(self._close_project_button)
        actions_layout.addWidget(self._project_tree_button)
        actions_layout.addWidget(self._select_visual_button)
        actions_layout.addStretch(1)

        self._content_row = QWidget(self)
        content_row_layout = QHBoxLayout(self._content_row)
        content_row_layout.setContentsMargins(0, 0, 0, 0)
        content_row_layout.setSpacing(9)

        self._media_frame = QFrame(self._content_row)
        self._media_frame.setProperty("panel", True)
        media_layout = QVBoxLayout(self._media_frame)
        media_layout.setContentsMargins(9, 9, 9, 9)
        media_layout.setSpacing(9)

        self._media_preview = MediaPreviewWidget(self._media_frame)
        self._media_preview.set_placeholder("No image", "")
        self._media_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._preview_label = self._media_preview

        media_meta_holder = QWidget(self._media_frame)
        media_meta_form = QFormLayout(media_meta_holder)
        media_meta_form.setContentsMargins(0, 0, 0, 0)
        media_meta_form.setSpacing(8)
        media_meta_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        self._value_labels: dict[str, QLabel] = {}
        for key, title in (
            ("name", "Name"),
            ("created_at", "Created"),
            ("updated_at", "Modified"),
            ("project_path", "Path"),
            ("image_path", "Image"),
        ):
            value = QLabel("-", media_meta_holder)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if key in {"created_at", "updated_at", "project_path", "image_path"}:
                value.setProperty("technical", True)
            media_meta_form.addRow(f"{title}:", value)
            self._value_labels[key] = value

        media_layout.addWidget(self._media_preview, 1)
        media_layout.addWidget(media_meta_holder, 0)

        self._editor_frame = QFrame(self._content_row)
        self._editor_frame.setProperty("panel", True)
        editor_layout = QVBoxLayout(self._editor_frame)
        editor_layout.setContentsMargins(9, 9, 9, 9)
        editor_layout.setSpacing(9)
        editor_title = QLabel("PROJECT DETAILS", self._editor_frame)
        editor_title.setProperty("section", True)

        editor_form_holder = QWidget(self._editor_frame)
        editor_form = QFormLayout(editor_form_holder)
        editor_form.setContentsMargins(0, 0, 0, 0)
        editor_form.setSpacing(8)
        editor_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        self._author_name_edit = QLineEdit(self._editor_frame)
        self._author_name_edit.setPlaceholderText("Author name")
        self._author_email_edit = QLineEdit(self._editor_frame)
        self._author_email_edit.setPlaceholderText("author@email.com")
        editor_form.addRow("Author:", self._author_name_edit)
        editor_form.addRow("Author Email:", self._author_email_edit)

        self._description_label = QLabel("DESCRIPTION", self._editor_frame)
        self._description_label.setProperty("section", True)
        self._description_text = QTextEdit(self._editor_frame)
        self._description_text.setReadOnly(False)
        self._description_text.setMinimumHeight(120)
        self._save_button = QPushButton("Save", self._editor_frame)
        self._save_button.setProperty("primary", True)
        self._save_button.setFixedHeight(34)
        self._save_button.setMinimumWidth(120)
        self._save_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._save_status_label = QLabel("", self._editor_frame)
        self._save_status_label.setProperty("muted", True)
        self._save_status_label.setProperty("technical", True)
        save_row = QWidget(self._editor_frame)
        save_row_layout = QHBoxLayout(save_row)
        save_row_layout.setContentsMargins(0, 0, 0, 0)
        save_row_layout.setSpacing(9)
        save_row_layout.addWidget(self._save_status_label, 1)
        save_row_layout.addWidget(self._save_button, 0, Qt.AlignRight)

        editor_layout.addWidget(editor_title)
        editor_layout.addWidget(editor_form_holder)
        editor_layout.addWidget(self._description_label)
        editor_layout.addWidget(self._description_text, 1)
        editor_layout.addWidget(save_row)

        content_row_layout.addWidget(self._media_frame, 4)
        content_row_layout.addWidget(self._editor_frame, 5)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._actions_frame)
        root_layout.addWidget(self._content_row, 1)

        self._new_project_button.clicked.connect(self.new_project_requested.emit)
        self._open_project_button.clicked.connect(self.open_project_requested.emit)
        self._close_project_button.clicked.connect(self.close_project_requested.emit)
        self._project_tree_button.clicked.connect(self.project_tree_requested.emit)
        self._select_visual_button.clicked.connect(self.select_visual_requested.emit)
        self._save_button.clicked.connect(self._emit_save_requested)

        initialize_widget_primitives(self)
        self._save_button.setEnabled(False)

    def set_project_metadata(self, *, project_path: Path | None, metadata: dict | None) -> None:
        self._project_path = project_path
        data = dict(metadata or {})
        self._value_labels["name"].setText(str(data.get("name", "-") or "-"))
        self._value_labels["created_at"].setText(str(data.get("created_at", "-") or "-"))
        self._value_labels["updated_at"].setText(str(data.get("updated_at", "-") or "-"))
        self._value_labels["project_path"].setText(str(project_path or "-"))
        image_path_raw = str(data.get("preview_image_path", "") or "")
        self._value_labels["image_path"].setText(image_path_raw or "-")
        self._author_name_edit.setText(str(data.get("author_name", "") or ""))
        self._author_email_edit.setText(str(data.get("author_email", "") or ""))
        self._description_text.setPlainText(str(data.get("description", "") or ""))

        self._save_button.setEnabled(project_path is not None)
        self._close_project_button.setEnabled(project_path is not None)
        self._select_visual_button.setEnabled(project_path is not None)
        if image_path_raw != self._preview_image_path_raw:
            self._preview_image_path_raw = image_path_raw
        self._render_preview()

    def set_save_feedback(self, message: str) -> None:
        self._save_status_label.setText(message.strip())

    def _emit_save_requested(self) -> None:
        payload = {
            "author_name": self._author_name_edit.text().strip(),
            "author_email": self._author_email_edit.text().strip(),
            "description": self._description_text.toPlainText().strip(),
        }
        self.save_requested.emit(payload)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)

    def _render_preview(self) -> None:
        if not self._preview_image_path_raw:
            self._media_preview.clear()
            return

        self._media_preview.set_media(
            {
                "type": BlockType.IMAGE.value,
                "path": self._preview_image_path_raw,
                "project_root": self._project_path,
            }
        )
