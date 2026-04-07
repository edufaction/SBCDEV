from application import StoryShotService
from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree


def _workspace_roots() -> list[Block]:
    project_root = Block(
        id="blk_project_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="PROJET",
        domain=BlockDomain.LIB,
        content={"workspace_role": "project_root"},
        tree=FreeTree(),
        graph=FreeGraph(),
    )
    story_root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story Root",
        domain=BlockDomain.STORY,
        content={"workspace_role": "story_root"},
        tree=FreeTree(),
        graph=FreeGraph(),
    )
    project_root.contains = [story_root.id]
    return [project_root, story_root]


def test_create_shot_attaches_block_to_story_root() -> None:
    service = StoryShotService()
    blocks = _workspace_roots()

    created = service.create_shot(blocks, name="Opening")

    story_root = next(block for block in blocks if block.id == "blk_story_root")
    assert created.profile == "shot"
    assert created.domain == BlockDomain.STORY
    assert created.id in story_root.contains
    assert created.container_paths.get(story_root.id, "") == ""


def test_list_shots_prefers_story_root_order() -> None:
    service = StoryShotService()
    blocks = _workspace_roots()
    story_root = next(block for block in blocks if block.id == "blk_story_root")
    shot_a = service.create_shot(blocks, name="A")
    shot_b = service.create_shot(blocks, name="B")

    story_root.contains = [shot_b.id, shot_a.id]
    names = [block.name for block in service.list_shots(blocks)]
    assert names[:2] == ["B", "A"]


def test_create_shot_requires_story_root() -> None:
    service = StoryShotService()
    blocks = [
        Block(
            id="blk_project_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="PROJET",
            domain=BlockDomain.LIB,
            content={"workspace_role": "project_root"},
            tree=FreeTree(),
            graph=FreeGraph(),
        )
    ]

    try:
        service.create_shot(blocks, name="X")
    except ValueError as exc:
        assert "Story root" in str(exc)
    else:
        raise AssertionError("Expected ValueError when no story root is available")


def test_update_shot_updates_name_description_and_tags() -> None:
    service = StoryShotService()
    blocks = _workspace_roots()
    created = service.create_shot(blocks, name="Opening")

    updated = service.update_shot(
        blocks,
        shot_id=created.id,
        name="Opening Revised",
        description="Wide angle setup for opening sequence.",
        tags=["intro", "city", "intro"],
        functional_name="shot_opening_revised",
        comment="Keep this shot as intro anchor.",
    )

    assert updated.id == created.id
    assert updated.name == "Opening Revised"
    assert updated.description == "Wide angle setup for opening sequence."
    assert updated.tags == ["story", "intro", "city", "shot"]
    assert updated.functional_name == "shot_opening_revised"
    assert updated.comment == "Keep this shot as intro anchor."


def test_update_shot_rejects_empty_name() -> None:
    service = StoryShotService()
    blocks = _workspace_roots()
    created = service.create_shot(blocks, name="Opening")

    try:
        service.update_shot(
            blocks,
            shot_id=created.id,
            name="   ",
            description="",
            tags=[],
            functional_name="",
            comment="",
        )
    except ValueError as exc:
        assert "name" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError when shot name is empty")
