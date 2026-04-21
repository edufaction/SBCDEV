from pathlib import Path

from application import ProjectStructureService
from domain import Block, BlockDomain, BlockType
from infrastructure.storage import ProjectStorageService


def test_project_structure_service_seeds_default_workspace_structure(tmp_path: Path) -> None:
    project_path = tmp_path / "project_structure_seed.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Structure Seed")
    service = ProjectStructureService(storage=storage)

    service.seed_workspace_structure_defaults(project_path)

    blocks = storage.load_blocks(project_path)
    by_id = {block.id: block for block in blocks}
    assert "blk_project_root" in by_id
    assert "blk_characters_root" in by_id
    assert "blk_story_root" in by_id
    assert "blk_lib_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert "blk_internal_lib_empty" in by_id
    assert by_id["blk_project_root"].profile == "workspace_root"
    assert by_id["blk_internal_lib_root"].name == "INTERNALLIB"
    assert by_id["blk_internal_lib_empty"].id in by_id["blk_internal_lib_root"].contains


def test_project_structure_service_ensures_workspace_roots_on_open(tmp_path: Path) -> None:
    project_path = tmp_path / "project_structure_open.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Structure Open")
    storage.save_blocks(
        project_path,
        [Block(id="blk_img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", content={"path": "a.png"})],
    )
    service = ProjectStructureService(storage=storage)

    updated = service.ensure_workspace_structure_on_open(project_path, list(storage.load_blocks(project_path)))

    by_id = {block.id: block for block in updated}
    assert "blk_project_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert "blk_internal_lib_empty" in by_id
    assert by_id["blk_project_root"].profile == "workspace_root"
    assert by_id["blk_internal_lib_root"].domain == BlockDomain.LIB
    assert by_id["blk_internal_lib_root"].id in by_id["blk_project_root"].contains


def test_project_structure_service_migrates_legacy_virtual_aliases(tmp_path: Path) -> None:
    project_path = tmp_path / "project_structure_legacy.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Structure Legacy")
    storage.save_blocks(
        project_path,
        [
            Block(
                id="blk_characters_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="Characters Root",
                domain=BlockDomain.CHARACTERS,
                contains=[],
            ),
            Block(
                id="blk_story_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="Story Root",
                domain=BlockDomain.STORY,
                contains=[],
            ),
            Block(
                id="blk_lib_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="Library Root",
                domain=BlockDomain.LIB,
                contains=[],
            ),
            Block(
                id="blk_virtual_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="VIRTUAL",
                domain=BlockDomain.LIB,
                contains=["blk_virtual_empty"],
            ),
            Block(
                id="blk_virtual_empty",
                type=BlockType.EMPTY,
                profile="virtual_empty",
                name="Drop Resources Here",
                domain=BlockDomain.LIB,
            ),
        ],
    )
    service = ProjectStructureService(storage=storage)

    updated = service.ensure_workspace_structure_on_open(project_path, list(storage.load_blocks(project_path)))

    by_id = {block.id: block for block in updated}
    assert "blk_virtual_root" not in by_id
    assert "blk_virtual_empty" not in by_id
    assert "blk_project_root" in by_id
    assert by_id["blk_internal_lib_root"].name == "INTERNALLIB"
    assert by_id["blk_internal_lib_empty"].id in by_id["blk_internal_lib_root"].contains
