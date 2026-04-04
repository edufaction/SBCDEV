import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from domain import Block, BlockType
from UI.Widgets import ThumbnailWidget
from UI.Widgets import thumbnail_widget as thumbnail_widget_module
from UI.themes import apply_theme


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_video_thumbnail_uses_extracted_preview(monkeypatch, tmp_path: Path) -> None:
    _ = _app()
    video_path = tmp_path / "storage" / "files" / "clip.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"not-a-real-video")

    def _fake_extract(video_file: Path, preview_file: Path, *, target_ms: int, timeout_ms: int = 5000) -> bool:
        del video_file, target_ms, timeout_ms
        image = QPixmap(64, 36)
        image.fill(QColor("#0ea5e9"))
        preview_file.parent.mkdir(parents=True, exist_ok=True)
        return image.save(str(preview_file), "JPG")

    monkeypatch.setattr(thumbnail_widget_module, "_extract_video_frame_with_qt", _fake_extract)

    block = Block(
        id="blk_video",
        type=BlockType.VIDEO,
        profile="asset",
        name="Clip",
        content={"storage_path": "storage/files/clip.mp4"},
    )
    widget = ThumbnailWidget(block, project_root=tmp_path)

    assert widget._canvas._pixmap is not None
    assert not widget._canvas._pixmap.isNull()
    previews = list((tmp_path / "cache" / "previews").glob("clip_*.jpg"))
    assert len(previews) == 1


def test_image_thumbnail_render_keeps_aspect_ratio(tmp_path: Path) -> None:
    app = _app()
    apply_theme(app, theme_name="dark", font_size=12)
    image_path = tmp_path / "storage" / "files" / "wide.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)

    source = QPixmap(400, 100)
    source.fill(QColor("#ef4444"))
    assert source.save(str(image_path), "PNG")

    canvas = thumbnail_widget_module._ThumbnailCanvas()
    canvas.resize(220, 220)
    canvas.set_data(BlockType.IMAGE, {"storage_path": "storage/files/wide.png"}, project_root=tmp_path)

    rendered = QPixmap(canvas.size())
    canvas.render(rendered)
    image = rendered.toImage()

    top_pixel = image.pixelColor(110, 25)
    center_pixel = image.pixelColor(110, 110)

    assert center_pixel.red() > 200
    assert center_pixel.green() < 100
    assert top_pixel.red() < 120
    assert top_pixel != center_pixel


def test_invalid_png_is_skipped_without_pixmap_load(tmp_path: Path) -> None:
    _ = _app()
    image_path = tmp_path / "storage" / "files" / "broken.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nBROKEN")

    canvas = thumbnail_widget_module._ThumbnailCanvas()
    canvas.set_data(BlockType.IMAGE, {"storage_path": "storage/files/broken.png"}, project_root=tmp_path)

    assert canvas._pixmap is None
