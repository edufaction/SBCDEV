import pytest

from application import UseCaseService
from domain import ValidationError
from infrastructure.repositories import BlockRepository
from services import BlockService


def _build_use_case_service() -> UseCaseService:
    return UseCaseService(BlockService(BlockRepository()))


def test_add_to_container_does_not_add_node_to_graph() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img = use_case.create_block(type="image", name="Caroline")

    use_case.add_to_container(shot.id, img.id)
    graph = use_case.get_graph(shot.id)

    assert len(graph.nodes) == 0


def test_add_block_to_graph_only_works_if_block_is_in_contains() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img = use_case.create_block(type="image", name="Caroline")

    with pytest.raises(ValidationError):
        use_case.add_block_to_graph(shot.id, img.id, x=100, y=120)

    use_case.add_to_container(shot.id, img.id)
    node = use_case.add_block_to_graph(shot.id, img.id, x=100, y=120)
    assert node.block_id == img.id
    assert node.x == 100
    assert node.y == 120


def test_graph_contains_only_explicitly_added_blocks() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img1 = use_case.create_block(type="image", name="Img 1")
    img2 = use_case.create_block(type="image", name="Img 2")

    use_case.add_to_container(shot.id, img1.id)
    use_case.add_to_container(shot.id, img2.id)
    use_case.add_block_to_graph(shot.id, img1.id, x=10, y=20)

    graph = use_case.get_graph(shot.id)
    block_ids = {node.block_id for node in graph.nodes.values()}
    assert block_ids == {img1.id}


def test_add_graph_edge_between_existing_nodes() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img1 = use_case.create_block(type="image", name="Img 1")
    img2 = use_case.create_block(type="image", name="Img 2")

    use_case.add_to_container(shot.id, img1.id)
    use_case.add_to_container(shot.id, img2.id)
    node1 = use_case.add_block_to_graph(shot.id, img1.id, x=10, y=20)
    node2 = use_case.add_block_to_graph(shot.id, img2.id, x=30, y=40)

    edge = use_case.add_graph_edge(shot.id, node1.id, node2.id, label="ref")
    graph = use_case.get_graph(shot.id)
    assert edge.id in graph.edges
