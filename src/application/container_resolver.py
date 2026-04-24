from __future__ import annotations

"""Container resolver producing a compact UI-oriented structure."""

from collections import defaultdict
from typing import Any

from domain import Block, PortType
from services import BlockService


class ContainerResolver:
    """Read-only projection builder for one container block.

    The resolver transforms raw relationships into a UI-ready payload:
    grouped content lists, input buckets, and lightweight graph edges.
    """

    def __init__(self, block_service: BlockService) -> None:
        self._block_service = block_service

    def resolve(self, container_id: str) -> dict[str, Any]:
        """Resolve one container into a compact structured projection.

        The returned dictionary intentionally duplicates some views (by type,
        by input port, graph nodes and edges) to keep UI rendering simple and
        avoid recomputation in widgets.
        """
        container = self._block_service.get_block(container_id)
        all_blocks = self._block_service.list_blocks()
        blocks_by_id = {block.id: block for block in all_blocks}

        # Resolve concrete block objects for ids listed in container.contains.
        contained_blocks = [blocks_by_id[child_id] for child_id in container.contains if child_id in blocks_by_id]

        contained_by_type: dict[str, list[Block]] = defaultdict(list)
        for block in contained_blocks:
            contained_by_type[block.type.value].append(block)

        exposed_contained_blocks = [block for block in contained_blocks if block.exposed]
        functional_blocks = [
            block
            for block in contained_blocks
            if block.functional_name.strip()
        ]

        # Keep explicit IN/TOP/BOTTOM buckets for direct UI rendering.
        inputs_by_port: dict[str, list[dict[str, Any]]] = {port.value: [] for port in (PortType.IN, PortType.TOP, PortType.BOTTOM)}
        for input_conn in sorted(container.inputs, key=lambda item: item.order):
            bucket = inputs_by_port.setdefault(input_conn.port.value, [])
            bucket.append(
                {
                    "source_block_id": input_conn.source_block_id,
                    "source_block": blocks_by_id.get(input_conn.source_block_id),
                    "name": input_conn.name,
                    "enabled": input_conn.enabled,
                    "order": input_conn.order,
                    "metadata": dict(input_conn.metadata),
                }
            )

        node_index: dict[str, dict[str, Any]] = {}

        def add_node(block: Block) -> None:
            node_index.setdefault(
                block.id,
                {
                    "id": block.id,
                    "type": block.type.value,
                    "domain": block.domain.value,
                    "profile": block.profile,
                    "name": block.name,
                    "exposed": block.exposed,
                },
            )

        add_node(container)
        for block in contained_blocks:
            add_node(block)
        for input_conn in container.inputs:
            source_block = blocks_by_id.get(input_conn.source_block_id)
            if source_block is not None:
                add_node(source_block)

        edges: list[dict[str, Any]] = []
        # `contains` edges represent hierarchy; `input` edges represent references.
        for block in contained_blocks:
            edges.append({"from": container.id, "to": block.id, "kind": "contains"})
        for input_conn in container.inputs:
            edges.append(
                {
                    "from": input_conn.source_block_id,
                    "to": container.id,
                    "kind": "input",
                    "port": input_conn.port.value,
                    "name": input_conn.name,
                }
            )

        return {
            "container": container,
            "contained_blocks": contained_blocks,
            "contained_by_type": dict(contained_by_type),
            "exposed_contained_blocks": exposed_contained_blocks,
            "inputs_by_port": inputs_by_port,
            "functional_blocks": functional_blocks,
            "nodes": list(node_index.values()),
            "edges": edges,
        }
