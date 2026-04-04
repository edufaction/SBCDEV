from __future__ import annotations

import hashlib
import struct
import tempfile
import zlib
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QVideoFrame, QVideoSink

from domain import Block


def resolve_media_path(content: dict, project_root: Path | None) -> Path | None:
    """Find absolute media path from block content mapping."""
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
    return resolve_media_path(block.content, project_root)


def load_image_safe(path: Path) -> QImage | None:
    """Load QImage safely with PNG CRC check validation."""
    if path.suffix.lower() == ".png" and not is_valid_png_crc(path):
        return None
    img = QImage(str(path))
    if img.isNull():
        return None
    return img


def is_valid_png_crc(path: Path) -> bool:
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


def preview_cache_path(video_path: Path, *, project_root: Path | None) -> Path:
    if project_root is not None:
        cache_dir = project_root / "cache" / "previews"
    else:
        cache_dir = Path(tempfile.gettempdir()) / "sbc2_cache" / "previews"
    fingerprint = hashlib.sha1(
        f"{video_path.resolve()}:{video_path.stat().st_mtime_ns}".encode("utf-8")
    ).hexdigest()[:16]
    return cache_dir / f"{video_path.stem}_{fingerprint}.jpg"


def extract_video_preview(video_path: Path, *, project_root: Path | None) -> Path | None:
    if not video_path.exists() or not video_path.is_file():
        return None

    preview_path = preview_cache_path(video_path, project_root=project_root)
    if preview_path.exists():
        return preview_path

    if _extract_video_frame_with_qt(video_path, preview_path, target_ms=1000):
        return preview_path
    if _extract_video_frame_with_qt(video_path, preview_path, target_ms=0):
        return preview_path
    return None


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
