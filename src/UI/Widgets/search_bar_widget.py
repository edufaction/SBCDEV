from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget


class SearchBarWidget(QWidget):
    """Standardized search bar wrapper with explicit signals."""

    text_changed = Signal(str)
    search_submitted = Signal(str)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None, *, placeholder: str = "") -> None:
        super().__init__(parent)
        self._had_text = False

        self._line_edit = QLineEdit(self)
        self._line_edit.setProperty("searchBar", True)
        self._line_edit.setClearButtonEnabled(True)
        self._line_edit.setPlaceholderText(placeholder)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._line_edit)

        self._line_edit.textChanged.connect(self._on_text_changed)
        self._line_edit.returnPressed.connect(self._on_return_pressed)

    @property
    def line_edit(self) -> QLineEdit:
        return self._line_edit

    def set_placeholder(self, text: str) -> None:
        self._line_edit.setPlaceholderText(text)

    def text(self) -> str:
        return self._line_edit.text()

    def set_text(self, text: str) -> None:
        self._line_edit.setText(text)

    def _on_text_changed(self, text: str) -> None:
        has_text = bool(text.strip())
        if self._had_text and not has_text:
            self.clear_requested.emit()
        self._had_text = has_text
        self.text_changed.emit(text)

    def _on_return_pressed(self) -> None:
        self.search_submitted.emit(self._line_edit.text())
