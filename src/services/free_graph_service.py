from __future__ import annotations

from uuid import uuid4

from domain import Block, BlockType, FreeGraph, FreeGraphEdge, FreeGraphNode, NotFoundError, ValidationError


class FreeGraphService:
    """Manipulate the graph embedded in a container block."""

    def ensure_graph(self, container: Block) -> FreeGraph:
        self._assert_container(container)
        if container.graph is None:
            container.graph = FreeGraph()
        return container.graph

    def add_block_node(self, container: Block, block_id: str, x: float = 0, y: float = 0) -> FreeGraphNode:
        graph = self.ensure_graph(container)
        if block_id not in container.contains:
            raise ValidationError(f"Block must be inside container before graph placement: {block_id}")
        node = FreeGraphNode(id=f"gnode_{uuid4().hex[:12]}", block_id=block_id, x=x, y=y)
        graph.nodes[node.id] = node
        return node

    def move_node(self, container: Block, node_id: str, x: float, y: float) -> FreeGraphNode:
        graph = self.ensure_graph(container)
        node = graph.nodes.get(node_id)
        if node is None:
            raise NotFoundError(f"Graph node not found: {node_id}")
        node.x = x
        node.y = y
        return node

    def remove_node(self, container: Block, node_id: str) -> None:
        graph = self.ensure_graph(container)
        if node_id not in graph.nodes:
            raise NotFoundError(f"Graph node not found: {node_id}")

        del graph.nodes[node_id]
        graph.edges = {
            edge_id: edge
            for edge_id, edge in graph.edges.items()
            if edge.source_node_id != node_id and edge.target_node_id != node_id
        }

    def add_edge(
        self,
        container: Block,
        source_node_id: str,
        target_node_id: str,
        label: str = "",
    ) -> FreeGraphEdge:
        graph = self.ensure_graph(container)
        if source_node_id not in graph.nodes:
            raise NotFoundError(f"Graph node not found: {source_node_id}")
        if target_node_id not in graph.nodes:
            raise NotFoundError(f"Graph node not found: {target_node_id}")

        edge = FreeGraphEdge(
            id=f"gedge_{uuid4().hex[:12]}",
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            label=label,
        )
        graph.edges[edge.id] = edge
        return edge

    def remove_edge(self, container: Block, edge_id: str) -> None:
        graph = self.ensure_graph(container)
        if edge_id not in graph.edges:
            raise NotFoundError(f"Graph edge not found: {edge_id}")
        del graph.edges[edge_id]

    @staticmethod
    def _assert_container(container: Block) -> None:
        if container.type != BlockType.CONTAINER:
            raise ValidationError(f"Block is not a container: {container.id}")

