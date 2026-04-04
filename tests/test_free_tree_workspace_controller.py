from application.free_tree_workspace_controller import FreeTreeItemSnapshot, FreeTreeWorkspaceController
from domain import Block, BlockType, FreeTree, FreeTreeNode


def _sample_blocks() -> list[Block]:
    return [
        Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container", contains=["img_1", "txt_1"]),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
        Block(id="txt_1", type=BlockType.TEXT, profile="note", name="Note 1"),
        Block(id="aud_1", type=BlockType.AUDIO, profile="voice", name="Audio 1"),
    ]


def test_set_blocks_builds_tree_and_locks_container_nodes() -> None:
    controller = FreeTreeWorkspaceController()
    controller.set_blocks(_sample_blocks())

    container_node_id = next(
        node_id
        for node_id, node in controller.tree.nodes.items()
        if node.kind == "folder" and node.block_id == "cnt_1"
    )
    assert container_node_id in controller.locked_node_ids

    child_ids = controller.tree.nodes[container_node_id].children
    assert child_ids
    assert all(controller.tree.nodes[child_id].block_id in {"img_1", "txt_1"} for child_id in child_ids)

    root_block_ids = {
        controller.tree.nodes[node_id].block_id
        for node_id in controller.tree.root_ids
        if controller.tree.nodes[node_id].kind == "block_ref"
    }
    assert "img_1" not in root_block_ids
    assert "txt_1" not in root_block_ids
    assert "aud_1" in root_block_ids


def test_move_block_ref_updates_container_relative_path() -> None:
    controller = FreeTreeWorkspaceController()
    controller.set_blocks(_sample_blocks())

    container_node_id = next(
        node_id
        for node_id, node in controller.tree.nodes.items()
        if node.kind == "folder" and node.block_id == "cnt_1"
    )
    folder_id = controller.add_folder("Principaux", parent_node_id=container_node_id)
    assert folder_id is not None
    image_node = controller.find_node_id_for_block("img_1")
    assert image_node is not None
    controller.move_node(image_node, folder_id)

    image_block = next(block for block in controller.blocks if block.id == "img_1")
    assert image_block.container_paths.get("cnt_1") == "Principaux"


def test_remove_folder_keeps_block_refs_and_reparents_to_root() -> None:
    controller = FreeTreeWorkspaceController()
    controller.set_blocks(
        [
            Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
            Block(id="txt_1", type=BlockType.TEXT, profile="note", name="Note 1"),
        ]
    )

    image_node = controller.find_node_id_for_block("img_1")
    assert image_node is not None
    folder_id = controller.add_folder("Folder A")
    assert folder_id is not None

    controller.move_node(image_node, folder_id)
    assert image_node in controller.tree.nodes[folder_id].children

    controller.remove_folder(folder_id)
    assert folder_id not in controller.tree.nodes
    assert image_node in controller.tree.root_ids


def test_add_folder_under_block_ref_targets_parent_folder() -> None:
    controller = FreeTreeWorkspaceController()
    controller.set_blocks(
        [
            Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
            Block(id="txt_1", type=BlockType.TEXT, profile="note", name="Note 1"),
        ]
    )

    folder_id = controller.add_folder("Folder A")
    assert folder_id is not None

    image_node = controller.find_node_id_for_block("img_1")
    assert image_node is not None
    controller.move_node(image_node, folder_id)

    nested_folder_id = controller.add_folder("Nested", parent_node_id=image_node)
    assert nested_folder_id is not None
    assert nested_folder_id in controller.tree.nodes[folder_id].children


def test_rebuild_from_snapshot_keeps_block_refs_without_children() -> None:
    controller = FreeTreeWorkspaceController()
    controller.set_blocks([Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1")])

    image_node = controller.find_node_id_for_block("img_1")
    assert image_node is not None

    snapshots = [
        FreeTreeItemSnapshot(
            node_id=image_node,
            node_kind="block_ref",
            name="Image 1",
            block_id="img_1",
            children=[
                FreeTreeItemSnapshot(
                    node_id="node_folder_user",
                    node_kind="folder",
                    name="Folder",
                )
            ],
        )
    ]

    controller.rebuild_from_snapshot(snapshots)

    assert image_node in controller.tree.nodes
    assert controller.tree.nodes[image_node].kind == "block_ref"
    assert controller.tree.nodes[image_node].children == []
    assert "node_folder_user" in controller.tree.nodes
    assert "node_folder_user" in controller.tree.root_ids


def test_apply_persisted_tree_deduplicates_same_block_between_container_and_root() -> None:
    controller = FreeTreeWorkspaceController()
    controller.set_blocks(_sample_blocks())

    persisted = FreeTree(
        root_ids=["node_container_cnt_1", "node_block_img_1_dup", "node_block_aud_1"],
        nodes={
            "node_container_cnt_1": FreeTreeNode(
                id="node_container_cnt_1",
                kind="folder",
                name="Container",
                block_id="cnt_1",
                children=["node_block_img_1", "node_block_txt_1"],
            ),
            "node_block_img_1": FreeTreeNode(
                id="node_block_img_1",
                kind="block_ref",
                name="Image 1",
                block_id="img_1",
            ),
            "node_block_img_1_dup": FreeTreeNode(
                id="node_block_img_1_dup",
                kind="block_ref",
                name="Image 1 (dup)",
                block_id="img_1",
            ),
            "node_block_txt_1": FreeTreeNode(
                id="node_block_txt_1",
                kind="block_ref",
                name="Note 1",
                block_id="txt_1",
            ),
            "node_block_aud_1": FreeTreeNode(
                id="node_block_aud_1",
                kind="block_ref",
                name="Audio 1",
                block_id="aud_1",
            ),
        },
    )

    controller.set_blocks(_sample_blocks(), persisted_tree=persisted)

    image_refs = [
        node_id
        for node_id, node in controller.tree.nodes.items()
        if node.kind == "block_ref" and node.block_id == "img_1"
    ]
    assert image_refs == ["node_block_img_1"]
    assert "node_block_img_1_dup" not in controller.tree.root_ids
