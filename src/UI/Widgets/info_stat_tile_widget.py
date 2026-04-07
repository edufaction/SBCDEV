from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from UI.themes import active_theme_tokens_ref


class InfoStatTileWidget(QFrame):
    """Compact dashboard tile with icon, label, and large numeric value."""

    def __init__(
        self,
        title: str,
        *,
        icon_name: str = "",
        value: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("statTile", True)
        self._title = (title or "").strip().upper()
        self._value = int(value)
        self._icon_name = (icon_name or "").strip()
        self._icons_dir = Path(__file__).resolve().parents[2] / "icons"
        self._icon_label = QLabel(self)
        self._icon_label.setProperty("statIcon", True)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setFixedSize(40, 40)

        self._title_label = QLabel(self._title, self)
        self._title_label.setProperty("section", True)
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._value_label = QLabel(str(self._value), self)
        self._value_label.setProperty("displayMd", True)
        self._value_label.setProperty("statValue", True)
        self._value_label.setAlignment(Qt.AlignCenter)

        labels_col = QWidget(self)
        labels_layout = QVBoxLayout(labels_col)
        labels_layout.setContentsMargins(0, 0, 0, 0)
        labels_layout.setSpacing(4)
        labels_layout.addWidget(self._title_label)
        labels_layout.addWidget(self._value_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self._icon_label, 0, Qt.AlignTop)
        layout.addWidget(labels_col, 1)

        self._render_icon()

    def set_value(self, value: int) -> None:
        self._value = max(0, int(value))
        self._value_label.setText(str(self._value))

    def set_title(self, title: str) -> None:
        self._title = (title or "").strip().upper()
        self._title_label.setText(self._title)

    def set_icon_name(self, icon_name: str) -> None:
        self._icon_name = (icon_name or "").strip()
        self._render_icon()

    def _render_icon(self) -> None:
        tokens = active_theme_tokens_ref()
        icon_color = tokens.get("on_surface_variant", tokens.get("on_surface", "#f9f9fd"))
        if not self._icon_name:
            self._icon_label.setPixmap(QPixmap())
            self._icon_label.setText("")
            return

        icon = self._tinted_icon(self._icon_name, icon_color)
        if icon.isNull():
            self._icon_label.setPixmap(QPixmap())
            self._icon_label.setText("")
            return
        self._icon_label.setText("")
        self._icon_label.setPixmap(icon.pixmap(QSize(20, 20)))

    def _tinted_icon(self, filename: str, color_hex: str) -> QIcon:
        path = self._icons_dir / filename
        if not path.exists():
            return QIcon()

        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QIcon()

        icon = QIcon()
        tint = QColor(color_hex)
        for size in (16, 20, 24):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            icon.addPixmap(pixmap)
        return icon
