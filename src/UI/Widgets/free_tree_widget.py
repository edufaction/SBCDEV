from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from application.block_template_service import BlockTemplateService
from application.free_tree_workspace_controller import FreeTreeItemSnapshot, FreeTreeWorkspaceController
from domain import Block, BlockAccessMode, BlockDomain, BlockProvenanceKind, BlockType, FreeTree, FreeTreeNode
from infrastructure.storage import ProjectStorageService
from UI.Widgets.panel_header_widget import PanelHeaderWidget
from UI.themes import active_theme_tokens_ref
from UI.themes import initialize_widget_primitives

BLOCK_IDS_MIME = "application/x-sbc2-block-ids"
ROLE_NODE_ID = Qt.UserRole + 300
ROLE_NODE_KIND = Qt.UserRole + 301
ROLE_BLOCK_ID = Qt.UserRole + 302
ROLE_NODE_LOCKED = Qt.UserRole + 303


class _FreeTreeView(QTreeWidget):
    structure_changed = Signal()
    external_blocks_dropped = Signal(object, str)
    external_files_dropped = Signal(object, str)

    @staticmethod
    def _block_ids_from_mime(event) -> list[str]:
        mime = event.mimeData()
        if mime is None:
            return []
        if mime.hasFormat(BLOCK_IDS_MIME):
            try:
                payload = bytes(mime.data(BLOCK_IDS_MIME)).decode("utf-8")
                ids = [line.strip() for line in payload.splitlines() if line.strip()]
                if ids:
                    return ids
            except Exception:
                pass
        text_payload = mime.text() or ""
        return [line.strip() for line in text_payload.splitlines() if line.strip()]

    @staticmethod
    def _file_paths_from_mime(event) -> list[str]:
        mime = event.mimeData()
        if mime is None:
            return []
        paths: list[str] = []
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            local = url.toLocalFile().strip()
            if local:
                paths.append(local)
        return paths

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._block_ids_from_mime(event) or self._file_paths_from_mime(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._block_ids_from_mime(event) or self._file_paths_from_mime(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        file_paths = self._file_paths_from_mime(event)
        if file_paths:
            drop_point = event.position().toPoint() if hasattr(event, "position") else event.pos()
            target_item = self.itemAt(drop_point)
            target_node_id = ""
            if target_item is not None:
                target_node_id = str(target_item.data(0, ROLE_NODE_ID) or "")
            self.external_files_dropped.emit(file_paths, target_node_id)
            event.acceptProposedAction()
            return

        block_ids = self._block_ids_from_mime(event)
        if block_ids:
            drop_point = event.position().toPoint() if hasattr(event, "position") else event.pos()
            target_item = self.itemAt(drop_point)
            target_node_id = ""
            if target_item is not None:
                target_node_id = str(target_item.data(0, ROLE_NODE_ID) or "")
            self.external_blocks_dropped.emit(block_ids, target_node_id)
            event.acceptProposedAction()
            return
        super().dropEvent(event)
        self.structure_changed.emit()


class FreeTreeWidget(QWidget):
    """Editable FreeTree widget with folder management and block drag-and-drop."""

    tree_changed = Signal(object)
    blocks_changed = Signal(object)
    block_selected = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self._interactive = True
        self._actions_visible = True
        self._icons_dir = Path(__file__).resolve().parents[2] / "icons"
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._project_root: Path | None = None
        self._storage_service = ProjectStorageService()
        self._template_service = BlockTemplateService()
        self._controller = FreeTreeWorkspaceController()
        self._blocks: list[Block] = []
        self._blocks_by_id: dict[str, Block] = {}
        self._tree = FreeTree()
        self._locked_node_ids: set[str] = set()

        self._header = PanelHeaderWidget("PROJECT FREE TREE", parent=self)
        self._add_folder_button = QPushButton("Add Folder", self)
        self._add_folder_button.setProperty("ghost", True)
        self._delete_folder_button = QPushButton("Delete Folder", self)
        self._delete_folder_button.setProperty("ghost", True)
        self._import_button = QPushButton("Add / Import", self)
        self._import_button.setProperty("ghost", True)
        self._add_template_button = QPushButton("Add Character Template", self)
        self._add_template_button.setProperty("ghost", True)
        self._delete_block_button = QPushButton("Delete Block", self)
        self._delete_block_button.setProperty("ghost", True)
        self._header.set_action_widgets(
            [
                self._add_folder_button,
                self._delete_folder_button,
                self._import_button,
                self._add_template_button,
                self._delete_block_button,
            ]
        )

        self._tree_view = _FreeTreeView(self)
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tree_view.setDragDropMode(QAbstractItemView.DragDrop)
        self._tree_view.setDefaultDropAction(Qt.MoveAction)
        self._tree_view.setDragEnabled(True)
        self._tree_view.setAcceptDrops(True)
        self._tree_view.setDropIndicatorShown(True)
        self._tree_view.structure_changed.connect(self._sync_tree_from_ui)
        self._tree_view.external_blocks_dropped.connect(self._handle_external_block_drop)
        self._tree_view.external_files_dropped.connect(self._handle_external_files_drop)
        self._tree_view.currentItemChanged.connect(self._handle_selection_changed)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(9, 9, 9, 9)
        root_layout.setSpacing(9)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._tree_view, 1)

        self._add_folder_button.clicked.connect(self._prompt_add_folder)
        self._delete_folder_button.clicked.connect(self._delete_selected_folder)
        self._import_button.clicked.connect(self._prompt_import_into_selected_container)
        self._add_template_button.clicked.connect(self._prompt_add_character_template)
        self._delete_block_button.clicked.connect(self._prompt_delete_selected_block)
        self._sync_state_from_controller()
        initialize_widget_primitives(self)
        self._refresh_action_state()

    def set_header_visible(self, visible: bool) -> None:
        self._header.setVisible(bool(visible))

    def set_actions_visible(self, visible: bool) -> None:
        self._actions_visible = bool(visible)
        for button in (
            self._add_folder_button,
            self._delete_folder_button,
            self._import_button,
            self._add_template_button,
            self._delete_block_button,
        ):
            button.setVisible(self._actions_visible)
        self._refresh_action_state()

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = bool(enabled)
        self._tree_view.setDragEnabled(self._interactive)
        self._tree_view.setAcceptDrops(self._interactive)
        self._tree_view.setDropIndicatorShown(self._interactive)
        if self._interactive:
            self._tree_view.setDragDropMode(QAbstractItemView.DragDrop)
        else:
            self._tree_view.setDragDropMode(QAbstractItemView.NoDragDrop)
        self._refresh_action_state()

    def set_blocks(
        self,
        blocks: list[Block],
        *,
        persisted_tree: FreeTree | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._project_root = project_root
        self._controller.set_blocks(blocks, persisted_tree=persisted_tree)
        self._sync_state_from_controller()
        self._render_tree()

    def add_folder(self, name: str, parent_node_id: str | None = None) -> str | None:
        folder_id = self._controller.add_folder(name, parent_node_id=parent_node_id)
        if folder_id is None:
            return None
        self._sync_state_from_controller()
        self._render_tree()
        self._select_node(folder_id)
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))
        return folder_id

    def move_node(self, node_id: str, new_parent_id: str | None) -> None:
        self._controller.move_node(node_id, new_parent_id)
        self._sync_state_from_controller()
        self._render_tree()
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))

    def set_block_relative_path(self, block_id: str, container_id: str, relative_path: str) -> bool:
        changed = self._controller.update_block_relative_path(
            block_id=block_id,
            parent_container_id=container_id,
            relative_path=relative_path,
        )
        if not changed:
            return False
        self._sync_state_from_controller()
        self._render_tree()
        selected_node = self.find_node_id_for_block(block_id)
        if selected_node:
            self._select_node(selected_node)
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))
        return True

    def remove_folder(self, folder_node_id: str) -> None:
        self._controller.remove_folder(folder_node_id)
        self._sync_state_from_controller()
        self._render_tree()
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))

    def find_node_id_for_block(self, block_id: str) -> str | None:
        return self._controller.find_node_id_for_block(block_id)

    def current_tree(self) -> FreeTree:
        return FreeTree(
            root_ids=list(self._tree.root_ids),
            nodes={
                node_id: FreeTreeNode(
                    id=node.id,
                    kind=node.kind,
                    name=node.name,
                    block_id=node.block_id,
                    children=list(node.children),
                )
                for node_id, node in self._tree.nodes.items()
            },
        )

    def _sync_state_from_controller(self) -> None:
        self._blocks = self._controller.blocks
        self._blocks_by_id = self._controller.blocks_by_id
        self._tree = self._controller.tree
        self._locked_node_ids = self._controller.locked_node_ids

    def _prompt_add_folder(self) -> None:
        current_item = self._tree_view.currentItem()
        parent_node_id = None
        if current_item is not None:
            current_kind = str(current_item.data(0, ROLE_NODE_KIND) or "")
            current_node_id = str(current_item.data(0, ROLE_NODE_ID) or "")
            if current_kind == "folder":
                parent_node_id = current_node_id
            elif current_kind == "block_ref":
                parent_node_id = self._controller.find_parent_folder_id(current_node_id)

        name, ok = QInputDialog.getText(self, "Add Folder", "Folder name:")
        if ok:
            self.add_folder(name, parent_node_id=parent_node_id)

    def _delete_selected_folder(self) -> None:
        item = self._tree_view.currentItem()
        if item is None:
            return
        node_id = str(item.data(0, ROLE_NODE_ID) or "")
        node = self._tree.nodes.get(node_id)
        if node is None or node.kind != "folder":
            return
        self.remove_folder(node_id)

    def _prompt_import_into_selected_container(self) -> None:
        if self._project_root is None or not self._project_root.exists():
            return
        target_folder_id = self._import_target_folder_id()
        if not target_folder_id:
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Files to Container",
            str(self._project_root),
            "All Files (*)",
        )
        if not files:
            return
        self._handle_external_files_drop(files, target_folder_id)

    def _prompt_add_character_template(self) -> None:
        target_folder_id = self._template_target_folder_id()
        if not target_folder_id:
            QMessageBox.warning(self, "Add Character Template", "No compatible container was found.")
            return

        character_name, accepted = QInputDialog.getText(self, "Add Character Template", "Character name:")
        if not accepted:
            return
        resolved_name = character_name.strip()
        if not resolved_name:
            return

        created_blocks = self._template_service.instantiate_character_template(character_name=resolved_name)
        created_root_node_id = self._insert_template_blocks(created_blocks, target_folder_id=target_folder_id)
        if created_root_node_id is None:
            QMessageBox.warning(self, "Add Character Template", "Template could not be inserted in the target.")
            return

        persisted_tree = self.current_tree()
        self._controller.set_blocks(self._blocks, persisted_tree=persisted_tree)
        self._sync_state_from_controller()
        self._render_tree()
        self._select_node(created_root_node_id)
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))

    def _prompt_delete_selected_block(self) -> None:
        selected_block = self._selected_block()
        if selected_block is None:
            return
        block_ids_to_delete = self._collect_block_descendants(selected_block.id)
        if not block_ids_to_delete:
            return
        if not self._confirm_block_deletion(selected_block, len(block_ids_to_delete) - 1):
            return
        self._delete_blocks(block_ids_to_delete)

    def _render_tree(self) -> None:
        self._tree_view.clear()
        for node_id in self._tree.root_ids:
            self._add_node_item(node_id, None)
        self._tree_view.expandAll()
        self._refresh_action_state()
        self._emit_selected_block()

    def _add_node_item(self, node_id: str, parent_item: QTreeWidgetItem | None) -> None:
        node = self._tree.nodes.get(node_id)
        if node is None:
            return

        item = QTreeWidgetItem([node.name])
        item.setData(0, ROLE_NODE_ID, node.id)
        item.setData(0, ROLE_NODE_KIND, node.kind)
        item.setData(0, ROLE_BLOCK_ID, node.block_id or "")
        item.setData(0, ROLE_NODE_LOCKED, node.id in self._locked_node_ids)

        is_locked = node.id in self._locked_node_ids
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if not is_locked:
            flags |= Qt.ItemIsDragEnabled
        if node.kind == "folder":
            item.setIcon(0, self._icon_for("project_folder_open.svg", self._folder_icon_color(node)))
            flags |= Qt.ItemIsDropEnabled
            container_block = self._blocks_by_id.get(node.block_id or "")
            if container_block is not None and container_block.type == BlockType.CONTAINER:
                item.setToolTip(0, f"{container_block.profile} | {container_block.type.value} | non deletable")
        else:
            block = self._blocks_by_id.get(node.block_id or "")
            if block is not None:
                item.setText(0, block.name or block.id)
                item.setToolTip(0, f"{block.profile} | {block.type.value}")
                item.setIcon(0, self._icon_for(self._icon_for_profile(block.profile), self._on_surface_variant_color()))
            flags &= ~Qt.ItemIsDropEnabled
        item.setFlags(flags)

        if parent_item is None:
            self._tree_view.addTopLevelItem(item)
        else:
            parent_item.addChild(item)

        for child_id in node.children:
            self._add_node_item(child_id, item)

    def _snapshot_from_item(self, item: QTreeWidgetItem) -> FreeTreeItemSnapshot:
        node_id = str(item.data(0, ROLE_NODE_ID) or "")
        node_kind = str(item.data(0, ROLE_NODE_KIND) or "folder")
        block_id_raw = str(item.data(0, ROLE_BLOCK_ID) or "")
        children = [self._snapshot_from_item(item.child(i)) for i in range(item.childCount())]
        return FreeTreeItemSnapshot(
            node_id=node_id,
            node_kind=node_kind,
            name=item.text(0),
            block_id=(block_id_raw or None),
            children=children,
        )

    def _sync_tree_from_ui(self) -> None:
        roots = [
            self._snapshot_from_item(self._tree_view.topLevelItem(i))
            for i in range(self._tree_view.topLevelItemCount())
        ]
        self._controller.rebuild_from_snapshot(roots)
        self._sync_state_from_controller()
        self._render_tree()
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))

    def _handle_external_block_drop(self, block_ids_payload: object, target_node_id: str) -> None:
        if not isinstance(block_ids_payload, list):
            return
        source_block_ids = [str(value).strip() for value in block_ids_payload if str(value).strip()]
        if not source_block_ids:
            return

        parent_folder_id = self._resolve_drop_parent_folder_id(target_node_id)
        created_block_ids: list[str] = []

        for source_block_id in source_block_ids:
            source_block = self._blocks_by_id.get(source_block_id)
            if source_block is None or source_block.type == BlockType.CONTAINER:
                continue

            target_container = self._nearest_container_block_for_node(parent_folder_id)
            created = self._clone_block_for_drop(
                source_block,
                target_domain=(target_container.domain if target_container is not None else None),
            )
            self._blocks.append(created)
            self._blocks_by_id[created.id] = created
            created_block_ids.append(created.id)

            node_id = self._new_tree_block_node_id(created.id)
            self._tree.nodes[node_id] = FreeTreeNode(
                id=node_id,
                kind="block_ref",
                name=created.name or created.id,
                block_id=created.id,
            )
            if parent_folder_id is None:
                self._tree.root_ids.append(node_id)
            else:
                parent = self._tree.nodes.get(parent_folder_id)
                if parent is None:
                    self._tree.root_ids.append(node_id)
                else:
                    parent.children.append(node_id)
                    self._append_to_nearest_container_contains(parent.id, created.id)

        if not created_block_ids:
            return

        persisted_tree = self.current_tree()
        self._controller.set_blocks(self._blocks, persisted_tree=persisted_tree)
        self._sync_state_from_controller()
        self._render_tree()
        self._select_node(self.find_node_id_for_block(created_block_ids[-1]) or "")
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))

    def _handle_external_files_drop(self, file_paths_payload: object, target_node_id: str) -> None:
        if not isinstance(file_paths_payload, list):
            return
        if self._project_root is None or not self._project_root.exists():
            return

        paths = [Path(str(raw)).expanduser() for raw in file_paths_payload if str(raw).strip()]
        file_paths = [path.resolve() for path in paths if path.exists() and path.is_file()]
        if not file_paths:
            return

        parent_folder_id = self._resolve_drop_parent_folder_id(target_node_id)
        target_container = self._nearest_container_block_for_node(parent_folder_id)
        created_block_ids: list[str] = []

        for source_path in file_paths:
            file_meta = self._storage_service.import_file(self._project_root, source_path)
            block_type, profile, content = self._block_spec_from_import(source_path, file_meta)
            created = Block(
                id=f"blk_{block_type.value}_{uuid4().hex[:12]}",
                type=block_type,
                profile=profile,
                name=source_path.stem or source_path.name,
                description=f"Imported from Finder: {source_path.name}",
                shared=False,
                domain=(target_container.domain if target_container is not None else BlockDomain.LIB),
                tags=["imported", "finder_drop", block_type.value],
                content=content,
            )
            self._blocks.append(created)
            self._blocks_by_id[created.id] = created
            created_block_ids.append(created.id)

            node_id = self._new_tree_block_node_id(created.id)
            self._tree.nodes[node_id] = FreeTreeNode(
                id=node_id,
                kind="block_ref",
                name=created.name or created.id,
                block_id=created.id,
            )
            if parent_folder_id is None:
                self._tree.root_ids.append(node_id)
            else:
                parent = self._tree.nodes.get(parent_folder_id)
                if parent is None:
                    self._tree.root_ids.append(node_id)
                else:
                    parent.children.append(node_id)
                    self._append_to_nearest_container_contains(parent.id, created.id)

        if not created_block_ids:
            return

        persisted_tree = self.current_tree()
        self._controller.set_blocks(self._blocks, persisted_tree=persisted_tree)
        self._sync_state_from_controller()
        self._render_tree()
        self._select_node(self.find_node_id_for_block(created_block_ids[-1]) or "")
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))

    def _resolve_drop_parent_folder_id(self, target_node_id: str) -> str | None:
        if target_node_id:
            target = self._tree.nodes.get(target_node_id)
            if target is not None:
                if target.kind == "folder":
                    return target.id
                return self._controller.find_parent_folder_id(target.id)

        return self._internal_lib_folder_id()

    def _clone_block_for_drop(self, source: Block, *, target_domain: BlockDomain | None = None) -> Block:
        provenance = self._clone_provenance_from_source(source)
        return Block(
            id=f"blk_{source.type.value}_{uuid4().hex[:12]}",
            type=source.type,
            profile=source.profile,
            name=(source.name or source.id),
            description=source.description,
            prompt_ref=source.prompt_ref,
            prompt_generated=source.prompt_generated,
            comment=source.comment,
            shared=False,
            domain=(target_domain or source.domain),
            access_mode=BlockAccessMode.OWNED,
            provenance=provenance,
            functional_name=source.functional_name,
            tags=list(source.tags),
            content=dict(source.content),
            contains=[],
            inputs=[],
            tree=None,
            graph=None,
        )

    def _clone_provenance_from_source(self, source: Block) -> dict:
        source_provenance = dict(source.provenance) if isinstance(source.provenance, dict) else {}
        source_kind = str(source_provenance.get("kind", "") or "").strip().lower()

        if source.is_link() or source_kind in {
            BlockProvenanceKind.LIB_LINK.value,
            BlockProvenanceKind.LIB_CLONE.value,
        }:
            provenance = dict(source_provenance)
            provenance["kind"] = BlockProvenanceKind.LIB_CLONE.value
            provenance.setdefault("source_block_id", source.id)
            provenance.setdefault("source_block_name", source.name or source.id)
            provenance["cloned_from_block_id"] = source.id
            provenance["cloned_at"] = self._utc_now_iso()
            return provenance

        return {
            "kind": BlockProvenanceKind.LOCAL.value,
            "cloned_from_block_id": source.id,
            "cloned_from_block_name": source.name or source.id,
            "cloned_at": self._utc_now_iso(),
        }

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _block_spec_from_import(source_path: Path, file_meta: dict[str, str]) -> tuple[BlockType, str, dict]:
        mime_type = str(file_meta.get("mime_type", "") or "")
        relative_path = str(file_meta.get("storage_path", "") or "")
        content = {
            "storage_path": relative_path,
            "mime_type": mime_type,
            "original_name": str(file_meta.get("original_name", "") or source_path.name),
        }

        suffix = source_path.suffix.lower()
        if mime_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
            return BlockType.IMAGE, "asset", content
        if mime_type.startswith("video/") or suffix in {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}:
            return BlockType.VIDEO, "asset", content
        if mime_type.startswith("audio/") or suffix in {".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg"}:
            return BlockType.AUDIO, "asset", content
        if suffix in {".prompt"}:
            content["prompt_ref"] = relative_path
            return BlockType.PROMPT, "preset", content
        if mime_type.startswith("text/") or suffix in {".txt", ".md", ".markdown", ".json", ".yaml", ".yml"}:
            return BlockType.TEXT, "note", content
        guessed_mime = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        content["mime_type"] = guessed_mime
        return BlockType.TEXT, "note", content

    def _new_tree_block_node_id(self, block_id: str) -> str:
        base = f"node_block_{block_id}"
        candidate = base
        while candidate in self._tree.nodes:
            candidate = f"{base}_{uuid4().hex[:6]}"
        return candidate

    def _new_tree_container_node_id(self, block_id: str) -> str:
        base = f"node_container_{block_id}"
        candidate = base
        while candidate in self._tree.nodes:
            candidate = f"{base}_{uuid4().hex[:6]}"
        return candidate

    def _selected_block(self) -> Block | None:
        item = self._tree_view.currentItem()
        if item is None:
            return None
        node_id = str(item.data(0, ROLE_NODE_ID) or "").strip()
        if not node_id:
            return None
        node = self._tree.nodes.get(node_id)
        if node is None or not node.block_id:
            return None
        return self._blocks_by_id.get(node.block_id)

    def _selected_container_folder_id(self) -> str | None:
        item = self._tree_view.currentItem()
        if item is None:
            return None
        node_id = str(item.data(0, ROLE_NODE_ID) or "").strip()
        return self._nearest_container_folder_id_for_node(node_id)

    def _import_target_folder_id(self) -> str | None:
        selected = self._selected_container_folder_id()
        if selected:
            return selected
        internal_lib = self._internal_lib_folder_id()
        if internal_lib:
            return internal_lib
        return self._first_container_folder_id()

    def _template_target_folder_id(self) -> str | None:
        selected = self._selected_container_folder_id()
        if selected:
            selected_container = self._nearest_container_block_for_node(selected)
            if selected_container is not None and self._is_valid_template_parent(selected_container):
                return selected

        characters_root = self._characters_workspace_folder_id()
        if characters_root:
            return characters_root

        internal_lib = self._internal_lib_folder_id()
        if internal_lib:
            internal_container = self._nearest_container_block_for_node(internal_lib)
            if internal_container is not None and self._is_valid_template_parent(internal_container):
                return internal_lib

        first = self._first_container_folder_id()
        if first:
            first_container = self._nearest_container_block_for_node(first)
            if first_container is not None and self._is_valid_template_parent(first_container):
                return first
        return None

    def _characters_workspace_folder_id(self) -> str | None:
        candidate_ids = [*self._tree.root_ids, *self._tree.nodes.keys()]
        seen: set[str] = set()
        for node_id in candidate_ids:
            if node_id in seen:
                continue
            seen.add(node_id)
            node = self._tree.nodes.get(node_id)
            if node is None or node.kind != "folder" or not node.block_id:
                continue
            block = self._blocks_by_id.get(node.block_id)
            if block is None or block.type != BlockType.CONTAINER:
                continue
            if block.domain == BlockDomain.CHARACTERS:
                return node.id
            normalized_name = (block.name or "").strip().upper()
            if block.profile == "workspace_root" and "CHAR" in normalized_name:
                return node.id
        return None

    @staticmethod
    def _is_valid_template_parent(container: Block) -> bool:
        if container.type != BlockType.CONTAINER:
            return False
        return container.profile not in {"character", "character_form"}

    def _internal_lib_folder_id(self) -> str | None:
        for node in self._tree.nodes.values():
            if node.kind != "folder" or not node.block_id:
                continue
            block = self._blocks_by_id.get(node.block_id)
            if block is None or block.type != BlockType.CONTAINER:
                continue
            if block.id == "blk_internal_lib_root":
                return node.id
            role = str(block.content.get("workspace_role", "") or "").strip().lower()
            if role == "internal_lib":
                return node.id
            normalized_name = (block.name or "").strip().upper().replace(" ", "_")
            if block.profile == "workspace_root" and normalized_name in {"INTERNALLIB", "INTERNAL_LIB"}:
                return node.id
        return None

    def _first_container_folder_id(self) -> str | None:
        for node in self._tree.nodes.values():
            if node.kind != "folder" or not node.block_id:
                continue
            block = self._blocks_by_id.get(node.block_id)
            if block is not None and block.type == BlockType.CONTAINER:
                return node.id
        return None

    def _nearest_container_folder_id_for_node(self, node_id: str | None) -> str | None:
        current_id = str(node_id or "").strip()
        visited: set[str] = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            node = self._tree.nodes.get(current_id)
            if node is None:
                return None
            if node.kind == "folder" and node.block_id:
                block = self._blocks_by_id.get(node.block_id)
                if block is not None and block.type == BlockType.CONTAINER:
                    return node.id
            current_id = self._controller.find_parent_id(current_id) or ""
        return None

    @staticmethod
    def _confirm_block_deletion(block: Block, descendants_count: int) -> bool:
        target_name = block.name or block.id
        if descendants_count > 0:
            message = f"Delete '{target_name}' and its {descendants_count} descendant block(s)?"
        else:
            message = f"Delete '{target_name}'?"
        answer = QMessageBox.question(
            None,
            "Confirm Block Deletion",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _collect_block_descendants(self, root_block_id: str) -> set[str]:
        pending = [root_block_id]
        collected: set[str] = set()
        while pending:
            current_id = pending.pop()
            if current_id in collected:
                continue
            collected.add(current_id)
            current = self._blocks_by_id.get(current_id)
            if current is None or current.type != BlockType.CONTAINER:
                continue
            pending.extend(child_id for child_id in current.contains if child_id and child_id not in collected)
        return collected

    def _delete_blocks(self, block_ids_to_delete: set[str]) -> None:
        if not block_ids_to_delete:
            return

        survivors: list[Block] = []
        for block in self._blocks:
            if block.id in block_ids_to_delete:
                continue
            if block.contains:
                block.contains = [child_id for child_id in block.contains if child_id not in block_ids_to_delete]
            if block.inputs:
                block.inputs = [
                    entry
                    for entry in block.inputs
                    if entry.source_block_id and entry.source_block_id not in block_ids_to_delete
                ]
            survivors.append(block)

        self._blocks = survivors
        self._blocks_by_id = {block.id: block for block in survivors}
        self._prune_tree_for_deleted_blocks(block_ids_to_delete)

        persisted_tree = self.current_tree()
        self._controller.set_blocks(self._blocks, persisted_tree=persisted_tree)
        self._sync_state_from_controller()
        self._render_tree()
        self.tree_changed.emit(self.current_tree())
        self.blocks_changed.emit(list(self._blocks))

    def _insert_template_blocks(self, created_blocks: list[Block], *, target_folder_id: str) -> str | None:
        if not created_blocks:
            return None

        target_container = self._nearest_container_block_for_node(target_folder_id)
        if target_container is None or not self._is_valid_template_parent(target_container):
            return None

        root_block: Block | None = None
        created_by_id: dict[str, Block] = {}
        for block in created_blocks:
            self._blocks.append(block)
            self._blocks_by_id[block.id] = block
            created_by_id[block.id] = block
            if block.type == BlockType.CONTAINER and block.profile == "character" and root_block is None:
                root_block = block

        if root_block is None:
            return None

        if root_block.id not in target_container.contains:
            target_container.contains.append(root_block.id)

        return self._insert_container_subtree(root_block, created_by_id=created_by_id, parent_folder_id=target_folder_id)

    def _insert_container_subtree(
        self,
        container: Block,
        *,
        created_by_id: dict[str, Block],
        parent_folder_id: str | None,
    ) -> str:
        folder_node_id = self._new_tree_container_node_id(container.id)
        self._tree.nodes[folder_node_id] = FreeTreeNode(
            id=folder_node_id,
            kind="folder",
            name=container.name or container.id,
            block_id=container.id,
        )
        if parent_folder_id is None:
            self._tree.root_ids.append(folder_node_id)
        else:
            parent = self._tree.nodes.get(parent_folder_id)
            if parent is None:
                self._tree.root_ids.append(folder_node_id)
            else:
                parent.children.append(folder_node_id)

        for child_id in container.contains:
            child = created_by_id.get(child_id) or self._blocks_by_id.get(child_id)
            if child is None:
                continue
            if child.type == BlockType.CONTAINER:
                self._insert_container_subtree(child, created_by_id=created_by_id, parent_folder_id=folder_node_id)
                continue
            block_node_id = self._new_tree_block_node_id(child.id)
            self._tree.nodes[block_node_id] = FreeTreeNode(
                id=block_node_id,
                kind="block_ref",
                name=child.name or child.id,
                block_id=child.id,
            )
            self._tree.nodes[folder_node_id].children.append(block_node_id)
        return folder_node_id

    def _prune_tree_for_deleted_blocks(self, block_ids_to_delete: set[str]) -> None:
        nodes_to_remove = {
            node_id
            for node_id, node in self._tree.nodes.items()
            if node.block_id and node.block_id in block_ids_to_delete
        }
        container_folder_ids = [
            node_id
            for node_id in nodes_to_remove
            if (self._tree.nodes.get(node_id) is not None and self._tree.nodes[node_id].kind == "folder")
        ]
        for folder_id in container_folder_ids:
            nodes_to_remove.update(self._collect_tree_subtree_ids(folder_id))

        if not nodes_to_remove:
            return

        for node_id in nodes_to_remove:
            self._tree.nodes.pop(node_id, None)
        for node in self._tree.nodes.values():
            node.children = [child_id for child_id in node.children if child_id not in nodes_to_remove]
        self._tree.root_ids = [root_id for root_id in self._tree.root_ids if root_id not in nodes_to_remove]

    def _collect_tree_subtree_ids(self, root_node_id: str) -> set[str]:
        pending = [root_node_id]
        collected: set[str] = set()
        while pending:
            node_id = pending.pop()
            if node_id in collected:
                continue
            collected.add(node_id)
            node = self._tree.nodes.get(node_id)
            if node is None:
                continue
            pending.extend(child_id for child_id in node.children if child_id not in collected)
        return collected

    def _append_to_nearest_container_contains(self, start_node_id: str, block_id: str) -> None:
        container = self._nearest_container_block_for_node(start_node_id)
        if container is None:
            return
        if block_id not in container.contains:
            container.contains.append(block_id)

    def _nearest_container_block_for_node(self, node_id: str | None) -> Block | None:
        current_id = str(node_id or "").strip()
        visited: set[str] = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            node = self._tree.nodes.get(current_id)
            if node is None:
                break
            if node.block_id:
                block = self._blocks_by_id.get(node.block_id)
                if block is not None and block.type == BlockType.CONTAINER:
                    return block
            current_id = self._controller.find_parent_id(current_id) or ""
        return None

    def _select_node(self, node_id: str) -> None:
        matches = self._tree_view.findItems("", Qt.MatchContains | Qt.MatchRecursive, 0)
        for item in matches:
            if str(item.data(0, ROLE_NODE_ID) or "") == node_id:
                self._tree_view.setCurrentItem(item)
                return

    def _handle_selection_changed(self, *_: object) -> None:
        self._refresh_action_state()
        self._emit_selected_block()

    def _emit_selected_block(self) -> None:
        selected_block, container_id = self._selected_block_and_container_id()
        self.block_selected.emit(selected_block, container_id or "")

    def _selected_block_and_container_id(self) -> tuple[Block | None, str | None]:
        item = self._tree_view.currentItem()
        if item is None:
            return None, None

        node_id = str(item.data(0, ROLE_NODE_ID) or "").strip()
        if not node_id:
            return None, None
        node = self._tree.nodes.get(node_id)
        if node is None or not node.block_id:
            return None, None

        block = self._blocks_by_id.get(node.block_id)
        if block is None:
            return None, None

        container_id = self._container_context_for_selected_node(node_id=node_id, node=node, block=block)
        return block, container_id

    def _container_context_for_selected_node(
        self,
        *,
        node_id: str,
        node: FreeTreeNode,
        block: Block,
    ) -> str | None:
        if node.kind == "folder":
            parent_node_id = self._controller.find_parent_id(node_id)
            parent_container = self._nearest_container_block_for_node(parent_node_id)
            if parent_container is not None:
                return parent_container.id
            return self._infer_single_path_container(block)

        container = self._nearest_container_block_for_node(node_id)
        if container is not None and container.id != block.id:
            return container.id
        return self._infer_single_path_container(block)

    @staticmethod
    def _infer_single_path_container(block: Block) -> str | None:
        keys = [str(key).strip() for key in block.container_paths.keys() if str(key).strip()]
        if len(keys) == 1:
            return keys[0]
        return None

    def _refresh_action_state(self) -> None:
        if not self._actions_visible:
            self._add_folder_button.setEnabled(False)
            self._delete_folder_button.setEnabled(False)
            self._import_button.setEnabled(False)
            self._add_template_button.setEnabled(False)
            self._delete_block_button.setEnabled(False)
            return
        if not self._interactive:
            self._add_folder_button.setEnabled(False)
            self._delete_folder_button.setEnabled(False)
            self._import_button.setEnabled(False)
            self._add_template_button.setEnabled(False)
            self._delete_block_button.setEnabled(False)
            return
        item = self._tree_view.currentItem()
        can_add_template = bool(self._template_target_folder_id())
        if item is None:
            self._delete_folder_button.setEnabled(False)
            self._import_button.setEnabled(self._project_root is not None and self._project_root.exists() and bool(self._import_target_folder_id()))
            self._add_template_button.setEnabled(can_add_template)
            self._delete_block_button.setEnabled(False)
            return
        node_id = str(item.data(0, ROLE_NODE_ID) or "")
        self._delete_folder_button.setEnabled(self._controller.is_deletable_folder(node_id))
        self._import_button.setEnabled(self._project_root is not None and self._project_root.exists() and bool(self._import_target_folder_id()))
        self._add_template_button.setEnabled(can_add_template)
        self._delete_block_button.setEnabled(self._selected_block() is not None)

    def _icon_for_profile(self, profile: str) -> str:
        value = (profile or "").lower()
        if value in {"character", "character_form"}:
            return "story_world_user_star.svg"
        if value in {"voice", "music", "sfx"}:
            return "story_world_message_circle_user.svg"
        if value in {"prompt", "preset"}:
            return "edit_filter_2_spark.svg"
        if value in {"asset", "reference", "generated", "variation", "image", "video"}:
            return "project_folder_open.svg"
        if value in {"note", "description", "dialogue"}:
            return "project_notebook.svg"
        return "actions_adjustments_search.svg"

    def _on_surface_color(self) -> str:
        return active_theme_tokens_ref().get("on_surface", "#f9f9fd")

    def _primary_color(self) -> str:
        return active_theme_tokens_ref().get("primary", "#8dacff")

    def _folder_icon_color(self, node: FreeTreeNode) -> str:
        if node.block_id:
            return self._on_surface_color()
        return self._primary_color()

    def _on_surface_variant_color(self) -> str:
        tokens = active_theme_tokens_ref()
        return tokens.get("on_surface_variant", tokens.get("on_surface", "#f9f9fd"))

    def _icon_for(self, filename: str, color_hex: str) -> QIcon:
        key = (filename, color_hex)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        path = self._icons_dir / filename
        if not path.exists():
            return QIcon()

        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QIcon()

        icon = QIcon()
        tint = QColor(color_hex)
        for size in (16, 18, 20, 24):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            icon.addPixmap(pixmap)

        self._icon_cache[key] = icon
        return icon
