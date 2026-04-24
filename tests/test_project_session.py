from pathlib import Path

from application import ProjectSession
from domain import Block, BlockAccessMode, BlockDomain, BlockType
from infrastructure.storage import ProjectStorageService


def test_project_session_persists_and_loads_blocks(tmp_path: Path) -> None:
    storage = ProjectStorageService()
    project_path = tmp_path / "session_demo.sbcprj"
    storage.create_project(project_path, "Session Demo")

    root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story",
        domain=BlockDomain.STORY,
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
    root.contains.append(shot.id)

    session = ProjectSession(project_root=project_path, blocks=[root, shot])
    session.persist()

    restored = ProjectSession()
    loaded = restored.load(project_path)

    assert restored.project_root == project_path.resolve()
    assert [block.id for block in loaded] == ["blk_story_root", "shot_1"]
    assert restored.find_container("shot_1") is not None


def test_project_session_persist_skips_projected_mount_blocks(tmp_path: Path) -> None:
    storage = ProjectStorageService()
    project_path = tmp_path / "session_mounted_skip.sbcprj"
    storage.create_project(project_path, "Session Mounted Skip")

    local = Block(id="blk_story_root", type=BlockType.CONTAINER, profile="workspace_root", name="Story")
    projected = Block(
        id="blk_mount_demo_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Mounted Story",
        access_mode=BlockAccessMode.LINK,
        provenance={"kind": "lib_link", "projected_mount": True, "mount_id": "demo"},
    )

    session = ProjectSession(project_root=project_path, blocks=[local, projected])
    session.persist()

    loaded = storage.load_blocks(project_path)
    assert [block.id for block in loaded] == ["blk_story_root"]
