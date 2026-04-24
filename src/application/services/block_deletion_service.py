from __future__ import annotations

from dataclasses import dataclass

from domain import Block, BlockType, FreeGraph, FreeTree


@dataclass(frozen=True, slots=True)
class BlockDeletionPreview:
    root_block_id: str
    root_block_name: str
    descendant_ids: tuple[str, ...]
    descendant_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BlockDeletionResult:
    deleted_ids: tuple[str, ...]
    deleted_names: tuple[str, ...]


class BlockDeletionService:
    """Recursively deletes one block and cleans all surviving references."""

    def preview(self, blocks: list[Block], *, block_id: str) -> BlockDeletionPreview:
        target = self._find_block(blocks, block_id)
        if target is None:
            raise ValueError(f"Block not found: {block_id}")
        self._validate_deletable(target)

        descendants = self._collect_descendants(blocks, target.id)
        descendant_ids = tuple(item.id for item in descendants)
        descendant_names = tuple(item.name or item.id for item in descendants)
        return BlockDeletionPreview(
            root_block_id=target.id,
            root_block_name=target.name or target.id,
            descendant_ids=descendant_ids,
            descendant_names=descendant_names,
        )

    def delete(self, blocks: list[Block], *, block_id: str) -> BlockDeletionResult:
        preview = self.preview(blocks, block_id=block_id)
        deleted_ids = {preview.root_block_id, *preview.descendant_ids}

        survivors: list[Block] = []
        for block in blocks:
            if block.id in deleted_ids:
                continue
            self._prune_block_references(block, deleted_ids)
            survivors.append(block)

        blocks[:] = survivors
        deleted_names = (preview.root_block_name, *preview.descendant_names)
        return BlockDeletionResult(
            deleted_ids=tuple([preview.root_block_id, *preview.descendant_ids]),
            deleted_names=deleted_names,
        )

    @staticmethod
    def _find_block(blocks: list[Block], block_id: str) -> Block | None:
        target = str(block_id or "").strip()
        if not target:
            return None
        return next((block for block in blocks if block.id == target), None)

    @staticmethod
    def _validate_deletable(block: Block) -> None:
        if block.type == BlockType.CONTAINER and block.profile == "workspace_root":
            raise ValueError("Workspace roots cannot be deleted.")

    def _collect_descendants(self, blocks: list[Block], root_block_id: str) -> list[Block]:
        by_id = {block.id: block for block in blocks}
        result: list[Block] = []
        root = by_id.get(root_block_id)
        if root is None or root.type != BlockType.CONTAINER:
            return result
        pending = list(reversed(root.contains))
        seen: set[str] = set()
        while pending:
            current_id = pending.pop()
            if current_id in seen:
                continue
            seen.add(current_id)
            current = by_id.get(current_id)
            if current is None:
                continue
            result.append(current)
            if current.type == BlockType.CONTAINER and current.contains:
                pending.extend(reversed(current.contains))
        return result

    def _prune_block_references(self, block: Block, deleted_ids: set[str]) -> None:
        if block.contains:
            block.contains = [child_id for child_id in block.contains if child_id not in deleted_ids]
        if block.inputs:
            block.inputs = [item for item in block.inputs if item.source_block_id not in deleted_ids]
        if block.container_paths:
            block.container_paths = {
                container_id: relative_path
                for container_id, relative_path in block.container_paths.items()
                if container_id not in deleted_ids
            }
        if block.type == BlockType.CONTAINER:
            if block.tree is not None:
                self._prune_tree(block.tree, deleted_ids)
            if block.graph is not None:
                self._prune_graph(block.graph, deleted_ids)

    @staticmethod
    def _prune_tree(tree: FreeTree, deleted_ids: set[str]) -> None:
        nodes_to_remove: set[str] = set()

        def collect_subtree(node_id: str) -> None:
            if node_id in nodes_to_remove:
                return
            nodes_to_remove.add(node_id)
            node = tree.nodes.get(node_id)
            if node is None:
                return
            for child_id in node.children:
                collect_subtree(child_id)

        for node_id, node in list(tree.nodes.items()):
            if node.block_id and node.block_id in deleted_ids:
                collect_subtree(node_id)

        if nodes_to_remove:
            tree.root_ids = [node_id for node_id in tree.root_ids if node_id not in nodes_to_remove]

        pruned_nodes = {
            node_id: node
            for node_id, node in tree.nodes.items()
            if node_id not in nodes_to_remove and (not node.block_id or node.block_id not in deleted_ids)
        }
        for node in pruned_nodes.values():
            node.children = [child_id for child_id in node.children if child_id in pruned_nodes]
        tree.nodes = pruned_nodes

    @staticmethod
    def _prune_graph(graph: FreeGraph, deleted_ids: set[str]) -> None:
        removed_node_ids = {
            node_id
            for node_id, node in graph.nodes.items()
            if node.block_id in deleted_ids
        }
        if removed_node_ids:
            graph.nodes = {
                node_id: node
                for node_id, node in graph.nodes.items()
                if node_id not in removed_node_ids
            }
            graph.edges = {
                edge_id: edge
                for edge_id, edge in graph.edges.items()
                if edge.source_node_id not in removed_node_ids and edge.target_node_id not in removed_node_ids
            }
