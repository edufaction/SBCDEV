from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton, QWidget

from UI.themes import active_theme_tokens_ref


@dataclass(slots=True)
class WorkspaceActionButtons:
    open_thumbnail_buttons: list[QPushButton]
    open_media_carousel_button: QPushButton
    all_buttons: list[QPushButton]


class WorkspaceActionButtonFactory:
    """Builds and refreshes workspace action buttons with themed SVG icons."""

    def __init__(self, *, parent: QWidget, icons_dir: Path) -> None:
        self._parent = parent
        self._icons_dir = icons_dir
        self._icon_cache: dict[tuple[str, str], QIcon] = {}

    def build(
        self,
        *,
        open_thumbnail_handler,
        open_media_carousel_handler,
    ) -> WorkspaceActionButtons:
        open_thumbnail_button = self._create_thumbnail_button(
            "Open Thumbnail List",
            on_click=open_thumbnail_handler,
            icon_name="project_folder_open.svg",
        )
        open_thumbnail_button_primary = self._create_thumbnail_button(
            "Open Primary",
            on_click=open_thumbnail_handler,
            style_property="primary",
            icon_name="project_layout_dashboard.svg",
        )
        open_thumbnail_button_accent = self._create_thumbnail_button(
            "Open Accent",
            on_click=open_thumbnail_handler,
            style_property="accent",
            icon_name="edit_filter_2_spark.svg",
        )
        open_thumbnail_button_ghost = self._create_thumbnail_button(
            "Open Ghost",
            on_click=open_thumbnail_handler,
            style_property="ghost",
            icon_name="story_world_message_circle_user.svg",
        )
        open_thumbnail_button_magic = self._create_thumbnail_button(
            "Open AI Magic",
            on_click=open_thumbnail_handler,
            style_property="aiMagic",
            icon_name="actions_adjustments_search.svg",
        )
        open_thumbnail_buttons = [
            open_thumbnail_button,
            open_thumbnail_button_primary,
            open_thumbnail_button_accent,
            open_thumbnail_button_ghost,
            open_thumbnail_button_magic,
        ]
        open_media_carousel_button = self._create_button(
            "Open Media Carousel",
            on_click=open_media_carousel_handler,
            style_property="primary",
            icon_name="project_layout_dashboard.svg",
        )
        all_buttons = [*open_thumbnail_buttons, open_media_carousel_button]
        return WorkspaceActionButtons(
            open_thumbnail_buttons=open_thumbnail_buttons,
            open_media_carousel_button=open_media_carousel_button,
            all_buttons=all_buttons,
        )

    def refresh_icons(self, buttons: list[QPushButton]) -> None:
        self._icon_cache.clear()
        for button in buttons:
            icon_name = button.property("iconName")
            if not isinstance(icon_name, str) or not icon_name:
                continue
            style_property = str(button.property("buttonStyleKey") or "")
            button.setIcon(self._icon_for(icon_name, self._button_icon_color(style_property)))

    def _create_thumbnail_button(
        self,
        text: str,
        *,
        on_click,
        style_property: str | None = None,
        icon_name: str | None = None,
    ) -> QPushButton:
        return self._create_button(
            text,
            on_click=on_click,
            style_property=style_property,
            icon_name=icon_name,
        )

    def _create_button(
        self,
        text: str,
        *,
        on_click,
        style_property: str | None = None,
        icon_name: str | None = None,
    ) -> QPushButton:
        button = QPushButton(text, self._parent)
        button.setProperty("buttonStyleKey", style_property or "")
        button.setProperty("iconName", icon_name or "")
        if style_property:
            button.setProperty(style_property, True)
        if icon_name:
            button.setIcon(self._icon_for(icon_name, self._button_icon_color(style_property)))
            button.setIconSize(QSize(16, 16))
        button.clicked.connect(on_click)
        return button

    @staticmethod
    def _button_icon_color(style_property: str | None) -> str:
        tokens = active_theme_tokens_ref()
        if style_property in {"primary", "accent"}:
            return tokens.get("on_primary_fixed", "#000000")
        return tokens.get("on_surface", "#f9f9fd")

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
        for size in (16, 18, 20, 24):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            icon.addPixmap(pixmap)

        self._icon_cache[cache_key] = icon
        return icon
