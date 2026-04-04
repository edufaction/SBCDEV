import pytest

from domain import BlockType, ValidationError
from infrastructure.repositories import BlockRepository
from services import BlockService


@pytest.mark.parametrize("parent_profile", ["character", "Caractere"])
def test_character_container_accepts_character_form_profile(parent_profile: str) -> None:
    service = BlockService(BlockRepository())

    parent = service.create_block(
        block_type=BlockType.CONTAINER,
        profile=parent_profile,
        name="Character",
    )
    child_form = service.create_block(
        block_type=BlockType.CONTAINER,
        profile="character_form",
        name="Default form",
    )

    updated_parent = service.add_to_container(parent.id, child_form.id)
    assert child_form.id in updated_parent.contains


def test_character_container_rejects_non_character_form_child() -> None:
    service = BlockService(BlockRepository())

    parent = service.create_block(
        block_type=BlockType.CONTAINER,
        profile="character",
        name="Character",
    )
    child_image = service.create_block(
        block_type=BlockType.IMAGE,
        profile="asset",
        name="Face",
    )

    with pytest.raises(ValidationError):
        service.add_to_container(parent.id, child_image.id)


@pytest.mark.parametrize(
    "child_type",
    [BlockType.EMPTY, BlockType.IMAGE, BlockType.VIDEO, BlockType.PROMPT, BlockType.TEXT, BlockType.AUDIO],
)
def test_character_form_container_accepts_media_blocks(child_type: BlockType) -> None:
    service = BlockService(BlockRepository())

    parent_form = service.create_block(
        block_type=BlockType.CONTAINER,
        profile="character_form",
        name="Form",
    )
    child = service.create_block(
        block_type=child_type,
        profile="asset",
        name=f"Asset {child_type.value}",
    )

    updated_form = service.add_to_container(parent_form.id, child.id)
    assert child.id in updated_form.contains


def test_character_form_container_rejects_nested_container() -> None:
    service = BlockService(BlockRepository())

    parent_form = service.create_block(
        block_type=BlockType.CONTAINER,
        profile="character_form",
        name="Form",
    )
    nested_container = service.create_block(
        block_type=BlockType.CONTAINER,
        profile="container",
        name="Nested",
    )

    with pytest.raises(ValidationError):
        service.add_to_container(parent_form.id, nested_container.id)


def test_generic_container_profile_keeps_default_permissive_behavior() -> None:
    service = BlockService(BlockRepository())

    generic_parent = service.create_block(
        block_type=BlockType.CONTAINER,
        profile="shot",
        name="Shot A",
    )
    image = service.create_block(
        block_type=BlockType.IMAGE,
        profile="asset",
        name="Ref",
    )

    updated_parent = service.add_to_container(generic_parent.id, image.id)
    assert image.id in updated_parent.contains


def test_non_container_parent_cannot_contain_child() -> None:
    service = BlockService(BlockRepository())

    non_container_parent = service.create_block(
        block_type=BlockType.TEXT,
        profile="note",
        name="Not a container",
    )
    child = service.create_block(
        block_type=BlockType.IMAGE,
        profile="asset",
        name="Image",
    )

    with pytest.raises(ValidationError):
        service.add_to_container(non_container_parent.id, child.id)
