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


def test_add_graph_edge_is_forbidden_when_not_derived_from_business_link() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img1 = use_case.create_block(type="image", name="Img 1")
    img2 = use_case.create_block(type="image", name="Img 2")

    use_case.add_to_container(shot.id, img1.id)
    use_case.add_to_container(shot.id, img2.id)
    node1 = use_case.add_block_to_graph(shot.id, img1.id, x=10, y=20)
    node2 = use_case.add_block_to_graph(shot.id, img2.id, x=30, y=40)

    with pytest.raises(ValidationError):
        use_case.add_graph_edge(shot.id, node1.id, node2.id, label="ref")


def test_connect_blocks_can_sync_graph_projection_when_container_and_nodes_are_known() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img1 = use_case.create_block(type="image", name="Img 1")
    img2 = use_case.create_block(type="image", name="Img 2")

    use_case.add_to_container(shot.id, img1.id)
    use_case.add_to_container(shot.id, img2.id)
    node1 = use_case.add_block_to_graph(shot.id, img1.id, x=10, y=20)
    node2 = use_case.add_block_to_graph(shot.id, img2.id, x=30, y=40)

    use_case.connect_blocks(
        target_block_id=img2.id,
        source_block_id=img1.id,
        port="in",
        name="ref",
        container_id=shot.id,
    )

    graph = use_case.get_graph(shot.id)
    assert any(
        edge.source_node_id == node1.id and edge.target_node_id == node2.id
        for edge in graph.edges.values()
    )


def test_disconnect_blocks_removes_business_link_and_graph_projection() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img1 = use_case.create_block(type="image", name="Img 1")
    img2 = use_case.create_block(type="image", name="Img 2")

    use_case.add_to_container(shot.id, img1.id)
    use_case.add_to_container(shot.id, img2.id)
    node1 = use_case.add_block_to_graph(shot.id, img1.id, x=10, y=20)
    node2 = use_case.add_block_to_graph(shot.id, img2.id, x=30, y=40)
    use_case.connect_blocks(
        target_block_id=img2.id,
        source_block_id=img1.id,
        port="in",
        name="ref",
        container_id=shot.id,
    )

    updated_target = use_case.disconnect_blocks(
        target_block_id=img2.id,
        source_block_id=img1.id,
        port="in",
        name="ref",
        container_id=shot.id,
    )
    assert updated_target.inputs == []

    graph = use_case.get_graph(shot.id)
    assert all(
        not (edge.source_node_id == node1.id and edge.target_node_id == node2.id)
        for edge in graph.edges.values()
    )


def test_move_block_in_graph_creates_or_updates_embedded_node_position() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")
    img = use_case.create_block(type="image", name="Img 1")

    use_case.add_to_container(shot.id, img.id)

    created = use_case.move_block_in_graph(shot.id, img.id, x=140, y=220)
    assert created.block_id == img.id
    assert created.x == 140
    assert created.y == 220

    moved = use_case.move_block_in_graph(shot.id, img.id, x=320, y=410)
    assert moved.id == created.id
    assert moved.x == 320
    assert moved.y == 410
