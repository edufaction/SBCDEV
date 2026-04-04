from __future__ import annotations

import hashlib
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QEventLoop, QMimeData, QPoint, QRect, QSize, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDrag, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QVideoFrame, QVideoSink
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from domain import Block, BlockType
from UI.themes import active_theme_tokens_ref, resolve_type_color, type_badge_label

MEDIA_ASPECT_WIDTH = 16
MEDIA_ASPECT_HEIGHT = 9
HORIZONTAL_GAP = 8
MIN_DETAILS_WIDTH = 140
MIN_MEDIA_WIDTH = 160
BLOCK_IDS_MIME = "application/x-sbc2-block-ids"


def _contrast_text_color(background: QColor) -> QColor:
    # Relative luminance approximation for readability.
    luma = (0.299 * background.red()) + (0.587 * background.green()) + (0.114 * background.blue())
    return QColor("#111827") if luma > 150 else QColor("#F8FAFC")


def _fit_rect_to_aspect(bounds: QRect, *, width_ratio: int, height_ratio: int) -> QRect:
    if bounds.width() <= 0 or bounds.height() <= 0:
        return QRect(bounds)

    target_width = bounds.width()
    target_height = max(1, round(target_width * height_ratio / width_ratio))
    if target_height > bounds.height():
        target_height = bounds.height()
        target_width = max(1, round(target_height * width_ratio / height_ratio))

    x = bounds.x() + (bounds.width() - target_width) // 2
    y = bounds.y() + (bounds.height() - target_height) // 2
    return QRect(x, y, target_width, target_height)


class _ThumbnailCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._block_type: BlockType = BlockType.TEXT
        self._content: dict = {}
        self._pixmap: QPixmap | None = None
        self._theme_tokens: dict[str, str] = active_theme_tokens_ref()
        self.setMinimumHeight(72)

    def set_theme_tokens(self, tokens: dict[str, str]) -> None:
        self._theme_tokens = tokens
        self.update()

    def set_data(self, block_type: BlockType, content: dict, project_root: Path | None = None) -> None:
        self._block_type = block_type
        self._content = dict(content)
        self._pixmap = self._load_pixmap(project_root)
        self.update()

    def _load_pixmap(self, project_root: Path | None) -> QPixmap | None:
        if self._block_type not in {BlockType.IMAGE, BlockType.VIDEO}:
            return None

        media_path = _resolve_media_path(self._content, project_root)
        if media_path is None:
            return None

        pixmap = _load_pixmap_safe(media_path)
        if pixmap is not None:
            return pixmap

        if self._block_type is BlockType.VIDEO:
            preview_path = _extract_video_preview(media_path, project_root=project_root)
            if preview_path is not None:
                preview_pixmap = _load_pixmap_safe(preview_path)
                if preview_pixmap is not None:
                    return preview_pixmap
        return None

    def _text_preview(self) -> str:
        for key in ("text", "prompt_generated", "prompt_ref", "description", "label"):
            value = self._content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return type_badge_label(self._block_type)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        tokens = self._theme_tokens
        base_color = resolve_type_color(self._block_type, tokens=tokens)
        border_color = QColor(tokens.get("outline_20", "#3b3f47"))
        panel_alt_color = QColor(tokens.get("surface_container_high", "#2b2e35"))
        badge_color = QColor(tokens.get("type_badge_text", "#f8fafc"))
        text_color = _contrast_text_color(base_color)

        painter.setBrush(base_color if self._pixmap is None else panel_alt_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 10, 10)

        if self._pixmap is not None:
            content_rect = rect.adjusted(6, 6, -6, -6)
            media_rect = _fit_rect_to_aspect(
                content_rect, width_ratio=MEDIA_ASPECT_WIDTH, height_ratio=MEDIA_ASPECT_HEIGHT
            )
            scaled = self._pixmap.scaled(media_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = media_rect.x() + (media_rect.width() - scaled.width()) // 2
            y = media_rect.y() + (media_rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        elif self._block_type in {BlockType.TEXT, BlockType.PROMPT}:
            painter.setPen(text_color)
            text_rect = _fit_rect_to_aspect(
                rect.adjusted(12, 10, -12, -10),
                width_ratio=MEDIA_ASPECT_WIDTH,
                height_ratio=MEDIA_ASPECT_HEIGHT,
            )
            painter.drawText(text_rect, Qt.TextWordWrap | Qt.AlignTop | Qt.AlignLeft, self._text_preview())
        else:
            painter.setPen(text_color)
            painter.drawText(rect, Qt.AlignCenter, type_badge_label(self._block_type))

        badge_rect = rect.adjusted(8, 8, -8, -8)
        painter.setPen(badge_color)
        painter.drawText(badge_rect, Qt.AlignTop | Qt.AlignRight, type_badge_label(self._block_type))


class ThumbnailWidget(QWidget):
    """Render a thumbnail area and block label based on block type/content."""

    clicked = Signal(object)
    double_clicked = Signal(object)

    def __init__(
        self,
        block: Block,
        *,
        project_root: Path | None = None,
        on_click: Callable[[Block], None] | None = None,
        on_double_click: Callable[[Block], None] | None = None,
        drag_enabled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("thumbnailCard", True)
        self._canvas = _ThumbnailCanvas(self)
        self._type_badge = QLabel(self)
        self._title_label = QLabel(self)
        self._meta_label = QLabel(self)
        self._block: Block = block
        self._on_click = on_click
        self._on_double_click = on_double_click
        self._drag_enabled = drag_enabled
        self._drag_start_pos = QPoint()
        self._theme_tokens: dict[str, str] = active_theme_tokens_ref()
        self._type_badge.setProperty("typeBadge", True)
        self._type_badge.setAlignment(Qt.AlignCenter)
        self._type_badge.setFixedHeight(22)
        self._type_badge.setMinimumWidth(96)
        self._title_label.setWordWrap(True)
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._meta_label.setWordWrap(True)
        self._meta_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._meta_label.setProperty("muted", True)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(180)

        self._details_panel = QWidget(self)
        self._details_layout = QVBoxLayout(self._details_panel)
        self._details_layout.setContentsMargins(0, 0, 0, 0)
        self._details_layout.setSpacing(8)
        self._details_layout.addWidget(self._type_badge, alignment=Qt.AlignLeft)
        self._details_layout.addWidget(self._title_label, alignment=Qt.AlignLeft | Qt.AlignTop)
        self._details_layout.addWidget(self._meta_label, alignment=Qt.AlignLeft | Qt.AlignTop)
        self._details_layout.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._canvas, stretch=2)
        layout.addWidget(self._details_panel, stretch=1)

        # Ensure click/double-click is handled by this widget even over child controls.
        self._canvas.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._type_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._meta_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._refresh_theme_cache()
        self.set_block(block, project_root=project_root)

    def set_block(self, block: Block, *, project_root: Path | None = None) -> None:
        self._refresh_theme_cache()
        self._block = block
        self._canvas.set_data(block.type, block.content, project_root=project_root)
        self._apply_type_badge(block.type)
        self._title_label.setText(block.name or block.id)
        self._meta_label.setText(self._meta_text_for_block(block))
        self._update_sections_layout()

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().changeEvent(event)
        if event.type() in {QEvent.StyleChange, QEvent.PaletteChange}:
            self._refresh_theme_cache()
            self._apply_type_badge(self._block.type)
            self._canvas.update()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._update_sections_layout()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self.clicked.emit(self._block)
            if self._on_click is not None:
                self._on_click(self._block)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if not self._drag_enabled:
            super().mouseMoveEvent(event)
            return
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._start_block_drag()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self._block)
            if self._on_double_click is not None:
                self._on_double_click(self._block)
        super().mouseDoubleClickEvent(event)

    def set_click_handlers(
        self,
        *,
        on_click: Callable[[Block], None] | None = None,
        on_double_click: Callable[[Block], None] | None = None,
    ) -> None:
        self._on_click = on_click
        self._on_double_click = on_double_click

    def set_drag_enabled(self, enabled: bool) -> None:
        self._drag_enabled = bool(enabled)

    def _apply_type_badge(self, block_type: BlockType) -> None:
        self._type_badge.setText(type_badge_label(block_type))
        self._type_badge.setProperty("blockType", block_type.value)
        style = self._type_badge.style()
        style.unpolish(self._type_badge)
        style.polish(self._type_badge)
        self._type_badge.update()

    def _refresh_theme_cache(self) -> None:
        self._theme_tokens = active_theme_tokens_ref()
        self._canvas.set_theme_tokens(self._theme_tokens)

    @staticmethod
    def _meta_text_for_block(block: Block) -> str:
        details = [block.type.value, block.profile]
        if block.is_link():
            details.append("LINK")
        return "  |  ".join(details)

    def _update_sections_layout(self) -> None:
        # Horizontal split: media on first two thirds, labels on remaining third.
        content_width = max(0, self.contentsRect().width())
        if content_width <= 0:
            return
        max_canvas_width = max(MIN_MEDIA_WIDTH, content_width - HORIZONTAL_GAP - MIN_DETAILS_WIDTH)
        target_canvas_width = min(max_canvas_width, max(MIN_MEDIA_WIDTH, (content_width * 2) // 3))
        if self._canvas.width() != target_canvas_width:
            self._canvas.setFixedWidth(target_canvas_width)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(max(420, hint.width()), max(180, hint.height()))

    @property
    def block(self) -> Block:
        return self._block

    @property
    def title_text(self) -> str:
        return self._title_label.text()

    @property
    def meta_text(self) -> str:
        return self._meta_label.text()

    @property
    def type_badge_text(self) -> str:
        return self._type_badge.text()

    @property
    def type_badge_style(self) -> str:
        return self._type_badge.styleSheet()

    @property
    def type_badge_type_key(self) -> str:
        value = self._type_badge.property("blockType")
        return str(value or "")

    def _start_block_drag(self) -> None:
        mime = QMimeData()
        mime.setData(BLOCK_IDS_MIME, self._block.id.encode("utf-8"))
        mime.setText(self._block.id)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)


def _resolve_media_path(content: dict, project_root: Path | None) -> Path | None:
    for key in ("thumbnail_path", "preview_path", "storage_path", "file_path", "path", "url"):
        raw_value = content.get(key)
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        candidate = Path(raw_value)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        if project_root is not None:
            resolved = (project_root / candidate).resolve()
            if resolved.exists():
                return resolved
    return None


def resolve_block_asset_path(block: Block, project_root: Path | None) -> Path | None:
    return _resolve_media_path(block.content, project_root)


def _load_pixmap_safe(path: Path) -> QPixmap | None:
    if path.suffix.lower() == ".png" and not _is_valid_png_crc(path):
        return None

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap


def _is_valid_png_crc(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False

    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return False

    cursor = 8
    saw_iend = False
    while cursor + 12 <= len(data):
        length = struct.unpack(">I", data[cursor : cursor + 4])[0]
        chunk_type = data[cursor + 4 : cursor + 8]
        chunk_start = cursor + 8
        chunk_end = chunk_start + length
        crc_pos = chunk_end

        if crc_pos + 4 > len(data):
            return False

        chunk_data = data[chunk_start:chunk_end]
        expected_crc = struct.unpack(">I", data[crc_pos : crc_pos + 4])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            return False

        cursor = crc_pos + 4
        if chunk_type == b"IEND":
            saw_iend = True
            break

    return saw_iend


def _extract_video_preview(video_path: Path, *, project_root: Path | None) -> Path | None:
    if not video_path.exists() or not video_path.is_file():
        return None

    preview_path = _preview_cache_path(video_path, project_root=project_root)
    if preview_path.exists():
        return preview_path

    if _extract_video_frame_with_qt(video_path, preview_path, target_ms=1000):
        return preview_path
    if _extract_video_frame_with_qt(video_path, preview_path, target_ms=0):
        return preview_path
    return None


def _preview_cache_path(video_path: Path, *, project_root: Path | None) -> Path:
    if project_root is not None:
        cache_dir = project_root / "cache" / "previews"
    else:
        cache_dir = Path(tempfile.gettempdir()) / "sbc2_cache" / "previews"
    fingerprint = hashlib.sha1(
        f"{video_path.resolve()}:{video_path.stat().st_mtime_ns}".encode("utf-8")
    ).hexdigest()[:16]
    return cache_dir / f"{video_path.stem}_{fingerprint}.jpg"


def _extract_video_frame_with_qt(
    video_path: Path, preview_path: Path, *, target_ms: int, timeout_ms: int = 5000
) -> bool:
    state = {"started": False, "captured": False}
    loop = QEventLoop()
    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)

    def _finish() -> None:
        if loop.isRunning():
            loop.quit()

    def _on_video_frame_changed(frame: QVideoFrame) -> None:
        if state["captured"] or not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        if image.save(str(preview_path), "JPG", 90):
            state["captured"] = True
            _finish()

    def _start_decode() -> None:
        if state["started"]:
            return
        state["started"] = True
        player.setPosition(max(0, int(target_ms)))
        player.play()

    def _on_media_status_changed(status: QMediaPlayer.MediaStatus) -> None:
        if status in {QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia}:
            _start_decode()
        elif status in {QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.NoMedia}:
            _finish()

    def _on_error_changed() -> None:
        if player.error() != QMediaPlayer.Error.NoError:
            _finish()

    sink.videoFrameChanged.connect(_on_video_frame_changed)
    player.mediaStatusChanged.connect(_on_media_status_changed)
    player.errorChanged.connect(_on_error_changed)

    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(_finish)
    timeout.start(timeout_ms)

    player.setSource(QUrl.fromLocalFile(str(video_path.resolve())))
    if player.mediaStatus() in {QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia}:
        _start_decode()

    try:
        loop.exec()
    finally:
        timeout.stop()
        player.stop()
        player.deleteLater()
        sink.deleteLater()

    return state["captured"] and preview_path.exists()
