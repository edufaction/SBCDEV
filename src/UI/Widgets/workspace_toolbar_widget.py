from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class WorkspaceToolbarWidget(QWidget):
    """Reusable top toolbar row for workspace panels."""

    def __init__(self, title: str = "", *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._title_label = QLabel(self)
        self._title_label.setProperty("section", True)

        self._leading_host = QWidget(self)
        self._leading_layout = QHBoxLayout(self._leading_host)
        self._leading_layout.setContentsMargins(0, 0, 0, 0)
        self._leading_layout.setSpacing(9)

        self._trailing_host = QWidget(self)
        self._trailing_layout = QHBoxLayout(self._trailing_host)
        self._trailing_layout.setContentsMargins(0, 0, 0, 0)
        self._trailing_layout.setSpacing(9)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(9)
        layout.addWidget(self._title_label, 0)
        layout.addWidget(self._leading_host, 1)
        layout.addStretch(1)
        layout.addWidget(self._trailing_host, 0)

        self.set_title(title)

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    def set_title(self, text: str) -> None:
        self._title_label.setText((text or "").strip())

    def set_leading_widgets(self, widgets: Iterable[QWidget]) -> None:
        self._replace_widgets(self._leading_layout, widgets)

    def set_trailing_widgets(self, widgets: Iterable[QWidget]) -> None:
        self._replace_widgets(self._trailing_layout, widgets)

    @staticmethod
    def _replace_widgets(layout: QHBoxLayout, widgets: Iterable[QWidget]) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        for widget in widgets:
            layout.addWidget(widget)
