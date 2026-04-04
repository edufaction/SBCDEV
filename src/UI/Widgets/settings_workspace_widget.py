from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QTabWidget, QVBoxLayout, QWidget

from UI.Widgets.panel_header_widget import PanelHeaderWidget
from UI.themes import THEME_NAMES, active_theme_tokens_ref, initialize_widget_primitives


class SettingsWorkspaceWidget(QWidget):
    """Workspace settings with tabbed interface."""

    theme_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None, *, theme_names: list[str] | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._icons_dir = Path(__file__).resolve().parents[2] / "icons"
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._theme_names = theme_names or list(THEME_NAMES)
        self._syncing = False

        self._header = PanelHeaderWidget("SETTINGS", parent=self)
        self._header_label = self._header.title_label

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("SettingsTabs")
        self._tabs.setDocumentMode(False)
        self._tabs.setIconSize(QSize(16, 16))
        self._tabs.currentChanged.connect(lambda *_: self._refresh_tab_icons())
        self._tabs.tabBar().setDrawBase(False)

        self._theme_combo = QComboBox(self)
        self._theme_combo.setProperty("commandBar", True)
        for theme_name in self._theme_names:
            self._theme_combo.addItem(theme_name.upper(), theme_name)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_index_changed)

        interface_tab = QWidget(self._tabs)
        interface_tab.setProperty("panel", True)
        interface_layout = QVBoxLayout(interface_tab)
        interface_layout.setContentsMargins(14, 14, 14, 14)
        interface_layout.setSpacing(9)
        interface_label = QLabel("INTERFACE", interface_tab)
        interface_label.setProperty("section", True)
        interface_hint = QLabel("Theme", interface_tab)
        interface_hint.setProperty("muted", True)
        interface_layout.addWidget(interface_label)
        interface_layout.addWidget(interface_hint)
        interface_layout.addWidget(self._theme_combo)
        interface_layout.addStretch(1)

        general_tab = QWidget(self._tabs)
        general_tab.setProperty("panel", True)
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(14, 14, 14, 14)
        general_layout.setSpacing(9)
        general_label = QLabel("GENERAL", general_tab)
        general_label.setProperty("section", True)
        general_hint = QLabel("Workspace settings panel is ready.", general_tab)
        general_hint.setProperty("muted", True)
        general_layout.addWidget(general_label)
        general_layout.addWidget(general_hint)
        general_layout.addStretch(1)

        storage_tab = QWidget(self._tabs)
        storage_tab.setProperty("panel", True)
        storage_layout = QVBoxLayout(storage_tab)
        storage_layout.setContentsMargins(14, 14, 14, 14)
        storage_layout.setSpacing(9)
        storage_label = QLabel("STORAGE", storage_tab)
        storage_label.setProperty("section", True)
        storage_layout.addWidget(storage_label)

        storage_form_holder = QWidget(storage_tab)
        storage_form = QFormLayout(storage_form_holder)
        storage_form.setContentsMargins(0, 0, 0, 0)
        storage_form.setSpacing(8)
        storage_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        self._storage_value_labels: dict[str, QLabel] = {}
        for key, title in (
            ("projects", "Projects"),
            ("libraries_user", "Libraries USER"),
            ("libraries_application", "Libraries APPLICATION"),
        ):
            value = QLabel("-", storage_form_holder)
            value.setProperty("technical", True)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            storage_form.addRow(f"{title}:", value)
            self._storage_value_labels[key] = value

        storage_layout.addWidget(storage_form_holder)
        storage_layout.addStretch(1)

        self._tabs.addTab(interface_tab, "Interface")
        self._tabs.addTab(general_tab, "General")
        self._tabs.addTab(storage_tab, "Storage")
        self._refresh_tab_icons()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header, 0)
        root_layout.addWidget(self._tabs, 1)

        initialize_widget_primitives(self)

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().changeEvent(event)
        if event.type() in {QEvent.StyleChange, QEvent.PaletteChange, QEvent.FontChange}:
            self._icon_cache.clear()
            self._refresh_tab_icons()

    def set_current_theme(self, theme_name: str) -> None:
        index = self._theme_combo.findData(theme_name)
        if index < 0:
            return
        if self._theme_combo.currentIndex() == index:
            return
        self._syncing = True
        try:
            self._theme_combo.setCurrentIndex(index)
        finally:
            self._syncing = False

    def _on_theme_index_changed(self, index: int) -> None:
        if self._syncing or index < 0:
            return
        theme_name = str(self._theme_combo.itemData(index) or "")
        if theme_name:
            self.theme_changed.emit(theme_name)

    def _refresh_tab_icons(self) -> None:
        self._tabs.setTabIcon(0, self._icon_for("actions_adjustments_search.svg", self._tab_icon_color(0)))
        self._tabs.setTabIcon(1, self._icon_for("project_layout_dashboard.svg", self._tab_icon_color(1)))
        self._tabs.setTabIcon(2, self._icon_for("project_folder_open.svg", self._tab_icon_color(2)))

    def _tab_icon_color(self, index: int) -> str:
        tokens = active_theme_tokens_ref()
        if index == self._tabs.currentIndex():
            return tokens.get("on_primary_fixed", "#ffffff")
        return tokens.get("on_surface_variant", tokens.get("on_surface", "#f9f9fd"))

    def set_storage_paths(
        self,
        *,
        projects_root: Path,
        user_libraries_root: Path,
        application_libraries_root: Path,
    ) -> None:
        self._storage_value_labels["projects"].setText(str(projects_root))
        self._storage_value_labels["libraries_user"].setText(str(user_libraries_root))
        self._storage_value_labels["libraries_application"].setText(str(application_libraries_root))

    def _icon_for(self, filename: str, color_hex: str) -> QIcon:
        key = (filename, color_hex)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        path = self._icons_dir / filename
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

        self._icon_cache[key] = icon
        return icon
