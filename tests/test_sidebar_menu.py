import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from UI.Widgets import SidebarMenu
from UI.themes import active_theme_tokens, apply_theme
from UI.windows.main_window import MainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _average_opaque_icon_color(button) -> QColor:
    image = button.icon().pixmap(18, 18).toImage()
    sampled: list[QColor] = []
    for x in range(image.width()):
        for y in range(image.height()):
            c = image.pixelColor(x, y)
            if c.alpha() > 220:
                sampled.append(c)
    assert sampled
    avg_r = round(sum(c.red() for c in sampled) / len(sampled))
    avg_g = round(sum(c.green() for c in sampled) / len(sampled))
    avg_b = round(sum(c.blue() for c in sampled) / len(sampled))
    return QColor(avg_r, avg_g, avg_b)


def test_sidebar_menu_loads_svg_icons_and_default_selection() -> None:
    app = _app()
    apply_theme(app, theme_name="dark", font_size=12)
    sidebar = SidebarMenu()
    sidebar.show()

    assert sidebar.width() == sidebar._calculate_required_width()
    assert sidebar.active_key == "dashboard"

    dashboard = sidebar.nav_button("dashboard")
    story = sidebar.nav_button("story_planner")
    tools = sidebar.nav_button("tools")
    project = sidebar.nav_button("project")
    assert dashboard is not None
    assert story is not None
    assert tools is not None
    assert project is not None
    assert not dashboard.icon().isNull()
    assert not story.icon().isNull()
    assert not tools.icon().isNull()
    assert not project.icon().isNull()
    assert dashboard.isChecked()

    tokens = active_theme_tokens()
    expected_active = QColor(tokens.get("on_surface", "#f9f9fd"))
    expected_inactive = QColor(tokens.get("on_surface_variant", "#aaabaf"))
    dashboard_avg = _average_opaque_icon_color(dashboard)
    story_avg = _average_opaque_icon_color(story)
    assert abs(dashboard_avg.red() - expected_active.red()) <= 12
    assert abs(dashboard_avg.green() - expected_active.green()) <= 12
    assert abs(dashboard_avg.blue() - expected_active.blue()) <= 12
    assert abs(story_avg.red() - expected_inactive.red()) <= 12
    assert abs(story_avg.green() - expected_inactive.green()) <= 12
    assert abs(story_avg.blue() - expected_inactive.blue()) <= 12


def test_sidebar_menu_notifies_caller_and_switches_active_state() -> None:
    _ = _app()
    received: list[str] = []
    sidebar = SidebarMenu(on_navigation=lambda key: received.append(key))
    sidebar.show()

    target = sidebar.nav_button("character_studio")
    assert target is not None
    QTest.mouseClick(target, Qt.LeftButton)

    assert received == ["character_studio"]
    assert sidebar.active_key == "character_studio"
    assert target.isChecked()


def test_sidebar_menu_burger_toggles_collapsed_icon_only_mode() -> None:
    _ = _app()
    sidebar = SidebarMenu()
    sidebar.show()

    expanded_width = sidebar.width()
    toggle = sidebar.toggle_button()
    assert toggle is not None

    QTest.mouseClick(toggle, Qt.LeftButton)

    assert sidebar.is_collapsed is True
    assert sidebar.width() < expanded_width
    assert sidebar.nav_button("dashboard").text() == ""
    assert sidebar.nav_button("project").text() == ""
    assert sidebar._profile_widget.isVisible() is False

    QTest.mouseClick(toggle, Qt.LeftButton)

    assert sidebar.is_collapsed is False
    assert sidebar.width() >= expanded_width
    assert sidebar.nav_button("dashboard").text() == "DASHBOARD"
    assert sidebar.nav_button("project").text() == "PROJECT"


def test_main_window_sidebar_navigation_updates_workspace_header() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    button = window._sidebar.nav_button("asset_library")
    assert button is not None
    QTest.mouseClick(button, Qt.LeftButton)

    assert window._section_key == "asset_library"
    assert window._workspace_header.text() == "ASSET LIBRARY"


def test_main_window_tools_navigation_shows_tools_workspace() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    button = window._sidebar.nav_button("tools")
    assert button is not None
    QTest.mouseClick(button, Qt.LeftButton)

    assert window._section_key == "tools"
    assert window._workspace_header.text() == "TOOLS"
    assert window._workspace_stack.currentWidget() is window._workspace_tools_page
    assert window._workspace_actions_frame.parentWidget() is window._workspace_tools_page
