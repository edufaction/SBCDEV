from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from domain import Block
from UI.Widgets import HorizontalCarouselWidget, PanelContainerWidget, resolve_block_asset_path
from UI.themes import initialize_widget_primitives
from UI.windows.window_helpers import load_app_icon, open_with_system_default_app


class MediaCarouselWindow(QMainWindow):
    """Dedicated window displaying IMAGE/VIDEO blocks in a horizontal carousel."""

    def __init__(self, *, blocks: list[Block] | None = None, project_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SBC2 - Media Carousel")
        icon = load_app_icon()
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(1080, 540)
        self.setMinimumSize(760, 420)

        self._project_root = project_root
        self._all_blocks = list(blocks or [])

        self._title = QLabel("MEDIA CAROUSEL (IMAGE / VIDEO)", self)
        self._title.setProperty("section", True)
        self._subtitle = QLabel("Horizontal thumbnails from project blocks.", self)
        self._subtitle.setProperty("muted", True)
        self._selection_info = QLabel("No selection", self)
        self._selection_info.setProperty("technical", True)

        self._carousel = HorizontalCarouselWidget(self)
        self._carousel.block_selected.connect(self._on_block_selected)
        self._carousel.block_activated.connect(self._open_asset)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(9)
        body_layout.addWidget(self._title)
        body_layout.addWidget(self._subtitle)
        body_layout.addWidget(self._carousel, 0)
        body_layout.addStretch(1)
        body_layout.addWidget(self._selection_info)

        self._panel = PanelContainerWidget(self)
        self._panel.set_body_widget(body)
        self.setCentralWidget(self._panel)

        self.set_blocks(self._all_blocks, project_root=self._project_root)
        initialize_widget_primitives(self)

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self._all_blocks = list(blocks)
        self._project_root = project_root
        self._carousel.set_blocks(self._all_blocks, project_root=self._project_root)
        eligible = [block for block in self._all_blocks if block.type.value in {"image", "video"}]
        self._subtitle.setText(f"Horizontal thumbnails from project blocks. Items: {len(eligible)}")
        if not eligible:
            self._selection_info.setText("No selection")

    def _on_block_selected(self, block: Block) -> None:
        self._selection_info.setText(f"Selected: {block.name or block.id}  |  {block.type.value}  |  {block.profile}")

    def _open_asset(self, block: Block) -> None:
        asset_path = resolve_block_asset_path(block, self._project_root)
        if asset_path is None or not asset_path.exists():
            return
        open_with_system_default_app(asset_path)
