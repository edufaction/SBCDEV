from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from UI.Widgets import ProjectWorkspaceWidget
from UI.themes import initialize_widget_primitives


class ProjectWorkspacePanel(QWidget):
    """Project workspace panel wrapper."""

    new_project_requested = Signal()
    open_project_requested = Signal()
    close_project_requested = Signal()
    project_tree_requested = Signal()
    select_visual_requested = Signal()
    save_requested = Signal(dict)

    def __init__(self, project_widget: ProjectWorkspaceWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._project_widget = project_widget

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._project_widget, 1)

        self._project_widget.new_project_requested.connect(self.new_project_requested.emit)
        self._project_widget.open_project_requested.connect(self.open_project_requested.emit)
        self._project_widget.close_project_requested.connect(self.close_project_requested.emit)
        self._project_widget.project_tree_requested.connect(self.project_tree_requested.emit)
        self._project_widget.select_visual_requested.connect(self.select_visual_requested.emit)
        self._project_widget.save_requested.connect(self.save_requested.emit)
        initialize_widget_primitives(self)

    @property
    def project_widget(self) -> ProjectWorkspaceWidget:
        return self._project_widget

    def set_project_metadata(self, *, project_path: Path | None, metadata: dict | None) -> None:
        self._project_widget.set_project_metadata(project_path=project_path, metadata=metadata)

    def set_save_feedback(self, message: str) -> None:
        self._project_widget.set_save_feedback(message)
