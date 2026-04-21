from __future__ import annotations

from pathlib import Path

from domain import Block


class SecondaryWindowsController:
    """Owns the lifecycle of secondary windows and keeps them in sync with project state."""

    def __init__(
        self,
        *,
        thumbnail_window_cls,
        media_carousel_window_cls,
        free_tree_window_cls,
        persist_blocks,
        parent,
    ) -> None:
        self._thumbnail_window_cls = thumbnail_window_cls
        self._media_carousel_window_cls = media_carousel_window_cls
        self._free_tree_window_cls = free_tree_window_cls
        self._persist_blocks = persist_blocks
        self._parent = parent
        self._thumbnail_window = None
        self._media_carousel_window = None
        self._free_tree_window = None

    @property
    def thumbnail_window(self):
        return self._thumbnail_window

    @property
    def media_carousel_window(self):
        return self._media_carousel_window

    @property
    def free_tree_window(self):
        return self._free_tree_window

    def open_thumbnail_window(self, *, blocks: list[Block], project_root: Path | None) -> None:
        if self._thumbnail_window is None:
            self._thumbnail_window = self._thumbnail_window_cls(blocks=blocks, project_root=project_root)
            self._thumbnail_window.blocks_changed.connect(self._persist_blocks)
            self._thumbnail_window.destroyed.connect(lambda *_: setattr(self, "_thumbnail_window", None))
        else:
            self._thumbnail_window.set_blocks(blocks, project_root=project_root)
        self._show_window(self._thumbnail_window)

    def open_media_carousel_window(self, *, blocks: list[Block], project_root: Path | None) -> None:
        if self._media_carousel_window is None:
            self._media_carousel_window = self._media_carousel_window_cls(blocks=blocks, project_root=project_root)
            self._media_carousel_window.destroyed.connect(lambda *_: setattr(self, "_media_carousel_window", None))
        else:
            self._media_carousel_window.set_blocks(blocks, project_root=project_root)
        self._show_window(self._media_carousel_window)

    def open_free_tree_window(self, *, blocks: list[Block], project_root: Path | None) -> None:
        if self._free_tree_window is None:
            self._free_tree_window = self._free_tree_window_cls(
                blocks=blocks,
                persisted_tree=None,
                project_root=project_root,
            )
            self._free_tree_window.blocks_changed.connect(self._persist_blocks)
            self._free_tree_window.destroyed.connect(lambda *_: setattr(self, "_free_tree_window", None))
        self._show_window(self._free_tree_window)

    def sync_project_blocks(self, *, blocks: list[Block], project_root: Path | None) -> None:
        if self._thumbnail_window is not None:
            self._thumbnail_window.set_blocks(blocks, project_root=project_root)
        if self._media_carousel_window is not None:
            self._media_carousel_window.set_blocks(blocks, project_root=project_root)

    def close_all(self) -> None:
        if self._thumbnail_window is not None:
            self._thumbnail_window.close()
            self._thumbnail_window.deleteLater()
            self._thumbnail_window = None
        if self._media_carousel_window is not None:
            self._media_carousel_window.close()
            self._media_carousel_window.deleteLater()
            self._media_carousel_window = None
        if self._free_tree_window is not None:
            self._free_tree_window.close()
            self._free_tree_window.deleteLater()
            self._free_tree_window = None

    @staticmethod
    def _show_window(window) -> None:
        window.show()
        window.raise_()
        window.activateWindow()
