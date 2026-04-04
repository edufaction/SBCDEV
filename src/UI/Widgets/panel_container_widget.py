from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget


class PanelContainerWidget(QWidget):
    """Standard container with header/body/footer slots."""

    def __init__(self, parent: QWidget | None = None, *, panel_alt: bool = False) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt" if panel_alt else "panel", True)

        self._header_widget: QWidget | None = None
        self._body_widget: QWidget | None = None
        self._footer_widget: QWidget | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(9)

    def _remove_slot(self, widget: QWidget | None) -> None:
        if widget is None:
            return
        self._layout.removeWidget(widget)
        widget.setParent(None)

    def set_header_widget(self, widget: QWidget | None) -> None:
        self._remove_slot(self._header_widget)
        self._header_widget = widget
        if widget is not None:
            self._layout.insertWidget(0, widget, 0)

    def set_body_widget(self, widget: QWidget | None) -> None:
        self._remove_slot(self._body_widget)
        self._body_widget = widget
        if widget is not None:
            index = 1 if self._header_widget is not None else 0
            self._layout.insertWidget(index, widget, 1)

    def set_footer_widget(self, widget: QWidget | None) -> None:
        self._remove_slot(self._footer_widget)
        self._footer_widget = widget
        if widget is not None:
            self._layout.addWidget(widget, 0)
