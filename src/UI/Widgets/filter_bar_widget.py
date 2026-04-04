from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget


class FilterBarWidget(QFrame):
    """Reusable horizontal container for search and filter controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._search_widget: QWidget | None = None
        self._filter_widgets: list[QWidget] = []

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(9, 9, 9, 9)
        self._layout.setSpacing(9)

    def set_search_widget(self, widget: QWidget | None, *, stretch: int = 2) -> None:
        if self._search_widget is not None:
            self._layout.removeWidget(self._search_widget)
            self._search_widget.setParent(None)
        self._search_widget = widget
        if widget is not None:
            self._layout.insertWidget(0, widget, stretch)

    def add_filter_widget(self, widget: QWidget, *, stretch: int = 1) -> None:
        self._filter_widgets.append(widget)
        self._layout.addWidget(widget, stretch)

    def clear_filter_widgets(self) -> None:
        for widget in self._filter_widgets:
            self._layout.removeWidget(widget)
            widget.setParent(None)
        self._filter_widgets.clear()
