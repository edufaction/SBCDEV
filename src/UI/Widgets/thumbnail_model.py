from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QMimeData,
    QModelIndex,
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    Signal,
)
from PySide6.QtGui import QImage, QPixmap

from domain import Block, BlockType
from UI.Widgets.thumbnail_utils import (
    extract_video_preview,
    load_image_safe,
    resolve_media_path,
)

BLOCK_ROLE = Qt.UserRole + 1
PIXMAP_ROLE = Qt.UserRole + 2
BLOCK_IDS_MIME = "application/x-sbc2-block-ids"


class _LoaderSignals(QObject):
    loaded = Signal(str, QImage)


class _ThumbnailTask(QRunnable):
    def __init__(self, block: Block, project_root: Path | None):
        super().__init__()
        self.block = block
        self.project_root = project_root
        self.signals = _LoaderSignals()

    def run(self) -> None:
        media_path = resolve_media_path(self.block.content, self.project_root)
        if not media_path:
            return

        img = None
        if self.block.type == BlockType.VIDEO:
            preview_path = extract_video_preview(media_path, project_root=self.project_root)
            if preview_path is not None:
                img = QImage(str(preview_path))
        elif self.block.type == BlockType.IMAGE:
            img = load_image_safe(media_path)

        if img is not None and not img.isNull():
            self.signals.loaded.emit(self.block.id, img)


class ThumbnailListModel(QAbstractListModel):
    """Model that exposes Block data and asynchronous pixmaps for delegates."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._blocks: list[Block] = []
        self._project_root: Path | None = None
        self._pixmaps: dict[str, QPixmap] = {}
        self._loading: set[str] = set()
        self._thread_pool = QThreadPool.globalInstance()

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self.beginResetModel()
        self._blocks = list(blocks)
        self._project_root = project_root
        self._pixmaps.clear()
        self._loading.clear()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._blocks)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemIsDragEnabled
        return base

    def mimeTypes(self) -> list[str]:
        return [BLOCK_IDS_MIME]

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        mime = QMimeData()
        block_ids: list[str] = []
        seen: set[str] = set()
        for index in indexes:
            block = self.block_at(index)
            if block is None or block.id in seen:
                continue
            seen.add(block.id)
            block_ids.append(block.id)
        payload = "\n".join(block_ids)
        mime.setData(BLOCK_IDS_MIME, payload.encode("utf-8"))
        mime.setText(payload)
        return mime

    def supportedDragActions(self) -> Qt.DropActions:
        return Qt.CopyAction

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._blocks)):
            return None

        block = self._blocks[index.row()]

        if role == BLOCK_ROLE:
            return block

        if role == PIXMAP_ROLE:
            if block.id in self._pixmaps:
                return self._pixmaps[block.id]

            if block.id not in self._loading and block.type in {BlockType.IMAGE, BlockType.VIDEO}:
                self._loading.add(block.id)
                task = _ThumbnailTask(block, self._project_root)
                task.signals.loaded.connect(self._on_image_loaded)
                self._thread_pool.start(task)
            return None

        return None

    def _on_image_loaded(self, block_id: str, image: QImage) -> None:
        self._pixmaps[block_id] = QPixmap.fromImage(image)
        for row, block in enumerate(self._blocks):
            if block.id == block_id:
                idx = self.index(row, 0)
                self.dataChanged.emit(idx, idx, [PIXMAP_ROLE])
                break

    def block_at(self, index: QModelIndex) -> Block | None:
        if not index.isValid() or not (0 <= index.row() < len(self._blocks)):
            return None
        return self._blocks[index.row()]
