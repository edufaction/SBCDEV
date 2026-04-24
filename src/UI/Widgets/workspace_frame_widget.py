from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSplitter, QVBoxLayout, QWidget
from UI.themes import active_theme_tokens_ref


_ICONS_DIR = Path(__file__).resolve().parents[2] / "icons"
_ZONE_TOGGLE_ICONS = {
    "LEFT": _ICONS_DIR / "navigation_arrows_left.svg",
    "RIGHT": _ICONS_DIR / "navigation_arrows_right.svg",
    "BOTTOM": _ICONS_DIR / "navigation_arrows_down.svg",
}


class WorkspaceFrameWidget(QWidget):
    """Reusable workspace frame with top/middle/bottom and left/work/right areas.

    Layout structure:
    - Vertical splitter:
      1) top zone
      2) middle zone
      3) bottom zone
    - Middle zone is an horizontal splitter:
      1) left
      2) workzone (center)
      3) right
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)

        self._top_host = self._new_host_widget()
        self._middle_host = self._new_host_widget()
        self._bottom_host = self._new_host_widget()

        self._left_host = self._new_host_widget()
        self._workzone_host = self._new_host_widget()
        self._right_host = self._new_host_widget()

        self._top_content_host = QWidget(self._top_host)
        self._top_toggles_host = QWidget(self._top_host)
        self._top_toggles_host.setProperty("panelAlt", True)
        self._left_toggle_button = self._create_zone_toggle_button("LEFT", self._on_left_toggled)
        self._right_toggle_button = self._create_zone_toggle_button("RIGHT", self._on_right_toggled)
        self._bottom_toggle_button = self._create_zone_toggle_button("BOTTOM", self._on_bottom_toggled)

        toggles_layout = QHBoxLayout(self._top_toggles_host)
        toggles_layout.setContentsMargins(0, 0, 0, 0)
        toggles_layout.setSpacing(6)
        toggles_layout.addWidget(self._left_toggle_button)
        toggles_layout.addWidget(self._right_toggle_button)
        toggles_layout.addWidget(self._bottom_toggle_button)

        top_layout = QHBoxLayout(self._top_host)
        top_layout.setContentsMargins(6, 6, 6, 6)
        top_layout.setSpacing(9)
        top_layout.addWidget(self._top_content_host, 1)
        top_layout.addWidget(self._top_toggles_host, 0, Qt.AlignRight | Qt.AlignVCenter)

        self._middle_splitter = QSplitter(Qt.Horizontal, self._middle_host)
        self._middle_splitter.setChildrenCollapsible(False)
        self._middle_splitter.addWidget(self._left_host)
        self._middle_splitter.addWidget(self._workzone_host)
        self._middle_splitter.addWidget(self._right_host)
        self._middle_splitter.setStretchFactor(0, 2)
        self._middle_splitter.setStretchFactor(1, 6)
        self._middle_splitter.setStretchFactor(2, 2)
        self._middle_splitter.setSizes([260, 860, 260])
        self._saved_middle_sizes = [260, 860, 260]

        middle_layout = QVBoxLayout(self._middle_host)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        middle_layout.addWidget(self._middle_splitter, 1)

        self._vertical_splitter = QSplitter(Qt.Vertical, self)
        self._vertical_splitter.setChildrenCollapsible(False)
        self._vertical_splitter.addWidget(self._top_host)
        self._vertical_splitter.addWidget(self._middle_host)
        self._vertical_splitter.addWidget(self._bottom_host)
        self._vertical_splitter.setStretchFactor(0, 0)
        self._vertical_splitter.setStretchFactor(1, 1)
        self._vertical_splitter.setStretchFactor(2, 0)
        self._vertical_splitter.setSizes([70, 720, 80])
        self._saved_vertical_sizes = [70, 720, 80]

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._vertical_splitter, 1)

    def set_top_widget(self, widget: QWidget | None) -> None:
        self._replace_host_content(self._top_content_host, widget)

    def set_bottom_widget(self, widget: QWidget | None) -> None:
        self._replace_host_content(self._bottom_host, widget)

    def set_left_widget(self, widget: QWidget | None) -> None:
        self._replace_host_content(self._left_host, widget)

    def set_workzone_widget(self, widget: QWidget | None) -> None:
        self._replace_host_content(self._workzone_host, widget)

    def set_workzone_panel_enabled(self, enabled: bool) -> None:
        self._workzone_host.setProperty("panel", bool(enabled))
        self._workzone_host.style().unpolish(self._workzone_host)
        self._workzone_host.style().polish(self._workzone_host)
        self._workzone_host.update()

    def set_right_widget(self, widget: QWidget | None) -> None:
        self._replace_host_content(self._right_host, widget)

    def set_left_zone_visible(self, visible: bool) -> None:
        self._left_toggle_button.setChecked(bool(visible))

    def set_right_zone_visible(self, visible: bool) -> None:
        self._right_toggle_button.setChecked(bool(visible))

    def set_bottom_zone_visible(self, visible: bool) -> None:
        self._bottom_toggle_button.setChecked(bool(visible))

    def _create_zone_toggle_button(self, text: str, callback) -> QPushButton:
        button = QPushButton("", self._top_toggles_host)
        button.setCheckable(True)
        button.setChecked(True)
        button.setProperty("ghost", True)
        button.setProperty("iconOnly", True)
        button.setMinimumHeight(26)
        button.setMinimumWidth(30)
        icon_path = _ZONE_TOGGLE_ICONS.get(text)
        if icon_path is not None and icon_path.exists():
            button.setIcon(self._icon_for(icon_path, active_theme_tokens_ref().get("on_surface", "#f3f5f8")))
            button.setIconSize(QSize(16, 16))
        button.setToolTip(f"Toggle {text.lower()} panel")
        button.setAccessibleName(f"Toggle {text.lower()} panel")
        button.toggled.connect(callback)
        return button

    @staticmethod
    def _icon_for(path: Path, color_hex: str) -> QIcon:
        if not path.exists():
            return QIcon()
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QIcon()

        icon = QIcon()
        tint = QColor(color_hex)
        for size in (16, 18, 20, 24):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            icon.addPixmap(pixmap)
        return icon

    def _on_left_toggled(self, visible: bool) -> None:
        self._apply_side_zone_visibility(left_visible=visible, right_visible=self._right_toggle_button.isChecked())

    def _on_right_toggled(self, visible: bool) -> None:
        self._apply_side_zone_visibility(left_visible=self._left_toggle_button.isChecked(), right_visible=visible)

    def _apply_side_zone_visibility(self, *, left_visible: bool, right_visible: bool) -> None:
        current_sizes = self._middle_splitter.sizes()
        if self._left_host.isVisible() and self._right_host.isVisible() and all(size > 0 for size in current_sizes):
            self._saved_middle_sizes = list(current_sizes)

        self._left_host.setVisible(bool(left_visible))
        self._right_host.setVisible(bool(right_visible))

        baseline = self._saved_middle_sizes if sum(self._saved_middle_sizes) > 0 else current_sizes
        total = max(1, int(sum(baseline)))
        left_size = baseline[0] if left_visible else 0
        right_size = baseline[2] if right_visible else 0
        center_size = max(1, total - left_size - right_size)
        self._middle_splitter.setSizes([left_size, center_size, right_size])

    def _on_bottom_toggled(self, visible: bool) -> None:
        current_sizes = self._vertical_splitter.sizes()
        if self._bottom_host.isVisible() and len(current_sizes) >= 3 and current_sizes[2] > 0:
            self._saved_vertical_sizes = list(current_sizes)

        self._bottom_host.setVisible(bool(visible))

        baseline = self._saved_vertical_sizes if sum(self._saved_vertical_sizes) > 0 else current_sizes
        total = max(1, int(sum(baseline)))
        top_size = baseline[0] if len(baseline) > 0 else 70
        bottom_size = baseline[2] if visible and len(baseline) > 2 else 0
        middle_size = max(1, total - top_size - bottom_size)
        self._vertical_splitter.setSizes([top_size, middle_size, bottom_size])

    @staticmethod
    def _new_host_widget() -> QWidget:
        host = QWidget()
        host.setProperty("panel", True)
        return host

    @staticmethod
    def _replace_host_content(host: QWidget, widget: QWidget | None) -> None:
        layout = host.layout()
        if layout is None:
            layout = QVBoxLayout(host)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        while layout.count():
            item = layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
        if widget is not None:
            layout.addWidget(widget, 1)
