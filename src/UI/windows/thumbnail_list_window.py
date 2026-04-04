from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QMainWindow, QSplitter, QStackedWidget

from domain import Block
from UI.Widgets import (
    AssetGridWidget,
    BlockPropertyWidget,
    FilterBarWidget,
    ModeSwitchWidget,
    PanelContainerWidget,
    SearchBarWidget,
    ThumbnailListView,
    resolve_block_asset_path,
)
from UI.themes import initialize_widget_primitives
from UI.windows.window_helpers import load_app_icon, open_with_system_default_app


class ThumbnailListWindow(QMainWindow):
    """Secondary window focused on the thumbnail list view."""

    def __init__(self, *, blocks: list[Block] | None = None, project_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SBC2 - Thumbnail List")
        icon = load_app_icon()
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(900, 680)
        self.setMinimumSize(640, 420)

        if blocks is None:
            blocks = []
        self._all_blocks = list(blocks)
        self._project_root = project_root

        self._search_bar = SearchBarWidget(self, placeholder="Search by tags...")
        # Compatibility alias kept for existing tests/callers.
        self._tag_search_input = self._search_bar.line_edit
        self._type_filter_combo = QComboBox(self)
        self._profile_filter_combo = QComboBox(self)
        self._mode_switch = ModeSwitchWidget(self, default_mode="list")
        self._filter_bar = FilterBarWidget(self)
        self._filter_bar.set_search_widget(self._search_bar, stretch=2)
        self._filter_bar.add_filter_widget(self._type_filter_combo, stretch=1)
        self._filter_bar.add_filter_widget(self._profile_filter_combo, stretch=1)
        self._filter_bar.add_filter_widget(self._mode_switch, stretch=0)
        self._build_filter_controls()

        self._list_view = ThumbnailListView(
            self,
            on_block_click=self._on_block_selected,
            on_block_double_click=self._open_asset_in_default_app,
        )
        self._grid_view = AssetGridWidget(
            self,
            on_block_click=self._on_block_selected,
            on_block_double_click=self._open_asset_in_default_app,
        )
        self._assets_stack = QStackedWidget(self)
        self._assets_stack.addWidget(self._list_view)
        self._assets_stack.addWidget(self._grid_view)
        self._assets_stack.setCurrentWidget(self._list_view)
        self._property_widget = BlockPropertyWidget(self)
        self._content_splitter = QSplitter(Qt.Horizontal, self)
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.addWidget(self._assets_stack)
        self._content_splitter.addWidget(self._property_widget)
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 2)
        self._content_splitter.setSizes([560, 340])
        self._apply_filters()

        self._panel = PanelContainerWidget(self)
        self._panel.set_header_widget(self._filter_bar)
        self._panel.set_body_widget(self._content_splitter)
        self.setCentralWidget(self._panel)
        initialize_widget_primitives(self)

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self._all_blocks = list(blocks)
        self._project_root = project_root
        self._rebuild_filter_controls()
        self._apply_filters()

    def _open_asset_in_default_app(self, block: Block) -> None:
        asset_path = resolve_block_asset_path(block, self._project_root)
        if asset_path is None or not asset_path.exists():
            return
        open_with_system_default_app(asset_path)

    def _on_block_selected(self, block: Block) -> None:
        self._property_widget.set_block(block)

    def _build_filter_controls(self) -> None:
        self._rebuild_filter_controls()
        self._search_bar.text_changed.connect(self._apply_filters)
        self._type_filter_combo.currentIndexChanged.connect(self._apply_filters)
        self._profile_filter_combo.currentIndexChanged.connect(self._apply_filters)
        self._mode_switch.mode_changed.connect(self._on_mode_changed)

    def _rebuild_filter_controls(self) -> None:
        selected_type = str(self._type_filter_combo.currentData() or "")
        selected_profile = str(self._profile_filter_combo.currentData() or "")

        self._type_filter_combo.blockSignals(True)
        self._profile_filter_combo.blockSignals(True)
        self._type_filter_combo.clear()
        self._profile_filter_combo.clear()
        self._type_filter_combo.addItem("All types", "")
        self._profile_filter_combo.addItem("All profiles", "")

        type_values = sorted({block.type.value for block in self._all_blocks})
        for type_value in type_values:
            self._type_filter_combo.addItem(type_value.upper(), type_value)

        profile_values = sorted({block.profile for block in self._all_blocks if block.profile})
        for profile in profile_values:
            self._profile_filter_combo.addItem(profile, profile)

        target_type_index = self._type_filter_combo.findData(selected_type)
        self._type_filter_combo.setCurrentIndex(target_type_index if target_type_index >= 0 else 0)
        target_profile_index = self._profile_filter_combo.findData(selected_profile)
        self._profile_filter_combo.setCurrentIndex(target_profile_index if target_profile_index >= 0 else 0)
        self._type_filter_combo.blockSignals(False)
        self._profile_filter_combo.blockSignals(False)

    def _on_mode_changed(self, mode: str) -> None:
        if mode == "grid":
            self._assets_stack.setCurrentWidget(self._grid_view)
            return
        self._assets_stack.setCurrentWidget(self._list_view)

    def _apply_filters(self, *_: object) -> None:
        tag_terms = [part for part in self._search_bar.text().strip().lower().split() if part]
        selected_type = str(self._type_filter_combo.currentData() or "")
        selected_profile = str(self._profile_filter_combo.currentData() or "")

        filtered: list[Block] = []
        for block in self._all_blocks:
            if selected_type and block.type.value != selected_type:
                continue
            if selected_profile and block.profile != selected_profile:
                continue
            if tag_terms:
                block_tags = [tag.lower() for tag in block.tags if isinstance(tag, str)]
                if not block_tags:
                    continue
                if not all(any(term in tag for tag in block_tags) for term in tag_terms):
                    continue
            filtered.append(block)

        self._list_view.set_blocks(filtered, project_root=self._project_root)
        self._grid_view.set_blocks(filtered, project_root=self._project_root)
        self._property_widget.set_block(None)
