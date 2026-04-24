from application import UseCaseService
from domain import BlockDomain, BlockType, PortType
from infrastructure.repositories import BlockRepository
from services import BlockService


def _build_use_case_service() -> UseCaseService:
    repository = BlockRepository()
    block_service = BlockService(repository)
    return UseCaseService(block_service)


def test_create_block() -> None:
    use_case = _build_use_case_service()

    block = use_case.create_block(
        type="image",
        domain="lib",
        profile="asset",
        name="Caroline Main Reference",
        exposed=True,
        content={"url": "/assets/caroline_ref.png"},
    )

    assert block.type is BlockType.IMAGE
    assert block.domain is BlockDomain.LIB
    assert block.exposed is True
    assert block.profile == "asset"
    assert block.content["url"].endswith("caroline_ref.png")


def test_add_to_container_and_remove_from_container() -> None:
    use_case = _build_use_case_service()

    container = use_case.create_block(type="container", domain="story", profile="shot", name="Shot A")
    asset = use_case.create_block(type="image", domain="lib", profile="asset", name="Ref")

    updated_container = use_case.add_to_container(container.id, asset.id)
    assert asset.id in updated_container.contains

    updated_container = use_case.remove_from_container(container.id, asset.id)
    assert asset.id not in updated_container.contains


def test_connect_input() -> None:
    use_case = _build_use_case_service()

    target = use_case.create_block(type="container", domain="story", profile="shot", name="Shot A")
    source = use_case.create_block(type="image", domain="lib", profile="asset", name="Ref")

    updated_target = use_case.connect_input(
        target_block_id=target.id,
        source_block_id=source.id,
        port="in",
        name="main_ref",
    )

    assert len(updated_target.inputs) == 1
    assert updated_target.inputs[0].source_block_id == source.id
    assert updated_target.inputs[0].name == "main_ref"
    assert updated_target.inputs[0].port is PortType.IN


def test_list_blocks_by_domain() -> None:
    use_case = _build_use_case_service()

    story_a = use_case.create_block(type="container", domain="story", profile="shot", name="Shot A")
    story_b = use_case.create_block(type="text", domain="story", profile="dialogue", name="Dialog A")
    _ = use_case.create_block(type="image", domain="lib", profile="asset", name="Ref")

    story_blocks = use_case.list_blocks_by_domain("story")
    assert {block.id for block in story_blocks} == {story_a.id, story_b.id}


def test_list_exposed_blocks() -> None:
    use_case = _build_use_case_service()

    shared_story = use_case.create_block(
        type="text",
        domain="story",
        profile="dialogue",
        name="Exposed Story Text",
        exposed=True,
    )
    shared_lib = use_case.create_block(
        type="image",
        domain="lib",
        profile="asset",
        name="Exposed Lib Image",
        exposed=True,
    )
    _ = use_case.create_block(type="video", domain="story", profile="asset", name="Local Story Video", exposed=False)

    exposed_all = use_case.list_exposed_blocks()
    assert {block.id for block in exposed_all} == {shared_story.id, shared_lib.id}

    exposed_story_only = use_case.list_exposed_blocks("story")
    assert [block.id for block in exposed_story_only] == [shared_story.id]
