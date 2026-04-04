import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from domain import Block, BlockType
from UI.Widgets import ThumbnailWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_thumbnail_widget_uses_horizontal_two_thirds_for_media_and_left_aligned_labels() -> None:
    app = _app()
    block = Block(id="blk_txt", type=BlockType.TEXT, profile="note", name="Title", content={"text": "Body"})
    widget = ThumbnailWidget(block)
    widget.resize(600, 240)
    widget.show()
    app.processEvents()

    expected_canvas_width = max(160, (widget.contentsRect().width() * 2) // 3)
    assert abs(widget._canvas.width() - expected_canvas_width) <= 2
    assert widget._canvas.width() > widget._details_panel.width()
    assert widget._title_label.alignment() & Qt.AlignLeft
    assert widget._meta_label.alignment() & Qt.AlignLeft
