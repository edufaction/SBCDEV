from domain import BlockType, NotFoundError, PortType
from infrastructure.repositories import BlockRepository
from services import BlockService


def test_create_block() -> None:
    repo = BlockRepository()
    service = BlockService(repo)

    block = service.create_block(
        block_type=BlockType.IMAGE,
        profile="reference_image",
        name="Character Front",
        content={"file_path": "assets/images/front.png"},
    )

    assert block.id
    assert block.type is BlockType.IMAGE
    assert block.profile == "reference_image"
    assert block.name == "Character Front"
    assert block.content["file_path"].endswith("front.png")


def test_add_and_remove_from_container() -> None:
    repo = BlockRepository()
    service = BlockService(repo)

    parent = service.create_block(block_type=BlockType.CONTAINER, profile="shot", name="Shot A")
    child = service.create_block(block_type=BlockType.TEXT, profile="note", name="Bio")

    updated_parent = service.add_to_container(parent.id, child.id)
    assert child.id in updated_parent.contains

    updated_parent = service.remove_from_container(parent.id, child.id)
    assert child.id not in updated_parent.contains

    try:
        service.remove_from_container(parent.id, child.id)
        assert False, "Expected NotFoundError"
    except NotFoundError:
        pass


def test_add_and_remove_input() -> None:
    repo = BlockRepository()
    service = BlockService(repo)

    target = service.create_block(block_type=BlockType.CONTAINER, profile="story_block", name="Scene 01")
    source = service.create_block(block_type=BlockType.IMAGE, profile="frame", name="Frame 01")

    updated_target = service.add_input(
        target_id=target.id,
        source_block_id=source.id,
        port=PortType.IN,
        name="frame_ref",
    )
    assert len(updated_target.inputs) == 1
    assert updated_target.inputs[0].name == "frame_ref"
    assert updated_target.inputs[0].source_block_id == source.id
    assert updated_target.inputs[0].port is PortType.IN

    updated_target = service.remove_input(
        target_id=target.id,
        source_block_id=source.id,
        port=PortType.IN,
        name="frame_ref",
    )
    assert updated_target.inputs == []
