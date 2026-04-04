from domain import BlockType
from infrastructure.repositories import BlockRepository
from services import BlockService, FreeTreeService


def test_creating_container_creates_embedded_tree() -> None:
    block_service = BlockService(BlockRepository())
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")

    assert container.tree is not None
    assert container.tree.root_ids == []
    assert container.tree.nodes == {}


def test_creating_non_container_has_no_tree() -> None:
    block_service = BlockService(BlockRepository())
    image = block_service.create_block(block_type=BlockType.IMAGE, profile="asset", name="Image")

    assert image.tree is None


def test_create_folder_works_on_embedded_tree() -> None:
    block_service = BlockService(BlockRepository())
    free_tree_service = FreeTreeService()
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")

    folder = free_tree_service.create_folder(container, None, "Folder A")

    assert container.tree is not None
    assert folder.id in container.tree.root_ids
    assert container.tree.nodes[folder.id].kind == "folder"


def test_move_node_works_on_embedded_tree() -> None:
    block_service = BlockService(BlockRepository())
    free_tree_service = FreeTreeService()
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")

    folder = free_tree_service.create_folder(container, None, "Folder A")
    node = free_tree_service.add_block_ref(container, "block_1", "Block 1")
    free_tree_service.move_node(container, node.id, folder.id)

    assert container.tree is not None
    assert node.id not in container.tree.root_ids
    assert node.id in container.tree.nodes[folder.id].children


def test_remove_node_works_on_embedded_tree() -> None:
    block_service = BlockService(BlockRepository())
    free_tree_service = FreeTreeService()
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")

    folder = free_tree_service.create_folder(container, None, "Folder A")
    child = free_tree_service.create_folder(container, folder.id, "Folder B")
    node = free_tree_service.add_block_ref(container, "block_1", "Block 1")
    free_tree_service.move_node(container, node.id, folder.id)

    free_tree_service.remove_node(container, folder.id)

    assert container.tree is not None
    assert folder.id not in container.tree.nodes
    assert child.id not in container.tree.nodes
    assert node.id not in container.tree.nodes
