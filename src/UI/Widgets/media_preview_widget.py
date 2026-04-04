from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QStackedLayout, QWidget

from domain import BlockType
from UI.Widgets.empty_state_widget import EmptyStateWidget
from UI.Widgets.thumbnail_utils import extract_video_preview, load_image_safe, resolve_media_path


class MediaPreviewWidget(QWidget):
    """Generic preview widget for image/video/text with empty fallback state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setStackingMode(QStackedLayout.StackOne)

        self._empty_state = EmptyStateWidget("No media", parent=self)
        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setProperty("panelAlt", True)
        self._image_label.setMinimumSize(320, 180)
        self._image_label.setMaximumHeight(225)

        self._text_preview = QPlainTextEdit(self)
        self._text_preview.setReadOnly(True)
        self._text_preview.setMinimumHeight(180)

        self._stack.addWidget(self._empty_state)
        self._stack.addWidget(self._image_label)
        self._stack.addWidget(self._text_preview)

        self._source_pixmap = QPixmap()
        self._empty_title = "No media"
        self._empty_description = ""
        self.clear()

    def set_placeholder(self, title: str, description: str = "") -> None:
        self._empty_title = (title or "").strip() or "No media"
        self._empty_description = (description or "").strip()
        if self._stack.currentWidget() is self._empty_state:
            self._empty_state.set_message(self._empty_title, description=self._empty_description)

    def clear(self) -> None:
        self._source_pixmap = QPixmap()
        self._image_label.clear()
        self._text_preview.clear()
        self._empty_state.set_message(self._empty_title, description=self._empty_description)
        self._stack.setCurrentWidget(self._empty_state)

    def set_media(self, media_descriptor: dict | None) -> None:
        if not media_descriptor:
            self.clear()
            return

        media_type = str(media_descriptor.get("type") or "").lower()
        if media_type in {BlockType.TEXT.value, BlockType.PROMPT.value, "text"}:
            text = str(media_descriptor.get("text") or "").strip()
            if not text:
                self.clear()
                return
            self._text_preview.setPlainText(text)
            self._stack.setCurrentWidget(self._text_preview)
            return

        pixmap = self._resolve_pixmap(media_descriptor)
        if pixmap is None or pixmap.isNull():
            self.clear()
            return

        self._source_pixmap = pixmap
        self._update_scaled_pixmap()
        self._stack.setCurrentWidget(self._image_label)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _resolve_pixmap(self, media_descriptor: dict) -> QPixmap | None:
        direct_path = str(media_descriptor.get("path") or "").strip()
        project_root_raw = media_descriptor.get("project_root")
        project_root = Path(project_root_raw) if isinstance(project_root_raw, (str, Path)) and project_root_raw else None

        media_path: Path | None = None
        if direct_path:
            candidate = Path(direct_path)
            if not candidate.is_absolute() and project_root is not None:
                candidate = (project_root / candidate).resolve()
            if candidate.exists():
                media_path = candidate

        if media_path is None:
            content = media_descriptor.get("content")
            if isinstance(content, dict):
                media_path = resolve_media_path(content, project_root)

        if media_path is None:
            return None

        type_value = str(media_descriptor.get("type") or "").lower()
        if type_value == BlockType.VIDEO.value:
            preview_path = extract_video_preview(media_path, project_root=project_root)
            if preview_path is None:
                return None
            image = load_image_safe(preview_path)
        else:
            image = load_image_safe(media_path)

        if image is None or image.isNull():
            return None
        return QPixmap.fromImage(image)

    def _update_scaled_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        scaled = self._source_pixmap.scaled(self._image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._image_label.setPixmap(scaled)
