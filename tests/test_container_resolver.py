from application import UseCaseService
from infrastructure.repositories import BlockRepository
from services import BlockService


def _build_use_case_service() -> UseCaseService:
    repository = BlockRepository()
    block_service = BlockService(repository)
    return UseCaseService(block_service)


def test_resolve_container_basic_case() -> None:
    use_case = _build_use_case_service()

    container = use_case.create_block(type="container", domain="story", profile="shot", name="Briefing Caroline")
    image = use_case.create_block(type="image", domain="lib", profile="asset", name="Caroline Ref")
    use_case.add_to_container(container.id, image.id)

    resolved = use_case.resolve_container(container.id)

    assert resolved["container"].id == container.id
    assert [block.id for block in resolved["contained_blocks"]] == [image.id]
    assert resolved["contained_by_type"]["image"][0].id == image.id
    assert resolved["inputs_by_port"]["in"] == []
    assert any(edge["kind"] == "contains" and edge["to"] == image.id for edge in resolved["edges"])


def test_resolve_container_with_mixed_assets_shared_and_ports() -> None:
    use_case = _build_use_case_service()

    shot = use_case.create_block(type="container", domain="story", profile="shot", name="Shot B")
    image = use_case.create_block(
        type="image",
        domain="lib",
        profile="asset",
        name="Main Ref",
        exposed=True,
        functional_name="main_ref",
    )
    video = use_case.create_block(type="video", domain="story", profile="footage", name="Action Take")
    preset = use_case.create_block(
        type="text",
        domain="story",
        profile="preset",
        name="Preset Line",
        exposed=True,
        functional_name="preset_main",
    )
    prompt = use_case.create_block(type="prompt", domain="story", profile="prompt", name="Prompt Input")

    use_case.add_to_container(shot.id, image.id)
    use_case.add_to_container(shot.id, video.id)
    use_case.add_to_container(shot.id, preset.id)
    use_case.add_to_container(shot.id, prompt.id)

    use_case.connect_input(target_block_id=shot.id, source_block_id=image.id, port="in", name="main_ref")
    use_case.connect_input(target_block_id=shot.id, source_block_id=preset.id, port="top", name="prompt_preset")
    use_case.connect_input(target_block_id=shot.id, source_block_id=prompt.id, port="bottom", name="injector")

    resolved = use_case.resolve_container(shot.id)

    assert {block.id for block in resolved["contained_blocks"]} == {image.id, video.id, preset.id, prompt.id}
    assert set(resolved["contained_by_type"]) >= {"image", "video", "text", "prompt"}
    assert {block.id for block in resolved["exposed_contained_blocks"]} == {image.id, preset.id}
    assert len(resolved["inputs_by_port"]["in"]) == 1
    assert len(resolved["inputs_by_port"]["top"]) == 1
    assert len(resolved["inputs_by_port"]["bottom"]) == 1
    assert {block.id for block in resolved["functional_blocks"]} == {image.id, preset.id}

    node_ids = {node["id"] for node in resolved["nodes"]}
    assert shot.id in node_ids
    assert {image.id, video.id, preset.id, prompt.id}.issubset(node_ids)

    input_edges = [edge for edge in resolved["edges"] if edge["kind"] == "input"]
    assert {(edge["port"], edge["name"]) for edge in input_edges} == {
        ("in", "main_ref"),
        ("top", "prompt_preset"),
        ("bottom", "injector"),
    }
