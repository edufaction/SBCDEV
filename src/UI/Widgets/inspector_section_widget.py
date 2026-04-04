from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget


class InspectorSectionWidget(QFrame):
    """Collapsible section container for inspector-style panels."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)

        self._header_button = QToolButton(self)
        self._header_button.setProperty("ghost", True)
        self._header_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._header_button.setArrowType(Qt.DownArrow)
        self._header_button.setCheckable(True)
        self._header_button.setChecked(True)
        self._header_button.clicked.connect(self._on_toggle)

        self._body = QWidget(self)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(9)
        layout.addWidget(self._header_button)
        layout.addWidget(self._body)

        self._content_widget: QWidget | None = None
        self.set_title(title)

    def set_title(self, text: str) -> None:
        self._header_button.setText((text or "").strip())

    def set_collapsed(self, value: bool) -> None:
        collapsed = bool(value)
        self._header_button.setChecked(not collapsed)
        self._body.setVisible(not collapsed)
        self._header_button.setArrowType(Qt.RightArrow if collapsed else Qt.DownArrow)

    def set_content_widget(self, widget: QWidget | None) -> None:
        if self._content_widget is not None:
            self._body_layout.removeWidget(self._content_widget)
            self._content_widget.setParent(None)
        self._content_widget = widget
        if widget is not None:
            self._body_layout.addWidget(widget)

    def _on_toggle(self, checked: bool) -> None:
        self.set_collapsed(not checked)
