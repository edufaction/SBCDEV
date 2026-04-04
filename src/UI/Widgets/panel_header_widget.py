from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class PanelHeaderWidget(QWidget):
    """Reusable panel header with title/subtitle and optional right-side actions."""

    def __init__(
        self,
        title: str = "",
        *,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._icon_label = QLabel(self)
        self._icon_label.setVisible(False)

        self._title_label = QLabel(self)
        self._title_label.setProperty("section", True)

        self._subtitle_label = QLabel(self)
        self._subtitle_label.setProperty("muted", True)
        self._subtitle_label.setWordWrap(True)

        self._title_column = QWidget(self)
        title_layout = QVBoxLayout(self._title_column)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(3)
        title_layout.addWidget(self._title_label)
        title_layout.addWidget(self._subtitle_label)

        self._actions_container = QWidget(self)
        self._actions_layout = QHBoxLayout(self._actions_container)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(9)
        top_row.addWidget(self._icon_label)
        top_row.addWidget(self._title_column, 1)
        top_row.addWidget(self._actions_container, 0)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(0)
        root_layout.addLayout(top_row)

        self.set_title(title)
        self.set_subtitle(subtitle)

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    @property
    def subtitle_label(self) -> QLabel:
        return self._subtitle_label

    def set_title(self, text: str) -> None:
        self._title_label.setText((text or "").strip())

    def set_subtitle(self, text: str) -> None:
        clean = (text or "").strip()
        self._subtitle_label.setText(clean)
        self._subtitle_label.setVisible(bool(clean))

    def set_icon(self, icon: QIcon | QPixmap | None) -> None:
        if isinstance(icon, QIcon):
            pixmap = icon.pixmap(18, 18)
        elif isinstance(icon, QPixmap):
            pixmap = icon
        else:
            pixmap = QPixmap()

        self._icon_label.setPixmap(pixmap)
        self._icon_label.setVisible(not pixmap.isNull())

    def clear_actions(self) -> None:
        while self._actions_layout.count():
            item = self._actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def set_action_widgets(self, widgets: Iterable[QWidget]) -> None:
        self.clear_actions()
        for widget in widgets:
            self._actions_layout.addWidget(widget)

    def set_actions(self, actions: Iterable[QAction]) -> None:
        buttons: list[QToolButton] = []
        for action in actions:
            button = QToolButton(self._actions_container)
            button.setAutoRaise(True)
            button.setDefaultAction(action)
            buttons.append(button)
        self.set_action_widgets(buttons)
