from application import UseCaseService
from infrastructure.repositories import BlockRepository
from services import BlockService


def _build_use_case_service() -> UseCaseService:
    return UseCaseService(BlockService(BlockRepository()))


def test_add_to_container_adds_block_to_contains() -> None:
    use_case = _build_use_case_service()
    container = use_case.create_block(type="container", name="Shot 01")
    image = use_case.create_block(type="image", name="Caroline")

    updated_container = use_case.add_to_container(container.id, image.id)
    assert image.id in updated_container.contains


def test_add_to_container_adds_block_ref_to_embedded_tree() -> None:
    use_case = _build_use_case_service()
    container = use_case.create_block(type="container", name="Shot 01")
    image = use_case.create_block(type="image", name="Caroline")

    updated_container = use_case.add_to_container(container.id, image.id)
    assert updated_container.tree is not None
    block_ref_ids = [node.block_id for node in updated_container.tree.nodes.values() if node.kind == "block_ref"]
    assert image.id in block_ref_ids


def test_create_block_in_container_updates_embedded_tree() -> None:
    use_case = _build_use_case_service()
    shot = use_case.create_block(type="container", name="Shot 01")

    image = use_case.create_block_in_container(
        parent_container_id=shot.id,
        type="image",
        name="Caroline",
    )

    updated_shot = use_case.resolve_container(shot.id)["container"]

    assert image.id in updated_shot.contains
    assert updated_shot.tree is not None
    block_ref_ids = [node.block_id for node in updated_shot.tree.nodes.values() if node.kind == "block_ref"]
    assert image.id in block_ref_ids
