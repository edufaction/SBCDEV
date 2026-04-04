from __future__ import annotations

"""Embedded FreeTree operations on container blocks."""

from uuid import uuid4

from domain import Block, BlockType, FreeTree, FreeTreeNode, NotFoundError, ValidationError


class FreeTreeService:
    """Manipulate the tree embedded in a container block."""

    def ensure_tree(self, container: Block) -> FreeTree:
        """Validate container and lazily initialize its embedded tree."""
        self._assert_container(container)
        if container.tree is None:
            container.tree = FreeTree()
        return container.tree

    def add_block_ref(self, container: Block, block_id: str, name: str | None = None) -> FreeTreeNode:
        tree = self.ensure_tree(container)
        node = FreeTreeNode(
            id=f"node_{uuid4().hex[:12]}",
            kind="block_ref",
            name=(name or block_id),
            block_id=block_id,
        )
        tree.nodes[node.id] = node
        tree.root_ids.append(node.id)
        return node

    def create_folder(self, container: Block, parent_node_id: str | None, name: str) -> FreeTreeNode:
        if not name.strip():
            raise ValidationError("folder name is required")

        tree = self.ensure_tree(container)
        node = FreeTreeNode(
            id=f"node_{uuid4().hex[:12]}",
            kind="folder",
            name=name.strip(),
        )
        tree.nodes[node.id] = node

        if parent_node_id is None:
            tree.root_ids.append(node.id)
            return node

        parent = tree.nodes.get(parent_node_id)
        if parent is None:
            raise NotFoundError(f"Parent node not found: {parent_node_id}")
        if parent.kind != "folder":
            raise ValidationError(f"Parent node is not a folder: {parent_node_id}")
        parent.children.append(node.id)
        return node

    def move_node(self, container: Block, node_id: str, new_parent_id: str | None) -> None:
        tree = self.ensure_tree(container)
        node = tree.nodes.get(node_id)
        if node is None:
            raise NotFoundError(f"Node not found: {node_id}")

        if new_parent_id is not None:
            new_parent = tree.nodes.get(new_parent_id)
            if new_parent is None:
                raise NotFoundError(f"Parent node not found: {new_parent_id}")
            if new_parent.kind != "folder":
                raise ValidationError(f"Parent node is not a folder: {new_parent_id}")
            if new_parent_id == node_id:
                raise ValidationError("cannot move a node under itself")
        else:
            new_parent = None

        current_parent_id = self._find_parent_id(tree, node_id)
        if current_parent_id is None:
            tree.root_ids = [item for item in tree.root_ids if item != node_id]
        else:
            current_parent = tree.nodes[current_parent_id]
            current_parent.children = [item for item in current_parent.children if item != node_id]

        if new_parent is None:
            tree.root_ids.append(node_id)
        else:
            new_parent.children.append(node_id)

    def remove_node(self, container: Block, node_id: str) -> None:
        tree = self.ensure_tree(container)
        if node_id not in tree.nodes:
            raise NotFoundError(f"Node not found: {node_id}")

        to_remove = self._collect_descendants(tree, node_id)
        parent_id = self._find_parent_id(tree, node_id)

        if parent_id is None:
            tree.root_ids = [item for item in tree.root_ids if item != node_id]
        else:
            parent = tree.nodes[parent_id]
            parent.children = [item for item in parent.children if item != node_id]

        for current_id in to_remove:
            tree.nodes.pop(current_id, None)

    def remove_block_refs(self, container: Block, block_id: str) -> None:
        tree = self.ensure_tree(container)
        node_ids = [
            node.id
            for node in tree.nodes.values()
            if node.kind == "block_ref" and node.block_id == block_id
        ]
        for node_id in node_ids:
            self.remove_node(container, node_id)

    @staticmethod
    def _assert_container(container: Block) -> None:
        if container.type != BlockType.CONTAINER:
            raise ValidationError(f"Block is not a container: {container.id}")

    def _collect_descendants(self, tree: FreeTree, node_id: str) -> set[str]:
        result: set[str] = set()
        stack = [node_id]
        while stack:
            current_id = stack.pop()
            if current_id in result:
                continue
            result.add(current_id)
            current = tree.nodes.get(current_id)
            if current is not None:
                stack.extend(current.children)
        return result

    def _find_parent_id(self, tree: FreeTree, node_id: str) -> str | None:
        for candidate in tree.nodes.values():
            if node_id in candidate.children:
                return candidate.id
        return None
