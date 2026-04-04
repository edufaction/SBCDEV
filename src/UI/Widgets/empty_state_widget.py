from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class EmptyStateWidget(QWidget):
    """Reusable empty-state panel for blank/none-selected situations."""

    action_requested = Signal()

    def __init__(
        self,
        title: str = "",
        *,
        description: str = "",
        action_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._title_label = QLabel(self)
        self._title_label.setProperty("section", True)
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setWordWrap(True)

        self._description_label = QLabel(self)
        self._description_label.setProperty("muted", True)
        self._description_label.setAlignment(Qt.AlignCenter)
        self._description_label.setWordWrap(True)

        self._action_button = QPushButton(self)
        self._action_button.setProperty("ghost", True)
        self._action_button.setVisible(False)
        self._action_button.clicked.connect(self.action_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)
        layout.addStretch(1)
        layout.addWidget(self._title_label)
        layout.addWidget(self._description_label)
        layout.addWidget(self._action_button, 0, Qt.AlignHCenter)
        layout.addStretch(1)

        self.set_message(title, description=description)
        self.set_action(action_text)

    def set_message(self, title: str, *, description: str = "") -> None:
        self._title_label.setText((title or "").strip())
        clean_description = (description or "").strip()
        self._description_label.setText(clean_description)
        self._description_label.setVisible(bool(clean_description))

    def set_action(self, text: str = "") -> None:
        clean = (text or "").strip()
        self._action_button.setText(clean)
        self._action_button.setVisible(bool(clean))
