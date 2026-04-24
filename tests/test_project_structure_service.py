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
    assert "blk_storage_project_root" in by_id
    assert "blk_storage_internal_root" in by_id
    assert "blk_characters_root" in by_id
    assert "blk_story_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert by_id["blk_storage_project_root"].profile == "storage_root"
    assert by_id["blk_storage_internal_root"].profile == "storage_root"
    assert by_id["blk_characters_root"].as_container().storage_root_id == "blk_storage_project_root"
    assert by_id["blk_characters_root"].as_container().workspace_scope == "project"
    assert by_id["blk_internal_lib_root"].as_container().storage_root_id == "blk_storage_internal_root"
    assert by_id["blk_internal_lib_root"].as_container().workspace_scope == "internal"
    assert by_id["blk_internal_lib_root"].name == "INTERNALLIB"
    assert by_id["blk_characters_root"].id in by_id["blk_storage_project_root"].contains
    assert by_id["blk_story_root"].id in by_id["blk_storage_project_root"].contains
    assert by_id["blk_internal_lib_root"].id in by_id["blk_storage_internal_root"].contains


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
    assert "blk_storage_project_root" in by_id
    assert "blk_storage_internal_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert by_id["blk_story_root"].as_container().storage_root_id == "blk_storage_project_root"
    assert by_id["blk_internal_lib_root"].domain == BlockDomain.LIB
    assert by_id["blk_internal_lib_root"].as_container().storage_root_id == "blk_storage_internal_root"


def test_project_structure_service_removes_legacy_project_root_on_open(tmp_path: Path) -> None:
    project_path = tmp_path / "project_structure_remove_project_root.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Structure Remove Project Root")
    storage.save_blocks(
        project_path,
        [
            Block(
                id="blk_project_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="PROJET",
                domain=BlockDomain.LIB,
                content={"workspace_role": "project_root", "workspace_scope": "project"},
            ),
            Block(id="blk_img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", content={"path": "a.png"}),
        ],
    )
    service = ProjectStructureService(storage=storage)

    updated = service.ensure_workspace_structure_on_open(project_path, list(storage.load_blocks(project_path)))

    by_id = {block.id: block for block in updated}
    assert "blk_project_root" not in by_id
    assert by_id["blk_characters_root"].id in by_id["blk_storage_project_root"].contains
    assert by_id["blk_story_root"].id in by_id["blk_storage_project_root"].contains
