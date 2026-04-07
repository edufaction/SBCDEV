from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from UI.Widgets import EmptyStateWidget, PanelHeaderWidget
from UI.themes import initialize_widget_primitives


class LibraryWorkspacePanel(QWidget):
    """Library workspace panel skeleton."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._header = PanelHeaderWidget("LIBRARY WORKSPACE", parent=self)
        self._empty = EmptyStateWidget(
            "Library workspace",
            description="Dedicated Library panel scaffold is ready for integration.",
            parent=self,
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._empty, 1)
        initialize_widget_primitives(self)
