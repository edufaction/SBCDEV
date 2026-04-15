from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from application import LibraryWorkspaceService
from domain import Block
from UI.Widgets import AssetGridWidget, EmptyStateWidget, MediaPreviewWidget, PanelHeaderWidget, SearchBarWidget
from UI.themes import initialize_widget_primitives

ROLE_LIBRARY_PATH = Qt.UserRole + 520


class LibraryWorkspacePanel(QWidget):
    """Library workspace panel for browsing and mounting library workspaces."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._service = LibraryWorkspaceService()
        self._project_root: Path | None = None
        self._user_libraries_root: Path | None = None
        self._application_libraries_root: Path | None = None
        self._library_entries: list[dict[str, object]] = []
        self._library_blocks: list[Block] = []
        self._selected_library_path: Path | None = None

        self._header = PanelHeaderWidget(
            "ASSET LIBRARY",
            subtitle="Browse external libraries, mount them on the project, and inspect their assets.",
            parent=self,
        )
        self._actions_frame = QFrame(self)
        self._actions_frame.setProperty("panelAlt", True)
        actions_layout = QHBoxLayout(self._actions_frame)
        actions_layout.setContentsMargins(9, 9, 9, 9)
        actions_layout.setSpacing(9)
        self._create_library_button = QPushButton("CREATE LIBRARY", self._actions_frame)
        self._create_library_button.setProperty("primary", True)
        self._mount_button = QPushButton("MOUNT", self._actions_frame)
        self._mount_button.setProperty("ghost", True)
        self._unmount_button = QPushButton("UNMOUNT", self._actions_frame)
        self._unmount_button.setProperty("ghost", True)
        self._refresh_button = QPushButton("REFRESH", self._actions_frame)
        self._refresh_button.setProperty("ghost", True)
        actions_layout.addWidget(self._create_library_button)
        actions_layout.addWidget(self._mount_button)
        actions_layout.addWidget(self._unmount_button)
        actions_layout.addWidget(self._refresh_button)
        actions_layout.addStretch(1)

        self._search_bar = SearchBarWidget(self, placeholder="Search assets by name, profile or tags")

        self._library_list = QListWidget(self)
        self._asset_grid = AssetGridWidget(self, on_block_click=self._on_block_selected)
        self._asset_grid.setMinimumWidth(420)

        self._preview_frame = QFrame(self)
        self._preview_frame.setProperty("panelAlt", True)
        preview_layout = QVBoxLayout(self._preview_frame)
        preview_layout.setContentsMargins(9, 9, 9, 9)
        preview_layout.setSpacing(9)
        preview_title = QLabel("SELECTION", self._preview_frame)
        preview_title.setProperty("section", True)
        self._preview_widget = MediaPreviewWidget(self._preview_frame)
        self._preview_widget.set_placeholder("No asset selected", "")

        details_holder = QWidget(self._preview_frame)
        details_form = QFormLayout(details_holder)
        details_form.setContentsMargins(0, 0, 0, 0)
        details_form.setSpacing(8)
        details_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        self._detail_labels: dict[str, QLabel] = {}
        for key, title in (
            ("library", "Library"),
            ("name", "Name"),
            ("type", "Type"),
            ("profile", "Profile"),
            ("tags", "Tags"),
        ):
            label = QLabel("-", details_holder)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if key in {"type", "profile"}:
                label.setProperty("technical", True)
            details_form.addRow(f"{title}:", label)
            self._detail_labels[key] = label

        self._empty = EmptyStateWidget(
            "No library available",
            description="Create a user library or mount an existing one to start browsing assets.",
            parent=self,
        )
        self._status_label = QLabel("", self)
        self._status_label.setProperty("muted", True)
        self._status_label.setProperty("technical", True)

        content_row = QWidget(self)
        content_layout = QHBoxLayout(content_row)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(9)
        content_layout.addWidget(self._library_list, 2)
        content_layout.addWidget(self._asset_grid, 5)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self._preview_widget, 1)
        preview_layout.addWidget(details_holder, 0)
        content_layout.addWidget(self._preview_frame, 3)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._actions_frame)
        root_layout.addWidget(self._search_bar)
        root_layout.addWidget(self._empty, 1)
        root_layout.addWidget(content_row, 1)
        root_layout.addWidget(self._status_label)

        self._create_library_button.clicked.connect(self._prompt_create_library)
        self._mount_button.clicked.connect(self._mount_selected_library)
        self._unmount_button.clicked.connect(self._unmount_selected_library)
        self._refresh_button.clicked.connect(self.refresh)
        self._library_list.itemSelectionChanged.connect(self._on_library_selection_changed)
        self._search_bar.text_changed.connect(lambda _text: self._refresh_asset_grid())

        initialize_widget_primitives(self)
        self._sync_visibility()

    def set_context(
        self,
        *,
        project_root: Path | None,
        user_libraries_root: Path,
        application_libraries_root: Path,
    ) -> None:
        self._project_root = project_root
        self._user_libraries_root = user_libraries_root
        self._application_libraries_root = application_libraries_root
        self.refresh()

    def refresh(self) -> None:
        roots = [root for root in (self._user_libraries_root, self._application_libraries_root) if root is not None]
        discovered = self._service.discover_libraries(roots)
        mounted = (
            self._service.list_mounted_libraries(self._project_root)
            if self._project_root is not None and self._project_root.exists()
            else []
        )
        mounted_by_path = {str(item.get("path", "") or ""): item for item in mounted}
        previous_path = str(self._selected_library_path or "")

        entries: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        for path in discovered:
            path_text = str(path.resolve())
            if path_text in seen_paths:
                continue
            seen_paths.add(path_text)
            metadata = self._service.load_library_metadata(path)
            mounted_item = mounted_by_path.get(path_text)
            entries.append(
                {
                    "path": path,
                    "label": str(metadata.get("name", "") or path.name),
                    "mounted": mounted_item is not None,
                    "enabled": bool(mounted_item.get("enabled", True)) if mounted_item is not None else False,
                    "read_only": bool(mounted_item.get("read_only", True)) if mounted_item is not None else True,
                    "mount_id": str(mounted_item.get("id", "") or "") if mounted_item is not None else "",
                    "origin": self._origin_label_for_path(path),
                }
            )

        self._library_entries = entries
        self._library_list.clear()
        for entry in self._library_entries:
            item = QListWidgetItem(self._library_item_label(entry))
            item.setData(ROLE_LIBRARY_PATH, str(entry["path"]))
            item.setToolTip(str(entry["path"]))
            self._library_list.addItem(item)

        selected_row = -1
        for index, entry in enumerate(self._library_entries):
            if str(entry["path"]) == previous_path:
                selected_row = index
                break
        if selected_row < 0 and self._library_entries:
            selected_row = 0
        if selected_row >= 0:
            self._library_list.setCurrentRow(selected_row)
        else:
            self._selected_library_path = None
            self._library_blocks = []
            self._refresh_asset_grid()
            self._clear_preview()
            self._status_label.setText("No library discovered.")
        self._sync_visibility()

    def _prompt_create_library(self) -> None:
        if self._user_libraries_root is None:
            self._status_label.setText("User libraries root is unavailable.")
            return
        raw_name, accepted = QInputDialog.getText(self, "Create Library", "Library name:")
        if not accepted:
            return
        library_name = str(raw_name or "").strip()
        if not library_name:
            return
        safe_name = library_name.replace("/", "_").replace("\\", "_").strip()
        base_path = self._user_libraries_root / safe_name
        library_path = base_path
        suffix = 2
        while library_path.exists():
            library_path = self._user_libraries_root / f"{safe_name}_{suffix}"
            suffix += 1
        self._service.create_library(library_path, name=library_name)
        self.refresh()
        self._select_library_path(library_path)
        self._status_label.setText(f"Library created: {library_path.name}")

    def _mount_selected_library(self) -> None:
        if self._project_root is None:
            self._status_label.setText("Open a project to mount a library.")
            return
        selected = self._selected_entry()
        if selected is None:
            return
        self._service.mount_library(
            self._project_root,
            library_path=Path(selected["path"]),
            label=str(selected["label"]),
            enabled=True,
            read_only=True,
        )
        self.refresh()
        self._select_library_path(Path(selected["path"]))
        self._status_label.setText(f"Library mounted: {selected['label']}")

    def _unmount_selected_library(self) -> None:
        if self._project_root is None:
            self._status_label.setText("Open a project to unmount a library.")
            return
        selected = self._selected_entry()
        if selected is None:
            return
        self._service.unmount_library(self._project_root, library_path=Path(selected["path"]))
        self.refresh()
        self._select_library_path(Path(selected["path"]))
        self._status_label.setText(f"Library unmounted: {selected['label']}")

    def _on_library_selection_changed(self) -> None:
        selected = self._selected_entry()
        if selected is None:
            self._selected_library_path = None
            self._library_blocks = []
            self._refresh_asset_grid()
            self._clear_preview()
            self._sync_visibility()
            return
        library_path = Path(selected["path"])
        self._selected_library_path = library_path
        try:
            loaded = self._service.load_library_blocks(library_path)
        except Exception:
            loaded = []
        self._library_blocks = [block for block in loaded if block.profile != "workspace_root"]
        self._refresh_asset_grid()
        self._clear_preview()
        self._detail_labels["library"].setText(str(selected["label"]))
        self._status_label.setText(f"{len(self._library_blocks)} block(s) in {selected['label']}")
        self._sync_visibility()

    def _refresh_asset_grid(self) -> None:
        filtered = self._filtered_blocks()
        self._asset_grid.set_blocks(filtered, project_root=self._selected_library_path)
        self._empty.setVisible(not self._library_entries)

    def _filtered_blocks(self) -> list[Block]:
        query = self._search_bar.text().strip().lower()
        if not query:
            return list(self._library_blocks)
        results: list[Block] = []
        for block in self._library_blocks:
            haystack = " ".join(
                [
                    block.id,
                    block.name,
                    block.profile,
                    block.type.value,
                    " ".join(block.tags),
                ]
            ).lower()
            if query in haystack:
                results.append(block)
        return results

    def _on_block_selected(self, block: Block) -> None:
        self._detail_labels["name"].setText(block.name or block.id)
        self._detail_labels["type"].setText(block.type.value)
        self._detail_labels["profile"].setText(block.profile or "-")
        self._detail_labels["tags"].setText(", ".join(block.tags) if block.tags else "-")
        self._preview_widget.set_media(
            {
                "type": block.type.value,
                "content": block.content,
                "project_root": self._selected_library_path,
                "text": block.prompt_generated or block.description,
            }
        )

    def _clear_preview(self) -> None:
        self._preview_widget.clear()
        for key, label in self._detail_labels.items():
            if key == "library" and self._selected_entry() is not None:
                continue
            label.setText("-")

    def _sync_visibility(self) -> None:
        has_libraries = bool(self._library_entries)
        self._library_list.setVisible(has_libraries)
        self._asset_grid.setVisible(has_libraries)
        self._preview_frame.setVisible(has_libraries)
        self._mount_button.setEnabled(self._can_mount_selected())
        self._unmount_button.setEnabled(self._can_unmount_selected())
        self._create_library_button.setEnabled(self._user_libraries_root is not None)

    def _can_mount_selected(self) -> bool:
        selected = self._selected_entry()
        return selected is not None and self._project_root is not None and not bool(selected["mounted"])

    def _can_unmount_selected(self) -> bool:
        selected = self._selected_entry()
        return selected is not None and self._project_root is not None and bool(selected["mounted"])

    def _selected_entry(self) -> dict[str, object] | None:
        item = self._library_list.currentItem()
        if item is None:
            return None
        selected_path = str(item.data(ROLE_LIBRARY_PATH) or "")
        for entry in self._library_entries:
            if str(entry["path"]) == selected_path:
                return entry
        return None

    def _select_library_path(self, library_path: Path) -> None:
        target = str(library_path.resolve())
        for row in range(self._library_list.count()):
            item = self._library_list.item(row)
            if item is None:
                continue
            if str(item.data(ROLE_LIBRARY_PATH) or "") == target:
                self._library_list.setCurrentRow(row)
                return

    @staticmethod
    def _origin_label_for_path(path: Path) -> str:
        parts = {part.upper() for part in path.parts}
        if "APPLICATION" in parts:
            return "APPLICATION"
        if "USER" in parts:
            return "USER"
        return "LOCAL"

    @staticmethod
    def _library_item_label(entry: dict[str, object]) -> str:
        prefix = "[MOUNTED] " if bool(entry["mounted"]) else ""
        return f"{prefix}{entry['label']} ({entry['origin']})"
