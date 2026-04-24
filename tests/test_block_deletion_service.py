from application import BlockDeletionService
from domain import Block, BlockType, FreeGraph, FreeGraphEdge, FreeGraphNode, FreeTree, FreeTreeNode, InputConnection, PortType


def test_block_deletion_service_removes_descendants_and_prunes_references() -> None:
    service = BlockDeletionService()
    root = Block(
        id="root_1",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Root",
        contains=["shot_1", "keep_1"],
        tree=FreeTree(
            root_ids=["node_shot", "node_keep"],
            nodes={
                "node_shot": FreeTreeNode(id="node_shot", kind="block_ref", name="Shot 1", block_id="shot_1"),
                "node_keep": FreeTreeNode(id="node_keep", kind="block_ref", name="Keep", block_id="keep_1"),
            },
        ),
    )
    shot = Block(
        id="shot_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        contains=["note_1"],
        container_paths={"root_1": ""},
        tree=FreeTree(
            root_ids=["node_note"],
            nodes={
                "node_note": FreeTreeNode(id="node_note", kind="block_ref", name="Note 1", block_id="note_1"),
            },
        ),
        graph=FreeGraph(
            nodes={
                "g1": FreeGraphNode(id="g1", block_id="note_1", x=10.0, y=20.0),
            },
            edges={
                "e1": FreeGraphEdge(id="e1", source_node_id="g1", target_node_id="g1", label="loop"),
            },
        ),
    )
    note = Block(
        id="note_1",
        type=BlockType.TEXT,
        profile="note",
        name="Note 1",
        container_paths={"shot_1": "", "root_1": ""},
    )
    keep = Block(
        id="keep_1",
        type=BlockType.IMAGE,
        profile="asset",
        name="Keep",
        container_paths={"root_1": ""},
    )
    consumer = Block(
        id="consumer_1",
        type=BlockType.TEXT,
        profile="preset",
        name="Consumer",
        container_paths={"shot_1": "", "root_1": ""},
    )
    consumer.inputs = [InputConnection(source_block_id="note_1", port=PortType.IN, name="ref")]

    blocks = [root, shot, note, keep, consumer]

    result = service.delete(blocks, block_id="shot_1")

    assert result.deleted_ids == ("shot_1", "note_1")
    assert [block.id for block in blocks] == ["root_1", "keep_1", "consumer_1"]
    assert root.contains == ["keep_1"]
    assert root.tree is not None
    assert root.tree.root_ids == ["node_keep"]
    assert set(root.tree.nodes) == {"node_keep"}
    assert keep.container_paths == {"root_1": ""}
    assert consumer.container_paths == {"root_1": ""}
    assert consumer.inputs == []


def test_block_deletion_service_refuses_workspace_root_deletion() -> None:
    service = BlockDeletionService()
    root = Block(id="root_1", type=BlockType.CONTAINER, profile="workspace_root", name="Root")

    try:
        service.preview([root], block_id="root_1")
    except ValueError as exc:
        assert str(exc) == "Workspace roots cannot be deleted."
    else:
        raise AssertionError("Expected workspace root deletion to be rejected.")
