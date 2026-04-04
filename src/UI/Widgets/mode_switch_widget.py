from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class ModeSwitchWidget(QWidget):
    """Compact switch to toggle between list/grid display modes."""

    mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None, *, default_mode: str = "list") -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._mode = ""

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for key, label in (("list", "List"), ("grid", "Grid")):
            btn = QPushButton(label, self)
            btn.setProperty("ghost", True)
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.clicked.connect(lambda checked=False, mode=key: self.set_mode(mode))
            self._group.addButton(btn)
            self._buttons[key] = btn
            layout.addWidget(btn)

        self.set_mode(default_mode if default_mode in self._buttons else "list")

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in self._buttons:
            return
        if mode == self._mode:
            return

        self._mode = mode
        for key, button in self._buttons.items():
            is_active = key == mode
            button.setChecked(is_active)
            button.setProperty("primary", is_active)
            button.setProperty("ghost", not is_active)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        self.mode_changed.emit(mode)
