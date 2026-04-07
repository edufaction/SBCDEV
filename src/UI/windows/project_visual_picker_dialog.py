from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from domain import Block
from UI.Widgets import Carousel3DWidget, PanelContainerWidget
from UI.themes import initialize_widget_primitives
from UI.windows.window_helpers import load_app_icon


class ProjectVisualPickerDialog(QDialog):
    """Pick one IMAGE block as the project visual and confirm explicitly."""

    def __init__(
        self,
        *,
        blocks: list[Block],
        project_root: Path | None,
        initial_selected_block_id: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Project Visual")
        icon = load_app_icon()
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(980, 520)
        self.setMinimumSize(760, 460)
        self.setModal(True)

        ordered_blocks = list(blocks)
        if initial_selected_block_id:
            for index, block in enumerate(ordered_blocks):
                if block.id != initial_selected_block_id:
                    continue
                ordered_blocks.insert(0, ordered_blocks.pop(index))
                break

        self._selected_block: Block | None = ordered_blocks[0] if ordered_blocks else None

        self._title = QLabel("PROJECT VISUAL SELECTION", self)
        self._title.setProperty("section", True)
        self._subtitle = QLabel("Select one image in the carousel, then click Validate.", self)
        self._subtitle.setProperty("muted", True)
        self._selection_info = QLabel("No selection", self)
        self._selection_info.setProperty("technical", True)

        self._carousel = Carousel3DWidget(self)

        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setProperty("ghost", True)
        self._validate_button = QPushButton("Validate", self)
        self._validate_button.setProperty("primary", True)
        self._validate_button.setEnabled(self._selected_block is not None)

        self._carousel.block_selected.connect(self._on_block_selected)
        self._carousel.set_blocks(ordered_blocks, project_root=project_root)
        if initial_selected_block_id:
            self._carousel.set_selected_block_id(initial_selected_block_id, animated=False)

        actions = QWidget(self)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(9)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._cancel_button, 0)
        actions_layout.addWidget(self._validate_button, 0)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(9)
        body_layout.addWidget(self._title)
        body_layout.addWidget(self._subtitle)
        body_layout.addWidget(self._carousel, 0)
        body_layout.addWidget(self._selection_info)
        body_layout.addStretch(1)
        body_layout.addWidget(actions, 0, Qt.AlignRight)

        panel = PanelContainerWidget(self)
        panel.set_body_widget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 9, 9, 9)
        root.setSpacing(0)
        root.addWidget(panel, 1)

        self._cancel_button.clicked.connect(self.reject)
        self._validate_button.clicked.connect(self.accept)
        self._refresh_selection_text()
        initialize_widget_primitives(self)

    def selected_block(self) -> Block | None:
        return self._selected_block

    def _on_block_selected(self, block: Block) -> None:
        self._selected_block = block
        if hasattr(self, "_validate_button"):
            self._validate_button.setEnabled(True)
        self._refresh_selection_text()

    def _refresh_selection_text(self) -> None:
        if self._selected_block is None:
            self._selection_info.setText("No selection")
            return
        self._selection_info.setText(
            f"Selected: {self._selected_block.name or self._selected_block.id}  |  {self._selected_block.profile}"
        )
