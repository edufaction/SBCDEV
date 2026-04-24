from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMessageBox


class ApplicationMenuBuilder:
    """Builds the native application menu bar for desktop platforms."""

    def __init__(
        self,
        *,
        window: QMainWindow,
        create_project: Callable[[], None],
        open_project: Callable[[], None],
        close_project: Callable[[], None],
        open_project_tree: Callable[[], None],
        open_thumbnail_browser: Callable[[], None],
        open_media_carousel: Callable[[], None],
        navigate_to_section: Callable[[str], None],
    ) -> None:
        self._window = window
        self._create_project = create_project
        self._open_project = open_project
        self._close_project = close_project
        self._open_project_tree = open_project_tree
        self._open_thumbnail_browser = open_thumbnail_browser
        self._open_media_carousel = open_media_carousel
        self._navigate_to_section = navigate_to_section

    def build(self) -> dict[str, QAction]:
        menu_bar = self._window.menuBar()
        menu_bar.clear()
        menu_bar.setNativeMenuBar(sys.platform == "darwin")

        actions: dict[str, QAction] = {}

        file_menu = menu_bar.addMenu("&File")
        actions["new_project"] = self._add_action(
            file_menu,
            text="New Project",
            shortcut=QKeySequence.New,
            handler=self._create_project,
        )
        actions["open_project"] = self._add_action(
            file_menu,
            text="Open Project",
            shortcut=QKeySequence.Open,
            handler=self._open_project,
        )
        actions["close_project"] = self._add_action(
            file_menu,
            text="Close Project",
            shortcut=QKeySequence.Close,
            handler=self._close_project,
        )
        file_menu.addSeparator()
        actions["preferences"] = self._add_action(
            file_menu,
            text="Preferences",
            shortcut=QKeySequence.Preferences,
            handler=lambda: self._navigate_to_section("settings"),
            menu_role=QAction.MenuRole.PreferencesRole,
        )
        file_menu.addSeparator()
        actions["quit"] = self._add_action(
            file_menu,
            text="Quit SBC2",
            shortcut=QKeySequence.Quit,
            handler=self._window.close,
            menu_role=QAction.MenuRole.QuitRole,
        )

        view_menu = menu_bar.addMenu("&View")
        actions["view_dashboard"] = self._add_action(
            view_menu,
            text="Dashboard",
            shortcut="Ctrl+1",
            handler=lambda: self._navigate_to_section("dashboard"),
        )
        actions["view_project"] = self._add_action(
            view_menu,
            text="Projects",
            shortcut="Ctrl+2",
            handler=lambda: self._navigate_to_section("project"),
        )
        actions["view_library"] = self._add_action(
            view_menu,
            text="Asset Library",
            shortcut="Ctrl+3",
            handler=lambda: self._navigate_to_section("asset_library"),
        )
        actions["view_character"] = self._add_action(
            view_menu,
            text="Character Studio",
            shortcut="Ctrl+4",
            handler=lambda: self._navigate_to_section("character_studio"),
        )
        actions["view_story"] = self._add_action(
            view_menu,
            text="Story Planner",
            shortcut="Ctrl+5",
            handler=lambda: self._navigate_to_section("story_planner"),
        )
        actions["view_settings"] = self._add_action(
            view_menu,
            text="Settings",
            shortcut="Ctrl+,",
            handler=lambda: self._navigate_to_section("settings"),
        )

        window_menu = menu_bar.addMenu("&Window")
        actions["window_tree"] = self._add_action(
            window_menu,
            text="Project Tree",
            shortcut="Ctrl+Shift+T",
            handler=self._open_project_tree,
        )
        actions["window_thumbnail"] = self._add_action(
            window_menu,
            text="Thumbnail Browser",
            shortcut="Ctrl+Shift+B",
            handler=self._open_thumbnail_browser,
        )
        actions["window_carousel"] = self._add_action(
            window_menu,
            text="Media Carousel",
            shortcut="Ctrl+Shift+M",
            handler=self._open_media_carousel,
        )

        help_menu = menu_bar.addMenu("&Help")
        actions["about"] = self._add_action(
            help_menu,
            text="About SBC2",
            handler=self._show_about_dialog,
            menu_role=QAction.MenuRole.AboutRole,
        )
        return actions

    def _add_action(
        self,
        menu,
        *,
        text: str,
        handler: Callable[[], None],
        shortcut: str | QKeySequence | None = None,
        menu_role: QAction.MenuRole = QAction.MenuRole.NoRole,
    ) -> QAction:
        action = QAction(text, self._window)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.setMenuRole(menu_role)
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self._window,
            "About SBC2",
            "SBC2\nStoryboard and asset repository desktop application.",
        )
