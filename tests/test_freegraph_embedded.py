import pytest

from domain import BlockType, NotFoundError, ValidationError
from infrastructure.repositories import BlockRepository
from services import BlockService, FreeGraphService


def test_creating_container_creates_embedded_graph() -> None:
    block_service = BlockService(BlockRepository())
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")

    assert container.graph is not None
    assert container.graph.nodes == {}
    assert container.graph.edges == {}


def test_creating_non_container_leaves_graph_none() -> None:
    block_service = BlockService(BlockRepository())
    image = block_service.create_block(block_type=BlockType.IMAGE, profile="asset", name="Image")

    assert image.graph is None


def test_move_node_updates_coordinates() -> None:
    block_service = BlockService(BlockRepository())
    graph_service = FreeGraphService()
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")
    source = block_service.create_block(block_type=BlockType.IMAGE, profile="asset", name="Source")
    block_service.add_to_container(container.id, source.id)
    container = block_service.get_block(container.id)

    node = graph_service.add_block_node(container, source.id, x=10, y=20)
    moved = graph_service.move_node(container, node.id, x=100, y=120)

    assert moved.x == 100
    assert moved.y == 120


def test_remove_node_removes_attached_edges() -> None:
    block_service = BlockService(BlockRepository())
    graph_service = FreeGraphService()
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")
    a = block_service.create_block(block_type=BlockType.IMAGE, profile="asset", name="A")
    b = block_service.create_block(block_type=BlockType.IMAGE, profile="asset", name="B")
    block_service.add_to_container(container.id, a.id)
    block_service.add_to_container(container.id, b.id)
    container = block_service.get_block(container.id)

    node_a = graph_service.add_block_node(container, a.id)
    node_b = graph_service.add_block_node(container, b.id)
    edge = graph_service.add_edge(container, node_a.id, node_b.id, label="ref")
    assert container.graph is not None
    assert edge.id in container.graph.edges

    graph_service.remove_node(container, node_a.id)
    assert node_a.id not in container.graph.nodes
    assert edge.id not in container.graph.edges


def test_add_edge_works_only_for_existing_nodes() -> None:
    block_service = BlockService(BlockRepository())
    graph_service = FreeGraphService()
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")
    a = block_service.create_block(block_type=BlockType.IMAGE, profile="asset", name="A")
    block_service.add_to_container(container.id, a.id)
    container = block_service.get_block(container.id)
    node_a = graph_service.add_block_node(container, a.id)

    with pytest.raises(NotFoundError):
        graph_service.add_edge(container, node_a.id, "missing-node", label="invalid")


def test_add_block_node_requires_block_already_in_contains() -> None:
    block_service = BlockService(BlockRepository())
    graph_service = FreeGraphService()
    container = block_service.create_block(block_type=BlockType.CONTAINER, profile="generic", name="Container")
    a = block_service.create_block(block_type=BlockType.IMAGE, profile="asset", name="A")

    with pytest.raises(ValidationError):
        graph_service.add_block_node(container, a.id)
