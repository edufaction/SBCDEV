from application.block_template_service import BlockTemplateService
from domain import BlockDomain, BlockType


def test_character_template_instantiation_builds_expected_hierarchy() -> None:
    service = BlockTemplateService()

    blocks = service.instantiate_character_template(character_name="Luna")
    by_id = {block.id: block for block in blocks}

    character_blocks = [block for block in blocks if block.type == BlockType.CONTAINER and block.profile == "character"]
    assert len(character_blocks) == 1
    character = character_blocks[0]
    assert character.name == "Luna"
    assert character.domain == BlockDomain.CHARACTERS
    assert len(character.contains) >= 2

    form_blocks = [by_id[child_id] for child_id in character.contains]
    assert all(block.type == BlockType.CONTAINER and block.profile == "character_form" for block in form_blocks)

    slot_blocks = [block for block in blocks if block.type == BlockType.EMPTY and block.profile == "template_slot"]
    assert slot_blocks
    assert all(block.content.get("template_slot") is True for block in slot_blocks)

    for form in form_blocks:
        assert form.contains
        for child_id in form.contains:
            slot = by_id[child_id]
            assert slot.type == BlockType.EMPTY
            assert slot.profile == "template_slot"


def test_character_template_instantiation_supports_custom_domain() -> None:
    service = BlockTemplateService()

    blocks = service.instantiate_character_template(character_name="Noe", domain=BlockDomain.LIB)

    assert blocks
    assert all(block.domain == BlockDomain.LIB for block in blocks)
