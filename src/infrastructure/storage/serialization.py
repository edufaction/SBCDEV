from __future__ import annotations

from domain import (
    Block,
    BlockAccessMode,
    BlockDomain,
    BlockType,
    FreeGraph,
    FreeGraphEdge,
    FreeGraphNode,
    FreeTree,
    FreeTreeNode,
    InputConnection,
    PortType,
    normalize_block_provenance,
)


def block_to_dict(block: Block) -> dict:
    access_mode = _as_access_mode(block.access_mode)
    provenance = normalize_block_provenance(block.provenance, access_mode=access_mode)
    return {
        "id": block.id,
        "type": block.type.value,
        "profile": block.profile,
        "name": block.name,
        "description": block.description,
        "prompt_ref": block.prompt_ref,
        "prompt_generated": block.prompt_generated,
        "comment": block.comment,
        "exposed": block.exposed,
        "domain": block.domain.value,
        "access_mode": access_mode.value,
        "provenance": provenance,
        "container_paths": {
            str(container_id): str(path_value or "")
            for container_id, path_value in block.container_paths.items()
            if str(container_id).strip()
        },
        "functional_name": block.functional_name,
        "tags": list(block.tags),
        "content": dict(block.content),
        "contains": list(block.contains),
        "inputs": [
            {
                "source_block_id": item.source_block_id,
                "port": item.port.value,
                "name": item.name,
                "enabled": item.enabled,
                "order": item.order,
                "metadata": dict(item.metadata),
            }
            for item in block.inputs
        ],
        "tree": _tree_to_dict(block.tree),
        "graph": _graph_to_dict(block.graph),
    }


def block_from_dict(data: dict) -> Block:
    inputs = [
        InputConnection(
            source_block_id=item["source_block_id"],
            port=PortType(item["port"]),
            name=item.get("name", ""),
            enabled=item.get("enabled", True),
            order=item.get("order", 0),
            metadata=dict(item.get("metadata", {})),
        )
        for item in data.get("inputs", [])
    ]

    access_mode = _as_access_mode(data.get("access_mode"))
    provenance = normalize_block_provenance(data.get("provenance"), access_mode=access_mode)

    return Block(
        id=data["id"],
        type=BlockType(data["type"]),
        profile=data.get("profile", "generic"),
        name=data.get("name", ""),
        description=data.get("description", ""),
        prompt_ref=data.get("prompt_ref", ""),
        prompt_generated=data.get("prompt_generated", ""),
        comment=data.get("comment", ""),
        exposed=data.get("exposed", data.get("shared", False)),
        domain=BlockDomain(data.get("domain", BlockDomain.LIB.value)),
        access_mode=access_mode,
        provenance=provenance,
        container_paths={
            str(container_id): str(path_value or "")
            for container_id, path_value in dict(data.get("container_paths", {})).items()
            if str(container_id).strip()
        },
        functional_name=data.get("functional_name", ""),
        tags=list(data.get("tags", [])),
        content=dict(data.get("content", {})),
        contains=list(data.get("contains", [])),
        inputs=inputs,
        tree=_tree_from_dict(data.get("tree")),
        graph=_graph_from_dict(data.get("graph")),
    )


def _as_access_mode(value: object) -> BlockAccessMode:
    if isinstance(value, BlockAccessMode):
        return value
    if isinstance(value, str):
        try:
            return BlockAccessMode(value.strip().lower())
        except ValueError:
            return BlockAccessMode.OWNED
    return BlockAccessMode.OWNED

def _tree_to_dict(tree: FreeTree | None) -> dict | None:
    if tree is None:
        return None
    return {
        "root_ids": list(tree.root_ids),
        "nodes": {
            node_id: {
                "id": node.id,
                "kind": node.kind,
                "name": node.name,
                "block_id": node.block_id,
                "children": list(node.children),
            }
            for node_id, node in tree.nodes.items()
        },
    }


def _tree_from_dict(data: dict | None) -> FreeTree | None:
    if data is None:
        return None
    nodes = {
        node_id: FreeTreeNode(
            id=node_data["id"],
            kind=node_data["kind"],
            name=node_data.get("name", ""),
            block_id=node_data.get("block_id"),
            children=list(node_data.get("children", [])),
        )
        for node_id, node_data in data.get("nodes", {}).items()
    }
    return FreeTree(root_ids=list(data.get("root_ids", [])), nodes=nodes)


def _graph_to_dict(graph: FreeGraph | None) -> dict | None:
    if graph is None:
        return None
    return {
        "nodes": {
            node_id: {
                "id": node.id,
                "block_id": node.block_id,
                "x": node.x,
                "y": node.y,
                "width": node.width,
                "height": node.height,
            }
            for node_id, node in graph.nodes.items()
        },
        "edges": {
            edge_id: {
                "id": edge.id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "label": edge.label,
            }
            for edge_id, edge in graph.edges.items()
        },
    }


def _graph_from_dict(data: dict | None) -> FreeGraph | None:
    if data is None:
        return None
    nodes = {
        node_id: FreeGraphNode(
            id=node_data["id"],
            block_id=node_data["block_id"],
            x=float(node_data.get("x", 0.0)),
            y=float(node_data.get("y", 0.0)),
            width=float(node_data.get("width", 0.0)),
            height=float(node_data.get("height", 0.0)),
        )
        for node_id, node_data in data.get("nodes", {}).items()
    }
    edges = {
        edge_id: FreeGraphEdge(
            id=edge_data["id"],
            source_node_id=edge_data["source_node_id"],
            target_node_id=edge_data["target_node_id"],
            label=edge_data.get("label", ""),
        )
        for edge_id, edge_data in data.get("edges", {}).items()
    }
    return FreeGraph(nodes=nodes, edges=edges)
