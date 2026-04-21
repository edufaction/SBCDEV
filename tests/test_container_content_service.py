from pathlib import Path

from application import ContainerContentService, ImportRequest, ProjectSession
from domain import Block, BlockDomain, BlockType, FreeGraph, FreeGraphNode
from infrastructure.storage import ProjectStorageService


def test_container_content_service_creates_note_in_container(tmp_path: Path) -> None:
    project_path = tmp_path / "content_notes.sbcprj"
    ProjectStorageService().create_project(project_path, "Content Notes")

    story_root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story",
        domain=BlockDomain.STORY,
        contains=["shot_1"],
        content={"workspace_role": "story_root"},
    )
    shot = Block(
        id="shot_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        domain=BlockDomain.STORY,
        container_paths={"blk_story_root": ""},
    )
    session = ProjectSession(project_root=project_path, blocks=[story_root, shot])

    result = ContainerContentService().create_note(session, container_id="shot_1")

    note = next(block for block in session.blocks if block.id == result.affected_block_ids[0])
    updated_shot = session.find_container("shot_1")

    assert note.type == BlockType.TEXT
    assert note.profile == "note"
    assert note.content["note_style"] == "postit"
    assert updated_shot is not None
    assert note.id in updated_shot.contains


def test_container_content_service_imports_into_placeholder_and_preserves_graph_node(tmp_path: Path) -> None:
    storage = ProjectStorageService()
    project_path = tmp_path / "content_imports.sbcprj"
    storage.create_project(project_path, "Content Imports")

    characters_root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters",
        domain=BlockDomain.CHARACTERS,
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Alice",
        domain=BlockDomain.CHARACTERS,
        contains=["form_1"],
        container_paths={"blk_characters_root": ""},
    )
    placeholder = Block(
        id="slot_front",
        type=BlockType.EMPTY,
        profile="template_slot",
        name="Front View",
        domain=BlockDomain.CHARACTERS,
        container_paths={"form_1": ""},
        content={"template_slot": True, "expected_types": ["image"]},
    )
    form = Block(
        id="form_1",
        type=BlockType.CONTAINER,
        profile="character_form",
        name="Main Form",
        domain=BlockDomain.CHARACTERS,
        contains=[placeholder.id],
        container_paths={"char_1": ""},
        graph=FreeGraph(
            nodes={
                "n1": FreeGraphNode(id="n1", block_id=placeholder.id, x=48.0, y=84.0),
            }
        ),
    )
    session = ProjectSession(project_root=project_path, blocks=[characters_root, character, form, placeholder])

    source_file = tmp_path / "front.png"
    source_file.write_bytes(b"fake-png-content")

    result = ContainerContentService().import_files(
        session,
        ImportRequest(
            container_id="form_1",
            file_paths=[str(source_file)],
            target_block_id="slot_front",
            graph_drop=(260.0, 310.0),
            source_tag="workspace_graph_drop",
        ),
    )

    replaced = next(block for block in session.blocks if block.id == "slot_front")
    updated_form = session.find_container("form_1")

    assert result.replaced_count == 1
    assert replaced.type == BlockType.IMAGE
    assert replaced.profile == "asset"
    assert replaced.content["storage_path"].startswith("storage/files/")
    assert updated_form is not None
    node = updated_form.graph.nodes["n1"]
    assert node.block_id == "slot_front"
    assert node.x == 48.0
    assert node.y == 84.0
