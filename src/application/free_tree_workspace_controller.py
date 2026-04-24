from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from domain import Block, BlockType, FreeTree, FreeTreeNode


@dataclass(slots=True)
class FreeTreeItemSnapshot:
    """Serializable tree row snapshot used by the UI layer after drag-and-drop."""

    node_id: str
    node_kind: str
    name: str
    block_id: str | None = None
    children: list[FreeTreeItemSnapshot] = field(default_factory=list)


class FreeTreeWorkspaceController:
    """Controller rebuilding and mutating the virtual FreeTree view.

    The controller is the bridge between persisted block ``container_paths`` and
    the interactive tree widget representation used by the UI. Snapshot trees
    coming from the widget are replayed onto ``container_paths``, which remain
    the single source of truth.
    """

    def __init__(self) -> None:
        self._blocks: list[Block] = []
        self._blocks_by_id: dict[str, Block] = {}
        self._tree = FreeTree()
        self._locked_node_ids: set[str] = set()
        self._emitted_node_ids: set[str] = set()

    @property
    def blocks(self) -> list[Block]:
        return list(self._blocks)

    @property
    def blocks_by_id(self) -> dict[str, Block]:
        return dict(self._blocks_by_id)

    @property
    def tree(self) -> FreeTree:
        return self._tree

    @property
    def locked_node_ids(self) -> set[str]:
        return set(self._locked_node_ids)

    def set_blocks(self, blocks: list[Block], *, persisted_tree: FreeTree | None = None) -> None:
        """Load blocks and rebuild the virtual tree from current container paths.

        Args:
            blocks: Full block collection of the current workspace.
            persisted_tree: Optional in-memory tree snapshot to replay after a
                widget-side reordering or refresh.
        """

        self._blocks = list(blocks)
        self._blocks_by_id = {block.id: block for block in self._blocks}
        self._tree, self._locked_node_ids = self._build_tree_from_paths()
        if persisted_tree is not None:
            self.apply_persisted_tree(persisted_tree)

    def apply_persisted_tree(self, persisted_tree: FreeTree | None) -> None:
        """Replay a tree snapshot into block ``container_paths``.

        The replay is conservative: explicit current paths already stored on a
        block are preserved instead of being erased by a flatter snapshot.
        """
        if persisted_tree is None:
            return
        parent_map = self._parent_map_for_tree(persisted_tree)
        changed = False

        for node_id, node in persisted_tree.nodes.items():
            if not node.block_id:
                continue
            block = self._blocks_by_id.get(node.block_id)
            if block is None:
                continue
            parent_container_id, rel_path = self._extract_path_from_snapshot_tree(
                persisted_tree,
                parent_map=parent_map,
                node_id=node_id,
            )
            if not parent_container_id:
                continue
            normalized = self._normalize_rel_path(rel_path)
            existing = self._normalize_rel_path(block.container_paths.get(parent_container_id, ""))
            if existing == normalized:
                continue
            # Do not overwrite an explicit path with a less specific snapshot.
            if existing and not normalized:
                continue
            block.container_paths[parent_container_id] = normalized
            changed = True

        if changed:
            self._tree, self._locked_node_ids = self._build_tree_from_paths()

    def add_folder(self, name: str, parent_node_id: str | None = None) -> str | None:
        folder_name = name.strip()
        if not folder_name:
            return None

        if parent_node_id and parent_node_id not in self._tree.nodes:
            parent_node_id = None
        if parent_node_id and self._tree.nodes[parent_node_id].kind != "folder":
            parent_node_id = self.find_parent_folder_id(parent_node_id)
        folder_id = self._new_unique_node_id("node_folder_user", folder_name)
        self._tree.nodes[folder_id] = FreeTreeNode(id=folder_id, kind="folder", name=folder_name)
        if parent_node_id is None:
            self._tree.root_ids.append(folder_id)
        else:
            parent_node = self._tree.nodes.get(parent_node_id)
            if parent_node is None:
                self._tree.root_ids.append(folder_id)
            else:
                if parent_node.block_id and not self._is_container_block_id(parent_node.block_id):
                    return None
                self._tree.nodes[parent_node_id].children.append(folder_id)
        self._sync_block_paths_from_tree()
        return folder_id

    def move_node(self, node_id: str, new_parent_id: str | None) -> None:
        if node_id not in self._tree.nodes:
            return
        if node_id in self._locked_node_ids:
            return
        if new_parent_id and (new_parent_id not in self._tree.nodes or self._tree.nodes[new_parent_id].kind != "folder"):
            new_parent_id = None
        if new_parent_id in self._locked_node_ids:
            return
        if new_parent_id is None:
            return

        target_context = self._path_context_for_node(new_parent_id)
        node_context = self._path_context_for_node(node_id)
        if node_context and target_context and node_context != target_context:
            return

        self._detach_from_current_parent(node_id)
        self._tree.nodes[new_parent_id].children.append(node_id)
        self._sync_block_paths_from_tree()

    def remove_folder(self, folder_node_id: str) -> None:
        folder = self._tree.nodes.get(folder_node_id)
        if folder is None or folder.kind != "folder":
            return
        if folder_node_id in self._locked_node_ids:
            return
        if folder.block_id:
            return

        destination_parent_id = self.find_parent_id(folder_node_id)
        children = list(folder.children)

        self._detach_from_current_parent(folder_node_id)
        self._tree.nodes.pop(folder_node_id, None)

        for node in self._tree.nodes.values():
            node.children = [child_id for child_id in node.children if child_id != folder_node_id]
        self._tree.root_ids = [root_id for root_id in self._tree.root_ids if root_id != folder_node_id]

        for child_id in children:
            if child_id not in self._tree.nodes:
                continue
            self._detach_from_current_parent(child_id)
            if destination_parent_id is None:
                self._tree.root_ids.append(child_id)
            else:
                self._tree.nodes[destination_parent_id].children.append(child_id)

        self._sync_block_paths_from_tree()

    def find_node_id_for_block(self, block_id: str) -> str | None:
        preferred: str | None = None
        for node_id, node in self._tree.nodes.items():
            if node.block_id != block_id:
                continue
            if node.kind == "block_ref":
                return node_id
            if preferred is None:
                preferred = node_id
        return preferred

    def update_block_relative_path(
        self,
        *,
        block_id: str,
        parent_container_id: str,
        relative_path: str,
    ) -> bool:
        block = self._blocks_by_id.get(block_id)
        parent = self._blocks_by_id.get(parent_container_id)
        if block is None or parent is None:
            return False
        if parent.type != BlockType.CONTAINER:
            return False
        if block.id not in parent.contains:
            return False

        normalized = self._normalize_rel_path(relative_path)
        current = self._normalize_rel_path(block.container_paths.get(parent_container_id, ""))
        if current == normalized:
            return False

        if normalized:
            block.container_paths[parent_container_id] = normalized
        else:
            block.container_paths.pop(parent_container_id, None)
        self._tree, self._locked_node_ids = self._build_tree_from_paths()
        return True

    def find_parent_id(self, node_id: str) -> str | None:
        for candidate in self._tree.nodes.values():
            if node_id in candidate.children:
                return candidate.id
        return None

    def find_parent_folder_id(self, node_id: str) -> str | None:
        parent_id = self.find_parent_id(node_id)
        if parent_id is None:
            return None
        parent = self._tree.nodes.get(parent_id)
        if parent is None or parent.kind != "folder":
            return None
        return parent.id

    def is_deletable_folder(self, node_id: str) -> bool:
        node = self._tree.nodes.get(node_id)
        return node is not None and node.kind == "folder" and node.block_id is None and node_id not in self._locked_node_ids

    def rebuild_from_snapshot(self, roots: list[FreeTreeItemSnapshot]) -> None:
        previous_nodes = self._tree.nodes
        rebuilt = FreeTree()

        def walk(snapshot: FreeTreeItemSnapshot) -> str:
            old = previous_nodes.get(snapshot.node_id)
            node_kind = old.kind if old is not None else snapshot.node_kind
            block_id = old.block_id if old is not None else snapshot.block_id
            node = FreeTreeNode(
                id=snapshot.node_id,
                kind=node_kind,
                name=snapshot.name,
                block_id=block_id,
                children=[],
            )
            if node.kind == "folder" and node.block_id and not self._is_container_block_id(node.block_id):
                node.block_id = None
            rebuilt.nodes[node.id] = node
            for child_snapshot in snapshot.children:
                child_id = walk(child_snapshot)
                if child_id not in rebuilt.nodes:
                    continue
                if node.kind == "folder":
                    node.children.append(child_id)
                else:
                    rebuilt.root_ids.append(child_id)
            return node.id

        for top_snapshot in roots:
            top_id = walk(top_snapshot)
            if top_id not in rebuilt.root_ids:
                rebuilt.root_ids.append(top_id)

        for node in rebuilt.nodes.values():
            if node.kind != "folder":
                node.children = []

        self._locked_node_ids = {node_id for node_id in self._locked_node_ids if node_id in rebuilt.nodes}
        self._tree = rebuilt
        self._deduplicate_root_ids()
        self._sync_block_paths_from_tree()

    def _build_tree_from_paths(self) -> tuple[FreeTree, set[str]]:
        tree = FreeTree()
        locked_node_ids: set[str] = set()
        self._emitted_node_ids = set()

        blocks_by_id = self._blocks_by_id
        containers = [block for block in self._blocks if block.type == BlockType.CONTAINER]

        contained_ids = {
            child_id
            for container in containers
            for child_id in container.contains
            if child_id in blocks_by_id
        }
        top_level_containers = [container for container in containers if container.id not in contained_ids]
        if not top_level_containers:
            top_level_containers = containers

        def add_container_node(
            container: Block,
            *,
            attach_parent_node_id: str | None,
            parent_container_id: str | None,
            lineage: set[str],
        ) -> str:
            target_parent = attach_parent_node_id
            if parent_container_id:
                rel_path = self._normalize_rel_path(container.container_paths.get(parent_container_id, ""))
                target_parent = ensure_virtual_folders(
                    base_parent_node_id=attach_parent_node_id,
                    rel_path=rel_path,
                )

            node_id = self._new_unique_node_id("node_container", container.id)
            tree.nodes[node_id] = FreeTreeNode(
                id=node_id,
                kind="folder",
                name=container.name or container.id,
                block_id=container.id,
            )
            locked_node_ids.add(node_id)
            if target_parent is None:
                tree.root_ids.append(node_id)
            else:
                tree.nodes[target_parent].children.append(node_id)

            child_ids: list[str] = []
            seen_child_ids: set[str] = set()
            for child_id in container.contains:
                if child_id not in blocks_by_id or child_id in seen_child_ids:
                    continue
                child_ids.append(child_id)
                seen_child_ids.add(child_id)

            for child_id in child_ids:
                child = blocks_by_id[child_id]
                if child.type == BlockType.CONTAINER and child.id not in lineage:
                    add_container_node(
                        child,
                        attach_parent_node_id=node_id,
                        parent_container_id=container.id,
                        lineage=(lineage | {container.id}),
                    )
                    continue
                add_leaf_block_ref(child, parent_node_id=node_id, parent_container_id=container.id)
            return node_id

        def add_leaf_block_ref(child: Block, *, parent_node_id: str, parent_container_id: str) -> None:
            rel_path = self._normalize_rel_path(child.container_paths.get(parent_container_id, ""))
            target_parent = ensure_virtual_folders(base_parent_node_id=parent_node_id, rel_path=rel_path)
            node_id = self._new_unique_node_id("node_block", child.id)
            tree.nodes[node_id] = FreeTreeNode(
                id=node_id,
                kind="block_ref",
                name=child.name or child.id,
                block_id=child.id,
            )
            tree.nodes[target_parent].children.append(node_id)

        def ensure_virtual_folders(*, base_parent_node_id: str | None, rel_path: str) -> str:
            current_parent = base_parent_node_id
            segments = [segment for segment in rel_path.split("/") if segment]
            for segment in segments:
                existing = None
                if current_parent is not None:
                    parent_node = tree.nodes.get(current_parent)
                    if parent_node is not None:
                        for child_id in parent_node.children:
                            child_node = tree.nodes.get(child_id)
                            if child_node is None:
                                continue
                            if child_node.kind == "folder" and child_node.block_id is None and child_node.name == segment:
                                existing = child_id
                                break
                if existing is None:
                    existing = self._new_unique_node_id("node_folder", segment)
                    tree.nodes[existing] = FreeTreeNode(id=existing, kind="folder", name=segment, block_id=None)
                    if current_parent is None:
                        tree.root_ids.append(existing)
                    else:
                        tree.nodes[current_parent].children.append(existing)
                current_parent = existing
            if current_parent is None:
                raise RuntimeError("base_parent_node_id is required for path-based virtual folders")
            return current_parent

        for container in top_level_containers:
            add_container_node(
                container,
                attach_parent_node_id=None,
                parent_container_id=None,
                lineage=set(),
            )

        # Blocks that are not attached by container links remain visible as root refs.
        visible_block_ids = {
            node.block_id
            for node in tree.nodes.values()
            if node.kind in {"folder", "block_ref"} and node.block_id
        }
        for block in self._blocks:
            if block.id in visible_block_ids:
                continue
            if block.type == BlockType.CONTAINER:
                node_id = self._new_unique_node_id("node_container", block.id)
                tree.nodes[node_id] = FreeTreeNode(
                    id=node_id,
                    kind="folder",
                    name=block.name or block.id,
                    block_id=block.id,
                )
                tree.root_ids.append(node_id)
                locked_node_ids.add(node_id)
                continue
            node_id = self._new_unique_node_id("node_block", block.id)
            tree.nodes[node_id] = FreeTreeNode(
                id=node_id,
                kind="block_ref",
                name=block.name or block.id,
                block_id=block.id,
            )
            tree.root_ids.append(node_id)

        self._deduplicate_tree(tree)
        return tree, locked_node_ids

    def _deduplicate_tree(self, tree: FreeTree) -> None:
        seen_roots: set[str] = set()
        tree.root_ids = [node_id for node_id in tree.root_ids if not (node_id in seen_roots or seen_roots.add(node_id))]
        for node in tree.nodes.values():
            seen: set[str] = set()
            node.children = [child_id for child_id in node.children if child_id in tree.nodes and not (child_id in seen or seen.add(child_id))]

    def _deduplicate_root_ids(self) -> None:
        seen: set[str] = set()
        self._tree.root_ids = [node_id for node_id in self._tree.root_ids if node_id in self._tree.nodes and not (node_id in seen or seen.add(node_id))]

    def _sync_block_paths_from_tree(self) -> None:
        parent_map = self._parent_map_for_tree(self._tree)
        containers_by_id = {block.id: block for block in self._blocks if block.type == BlockType.CONTAINER}

        parent_relations: dict[str, set[str]] = {}
        for container in containers_by_id.values():
            for child_id in container.contains:
                child = self._blocks_by_id.get(child_id)
                if child is None:
                    continue
                parent_relations.setdefault(child.id, set()).add(container.id)

        for block in self._blocks:
            if block.container_paths:
                block.container_paths = {
                    parent_id: self._normalize_rel_path(path)
                    for parent_id, path in block.container_paths.items()
                    if parent_id in parent_relations.get(block.id, set())
                }

            for parent_container_id in parent_relations.get(block.id, set()):
                path = self._path_for_block_in_container(block_id=block.id, parent_container_id=parent_container_id, parent_map=parent_map)
                block.container_paths[parent_container_id] = self._normalize_rel_path(path)

    def _path_for_block_in_container(
        self,
        *,
        block_id: str,
        parent_container_id: str,
        parent_map: dict[str, str | None],
    ) -> str:
        candidate_ids = [
            node_id
            for node_id, node in self._tree.nodes.items()
            if node.block_id == block_id and node.kind in {"folder", "block_ref"}
        ]
        for node_id in candidate_ids:
            container_id, rel_path = self._extract_path_from_tree(
                self._tree,
                parent_map=parent_map,
                node_id=node_id,
            )
            if container_id == parent_container_id:
                return rel_path
        return ""

    def _extract_path_from_tree(
        self,
        tree: FreeTree,
        *,
        parent_map: dict[str, str | None],
        node_id: str,
    ) -> tuple[str, str]:
        node = tree.nodes.get(node_id)
        if node is None:
            return "", ""

        cursor = parent_map.get(node_id)
        segments: list[str] = []
        while cursor:
            ancestor = tree.nodes.get(cursor)
            if ancestor is None:
                break
            if ancestor.kind == "folder" and ancestor.block_id and self._is_container_block_id(ancestor.block_id):
                return ancestor.block_id, "/".join(reversed(segments))
            if ancestor.kind == "folder" and ancestor.block_id is None:
                segment = ancestor.name.strip().replace("\\", "/").strip("/")
                if segment:
                    segments.append(segment)
            cursor = parent_map.get(cursor)
        return "", ""

    def _extract_path_from_snapshot_tree(
        self,
        tree: FreeTree,
        *,
        parent_map: dict[str, str | None],
        node_id: str,
    ) -> tuple[str, str]:
        return self._extract_path_from_tree(tree, parent_map=parent_map, node_id=node_id)

    @staticmethod
    def _parent_map_for_tree(tree: FreeTree) -> dict[str, str | None]:
        parent_map: dict[str, str | None] = {root_id: None for root_id in tree.root_ids}
        for node in tree.nodes.values():
            for child_id in node.children:
                if child_id in tree.nodes:
                    parent_map[child_id] = node.id
        for node_id in tree.nodes:
            parent_map.setdefault(node_id, None)
        return parent_map

    def _path_context_for_node(self, node_id: str) -> str:
        parent_map = self._parent_map_for_tree(self._tree)
        container_id, _ = self._extract_path_from_tree(self._tree, parent_map=parent_map, node_id=node_id)
        if container_id:
            return container_id
        node = self._tree.nodes.get(node_id)
        if node is not None and node.block_id and self._is_container_block_id(node.block_id):
            return node.block_id
        return ""

    def _detach_from_current_parent(self, node_id: str) -> None:
        parent_id = self.find_parent_id(node_id)
        if parent_id is None:
            self._tree.root_ids = [root_id for root_id in self._tree.root_ids if root_id != node_id]
            return
        parent = self._tree.nodes.get(parent_id)
        if parent is None:
            return
        parent.children = [child_id for child_id in parent.children if child_id != node_id]

    def _is_container_block_id(self, block_id: str) -> bool:
        block = self._blocks_by_id.get(block_id)
        return block is not None and block.type == BlockType.CONTAINER

    def _new_unique_node_id(self, prefix: str, suffix: str) -> str:
        stem = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in suffix.strip().lower())
        stem = stem.strip("_") or uuid4().hex[:8]
        candidate = f"{prefix}_{stem}"
        if candidate in self._emitted_node_ids:
            candidate = f"{candidate}_{uuid4().hex[:6]}"
        self._emitted_node_ids.add(candidate)
        return candidate

    @staticmethod
    def _normalize_rel_path(value: str | None) -> str:
        text = str(value or "").replace("\\", "/")
        raw_parts = [part.strip() for part in text.split("/") if part.strip()]
        cleaned_parts: list[str] = []
        for part in raw_parts:
            if part in {".", ".."}:
                continue
            cleaned_parts.append(part)
        return "/".join(cleaned_parts)
