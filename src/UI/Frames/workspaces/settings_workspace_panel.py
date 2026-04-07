from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from UI.Widgets import SettingsWorkspaceWidget
from UI.themes import initialize_widget_primitives


class SettingsWorkspacePanel(QWidget):
    """Settings workspace panel wrapper."""

    theme_changed = Signal(str)

    def __init__(self, settings_widget: SettingsWorkspaceWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._settings_widget = settings_widget

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._settings_widget, 1)
        self._settings_widget.theme_changed.connect(self.theme_changed.emit)
        initialize_widget_primitives(self)

    @property
    def settings_widget(self) -> SettingsWorkspaceWidget:
        return self._settings_widget

    def set_current_theme(self, theme_name: str) -> None:
        self._settings_widget.set_current_theme(theme_name)

    def set_storage_paths(
        self,
        *,
        projects_root: Path,
        user_libraries_root: Path,
        application_libraries_root: Path,
    ) -> None:
        self._settings_widget.set_storage_paths(
            projects_root=projects_root,
            user_libraries_root=user_libraries_root,
            application_libraries_root=application_libraries_root,
        )
