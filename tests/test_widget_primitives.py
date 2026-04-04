import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem

from UI.themes import initialize_widget_primitives, install_widget_primitives
from UI.themes.widget_primitives import SCROLLBAR_SINGLE_STEP


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _make_scrollable_list() -> QListWidget:
    view = QListWidget()
    view.resize(220, 120)
    for idx in range(80):
        view.addItem(QListWidgetItem(f"Row {idx:03d}"))
    return view


def test_initialize_widget_primitives_applies_scrollbar_properties() -> None:
    app = _app()
    view = _make_scrollable_list()
    view.show()
    app.processEvents()

    initialize_widget_primitives(view)

    vbar = view.verticalScrollBar()
    hbar = view.horizontalScrollBar()
    assert view.property("productionScrollArea") is True
    assert vbar.property("productionScrollBar") is True
    assert hbar.property("productionScrollBar") is True
    assert vbar.singleStep() >= SCROLLBAR_SINGLE_STEP
    view.close()
    view.deleteLater()
    app.processEvents()


def test_install_widget_primitives_applies_to_existing_top_level_widgets() -> None:
    app = _app()
    view = _make_scrollable_list()
    view.show()
    install_widget_primitives(app)
    app.processEvents()

    assert view.property("productionScrollArea") is True
    assert view.verticalScrollBar().property("productionScrollBar") is True
    assert view.horizontalScrollBar().property("productionScrollBar") is True
    view.close()
    view.deleteLater()
    app.processEvents()
