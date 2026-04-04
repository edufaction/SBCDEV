from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from UI.themes import active_theme_tokens


class SidebarMenu(QFrame):
    """Left production sidebar with branded navigation."""

    navigation_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None, *, on_navigation: Callable[[str], None] | None = None) -> None:
        super().__init__(parent)
        self._on_navigation = on_navigation
        self._active_key = "dashboard"
        self._collapsed = False
        self._icons_dir = Path(__file__).resolve().parents[2] / "icons"
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self._footer_buttons: dict[str, QPushButton] = {}
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        self.setObjectName("Sidebar")
        self.setFrameShape(QFrame.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(8)

        self._header_widget = self._build_header()
        layout.addWidget(self._header_widget)
        layout.addSpacing(8)
        self._sidebar_toggle_button = self._create_sidebar_toggle_button()
        layout.addWidget(self._sidebar_toggle_button)
        layout.addSpacing(8)

        for key, text, icon_name in (
            ("dashboard", "DASHBOARD", "project_layout_dashboard.svg"),
            ("asset_library", "ASSET LIBRARY", "project_folder_open.svg"),
            ("character_studio", "CHARACTER STUDIO", "story_world_user_star.svg"),
            ("story_planner", "STORY PLANNER", "project_notebook.svg"),
            ("ai_presets", "AI PRESETS", "edit_filter_2_spark.svg"),
            ("tools", "TOOLS", "project_clipboard_list.svg"),
        ):
            btn = self._create_nav_button(key, text, icon_name, footer=False)
            self._nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        for key, text, icon_name in (
            ("project", "PROJECT", "project_notebook.svg"),
            ("support", "SUPPORT", "story_world_message_circle_user.svg"),
            ("settings", "SETTINGS", "actions_adjustments_search.svg"),
        ):
            btn = self._create_nav_button(key, text, icon_name, footer=True)
            self._footer_buttons[key] = btn
            layout.addWidget(btn)

        layout.addSpacing(14)
        self._profile_widget = self._build_profile_widget()
        layout.addWidget(self._profile_widget)

        self._refresh_icons()
        self.set_collapsed(False)
        self._update_sidebar_width()
        self.set_active("dashboard")

    @property
    def active_key(self) -> str:
        return self._active_key

    def nav_button(self, key: str) -> QPushButton | None:
        return self._nav_buttons.get(key) or self._footer_buttons.get(key)

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_button(self) -> QPushButton:
        return self._sidebar_toggle_button

    def set_active(self, key: str) -> None:
        button = self._nav_buttons.get(key) or self._footer_buttons.get(key)
        if button is not None:
            self._active_key = key
            button.setChecked(True)
        self._refresh_nav_styles()
        self._refresh_icons()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self.setProperty("collapsed", self._collapsed)

        self._sidebar_title.setVisible(not self._collapsed)
        self._sidebar_subtitle.setVisible(not self._collapsed)
        self._profile_widget.setVisible(not self._collapsed)

        for button in [*self._nav_buttons.values(), *self._footer_buttons.values()]:
            full_text = str(button.property("fullText") or "")
            button.setText("" if self._collapsed else full_text)
            button.setToolTip(full_text if self._collapsed else "")
            button.setProperty("collapsed", self._collapsed)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        self._sidebar_toggle_button.setToolTip("Expand sidebar" if self._collapsed else "Collapse sidebar")
        self._sidebar_toggle_button.style().unpolish(self._sidebar_toggle_button)
        self._sidebar_toggle_button.style().polish(self._sidebar_toggle_button)
        self._sidebar_toggle_button.update()

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self._refresh_nav_styles()
        self._refresh_icons()
        self._update_sidebar_width()

    def _build_header(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("SidebarHeader")
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        crest = QLabel(container)
        crest.setObjectName("SidebarBrandCrest")
        crest.setFixedSize(28, 28)
        crest.setText("A")
        crest.setAlignment(Qt.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)

        self._sidebar_title = QLabel("The Architect", container)
        self._sidebar_title.setObjectName("SidebarBrandTitle")
        self._sidebar_subtitle = QLabel("AI StoryBoard", container)
        self._sidebar_subtitle.setObjectName("SidebarBrandSubtitle")
        text_col.addWidget(self._sidebar_title)
        text_col.addWidget(self._sidebar_subtitle)

        row.addWidget(crest)
        row.addLayout(text_col, 1)
        return container

    def _build_profile_widget(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("SidebarProfile")
        row = QHBoxLayout(container)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(10)

        avatar = QLabel(container)
        avatar.setObjectName("SidebarProfileAvatar")
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setText("SL")

        details = QVBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(0)
        name = QLabel("Studio Lead", container)
        name.setObjectName("SidebarProfileName")
        role = QLabel("Creative Session", container)
        role.setObjectName("SidebarProfileRole")
        details.addWidget(name)
        details.addWidget(role)

        row.addWidget(avatar)
        row.addLayout(details, 1)
        return container

    def _create_sidebar_toggle_button(self) -> QPushButton:
        button = QPushButton("", self)
        button.setCursor(QCursor(Qt.PointingHandCursor))
        button.setProperty("sidebarToggle", True)
        button.setProperty("iconName", "project_layout_list.svg")
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(34)
        button.setToolTip("Collapse sidebar")
        button.clicked.connect(self.toggle_collapsed)
        return button

    def _create_nav_button(self, key: str, text: str, icon_name: str, *, footer: bool) -> QPushButton:
        btn = QPushButton(text, self)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setProperty("iconName", icon_name)
        btn.setProperty("fullText", text)
        btn.setIconSize(QSize(18, 18))
        btn.setMinimumHeight(42)
        btn.setProperty("sidebarNav", True)
        btn.setProperty("footerAction", footer)
        btn.setProperty("sectionKey", key)
        btn.setCheckable(True)
        btn.setAutoDefault(False)
        self._nav_group.addButton(btn)
        btn.clicked.connect(lambda checked=False, section_key=key: self._on_button_clicked(section_key))
        return btn

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().changeEvent(event)
        if event.type() in {QEvent.StyleChange, QEvent.PaletteChange, QEvent.FontChange}:
            self._refresh_icons()
            self._update_sidebar_width()

    def _on_button_clicked(self, key: str) -> None:
        self._active_key = key
        self._refresh_nav_styles()
        self._refresh_icons()
        self.navigation_requested.emit(key)
        if self._on_navigation is not None:
            self._on_navigation(key)

    def _refresh_nav_styles(self) -> None:
        for key, btn in {**self._nav_buttons, **self._footer_buttons}.items():
            btn.setProperty("active", key == self._active_key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _refresh_icons(self) -> None:
        tokens = active_theme_tokens()
        on_surface = tokens.get("on_surface", "#f9f9fd")
        on_surface_variant = tokens.get("on_surface_variant", on_surface)
        for button in [*self._nav_buttons.values(), *self._footer_buttons.values()]:
            icon_name = button.property("iconName")
            if isinstance(icon_name, str):
                icon_color = on_surface if button.isChecked() else on_surface_variant
                button.setIcon(self._icon_for(icon_name, icon_color))
        toggle_icon_name = self._sidebar_toggle_button.property("iconName")
        if isinstance(toggle_icon_name, str):
            self._sidebar_toggle_button.setIcon(self._icon_for(toggle_icon_name, on_surface_variant))

    def _update_sidebar_width(self) -> None:
        self.setFixedWidth(self._calculate_required_width())

    def _calculate_required_width(self) -> int:
        if self._collapsed:
            margins = self.layout().contentsMargins()
            compact_content_width = 42
            return compact_content_width + margins.left() + margins.right()

        # Button content width: [left padding] + [icon] + [gap] + [text] + [right padding]
        button_content_width = 0
        for button in [*self._nav_buttons.values(), *self._footer_buttons.values()]:
            fm = QFontMetrics(button.font())
            text_width = fm.horizontalAdvance(button.text())
            icon_width = button.iconSize().width()
            candidate = 14 + icon_width + 10 + text_width + 14
            if candidate > button_content_width:
                button_content_width = candidate

        title = self.findChild(QLabel, "SidebarBrandTitle")
        subtitle = self.findChild(QLabel, "SidebarBrandSubtitle")
        header_width = 0
        if title is not None:
            title_width = QFontMetrics(title.font()).horizontalAdvance(title.text())
            subtitle_width = 0
            if subtitle is not None:
                subtitle_width = QFontMetrics(subtitle.font()).horizontalAdvance(subtitle.text())
            header_width = 28 + 10 + max(title_width, subtitle_width)

        profile_name = self.findChild(QLabel, "SidebarProfileName")
        profile_role = self.findChild(QLabel, "SidebarProfileRole")
        profile_width = 0
        if profile_name is not None:
            name_width = QFontMetrics(profile_name.font()).horizontalAdvance(profile_name.text())
            role_width = 0
            if profile_role is not None:
                role_width = QFontMetrics(profile_role.font()).horizontalAdvance(profile_role.text())
            profile_width = 8 + 28 + 10 + max(name_width, role_width) + 8

        content_width = max(button_content_width, header_width, profile_width)
        margins = self.layout().contentsMargins()
        return content_width + margins.left() + margins.right()

    def _icon_for(self, filename: str, color_hex: str) -> QIcon:
        cache_key = (filename, color_hex)
        cached = self._icon_cache.get(cache_key)
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
        for size in (16, 18, 20, 24, 28):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            icon.addPixmap(pixmap)

        self._icon_cache[cache_key] = icon
        return icon
