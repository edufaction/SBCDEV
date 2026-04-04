import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from domain import Block, BlockType
from UI.Widgets import ThumbnailWidget
from UI.themes import apply_theme, load_qss_template


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_thumbnail_widget_uses_theme_type_color_for_badge() -> None:
    app = _app()
    apply_theme(app, theme_name="dark", font_size=12)
    block = Block(id="blk_img", type=BlockType.IMAGE, profile="asset", name="Image", content={})
    widget = ThumbnailWidget(block)
    assert widget.type_badge_text == "IMAGE"
    assert widget.type_badge_type_key == "image"
    assert widget.type_badge_style == ""

    apply_theme(app, theme_name="light", font_size=12)
    widget.set_block(block)
    assert widget.type_badge_type_key == "image"
    assert widget.type_badge_style == ""


def test_type_badge_qss_rules_are_centralized() -> None:
    qss = load_qss_template()
    assert 'QLabel[typeBadge="true"][blockType="image"]' in qss
    assert "@type_image" in qss
