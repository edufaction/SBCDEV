from pathlib import Path

from application import CharacterWorkspaceService, LibraryWorkspaceService
from domain import Block, BlockType
from infrastructure.storage import ProjectStorageService


def test_character_workspace_service_creates_template_under_characters_root() -> None:
    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        content={"workspace_role": "characters_root"},
    )
    blocks = [root]

    service = CharacterWorkspaceService()
    character = service.create_character(blocks, name="Ariane")

    assert character.profile == "character"
    assert character.id in root.contains
    assert character.container_paths[root.id] == ""

    by_id = {block.id: block for block in blocks}
    form_ids = list(character.contains)
    assert form_ids
    for form_id in form_ids:
        form = by_id[form_id]
        assert form.profile == "character_form"
        assert form.container_paths[character.id] == ""
        for slot_id in form.contains:
            slot = by_id[slot_id]
            assert slot.profile == "template_slot"
            assert slot.container_paths[form.id] == ""


def test_character_workspace_service_lists_root_order_then_fallback() -> None:
    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        contains=["char_b"],
        content={"workspace_role": "characters_root"},
    )
    char_a = Block(id="char_a", type=BlockType.CONTAINER, profile="character", name="Alpha")
    char_b = Block(id="char_b", type=BlockType.CONTAINER, profile="character", name="Beta")
    blocks = [root, char_a, char_b]

    service = CharacterWorkspaceService()

    assert [block.id for block in service.list_characters(blocks)] == ["char_b", "char_a"]


def test_character_workspace_service_updates_character_payload_and_normalizes_tags() -> None:
    character = Block(id="char_1", type=BlockType.CONTAINER, profile="character", name="Old Name")
    blocks = [character]

    service = CharacterWorkspaceService()
    updated = service.update_character_from_payload(
        blocks,
        {
            "character_id": "char_1",
            "name": "Nova",
            "description": "Lead hero",
            "functional_name": "hero_main",
            "comment": "Keep silhouette strong",
            "tags": ["Lead", "character", "lead", "hero"],
        },
    )

    assert updated is character
    assert updated.name == "Nova"
    assert updated.description == "Lead hero"
    assert updated.functional_name == "hero_main"
    assert updated.comment == "Keep silhouette strong"
    assert updated.tags == ["Lead", "character", "hero"]


def test_library_workspace_service_mounts_and_unmounts_library(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    library_path = tmp_path / "library"
    ProjectStorageService().create_project(project_path, "Demo")

    service = LibraryWorkspaceService()
    service.create_library(library_path, name="Characters")

    mounted = service.mount_library(project_path, library_path=library_path, label="Characters")
    mounts = service.list_mounted_libraries(project_path)

    assert mounted["label"] == "Characters"
    assert len(mounts) == 1
    assert mounts[0]["path"] == str(library_path.resolve())

    remaining = service.unmount_library(project_path, mount_id=mounted["id"])
    assert remaining == []
