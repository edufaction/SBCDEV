from __future__ import annotations

from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QFrame, QScrollBar, QWidget


SCROLLBAR_SINGLE_STEP = 24


def initialize_widget_primitives(root: QWidget) -> None:
    """Initialize baseline look-and-feel primitives for a widget subtree."""
    if root is None:
        return

    _initialize_one(root)
    for child in root.findChildren(QWidget):
        _initialize_one(child)


def install_widget_primitives(app: QApplication) -> None:
    """Install baseline primitives for current top-level widgets (one-shot)."""
    if app is None:
        return

    if app.property("sbc2_widget_primitives_installed") is True:
        return

    app.setProperty("sbc2_widget_primitives_installed", True)
    for top_level in app.topLevelWidgets():
        if isinstance(top_level, QWidget):
            initialize_widget_primitives(top_level)


def _initialize_one(widget: QWidget) -> None:
    if isinstance(widget, QAbstractScrollArea):
        widget.setProperty("productionScrollArea", True)
        if isinstance(widget, QFrame):
            widget.setFrameShape(QFrame.NoFrame)
        _configure_scrollbar(widget.verticalScrollBar())
        _configure_scrollbar(widget.horizontalScrollBar())
    elif isinstance(widget, QScrollBar):
        _configure_scrollbar(widget)


def _configure_scrollbar(scrollbar: QScrollBar | None) -> None:
    if scrollbar is None:
        return
    scrollbar.setProperty("productionScrollBar", True)
    if scrollbar.singleStep() <= 0:
        scrollbar.setSingleStep(SCROLLBAR_SINGLE_STEP)
    else:
        scrollbar.setSingleStep(max(scrollbar.singleStep(), SCROLLBAR_SINGLE_STEP))
