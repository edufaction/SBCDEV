import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from domain import Block, BlockType
from UI.Widgets import ThumbnailListView


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_thumbnail_list_view_displays_thumbnail_model() -> None:
    _ = _app()
    blocks = [
        Block(id="blk_1", type=BlockType.IMAGE, profile="asset", name="Image A", content={}),
        Block(id="blk_2", type=BlockType.TEXT, profile="note", name="Text B", content={"text": "hello"}),
        Block(id="blk_3", type=BlockType.PROMPT, profile="prompt", name="Prompt C", content={"prompt_generated": "x"}),
    ]
    view = ThumbnailListView()
    view.set_blocks(blocks)

    model = view.model()
    assert model is not None
    assert model.rowCount() == 3

    assert view.property("productionScrollArea") is True
    assert view.verticalScrollBar().property("productionScrollBar") is True
    assert view.horizontalScrollBar().property("productionScrollBar") is True

    for index, block in enumerate(blocks):
        model_idx = model.index(index, 0)
        assert model_idx.data(Qt.UserRole + 1) is block


def test_thumbnail_list_view_dispatches_click_and_double_click_handlers() -> None:
    _ = _app()
    clicked: list[str] = []
    double_clicked: list[str] = []

    block = Block(id="blk_1", type=BlockType.IMAGE, profile="asset", name="Image A", content={})
    view = ThumbnailListView(
        on_block_click=lambda b: clicked.append(b.id),
        on_block_double_click=lambda b: double_clicked.append(b.id),
    )
    view.set_blocks([block])
    view.resize(320, 280)
    view.show()

    # Emulate Qt signal emissions directly since we cannot easily mouse-click a specific QListView item painted natively
    model = view.model()
    model_idx = model.index(0, 0)
    
    view.clicked.emit(model_idx)
    view.doubleClicked.emit(model_idx)

    assert clicked == ["blk_1"]
    assert double_clicked == ["blk_1"]
