from pathlib import Path

from application import MountedStorageProjectionService
from domain import Block, BlockAccessMode, BlockDomain, BlockType
from infrastructure.storage import LibraryStorageService, ProjectStorageService


def test_mounted_storage_projection_service_projects_canonical_library_roots(tmp_path: Path) -> None:
    host_project = tmp_path / "host_project.sbcprj"
    library_path = tmp_path / "source_library"
    project_storage = ProjectStorageService()
    library_storage = LibraryStorageService()
    project_storage.create_project(host_project, "Host")
    library_storage.create_library(library_path, "Source Library")

    source_storage_root = Block(
        id="src_storage_root",
        type=BlockType.CONTAINER,
        profile="storage_root",
        name="Source Storage",
        domain=BlockDomain.LIB,
        content={"storage_kind": "project_space", "source_kind": "project"},
        contains=["src_story_root"],
    )
    source_story_root = Block(
        id="src_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story Root",
        domain=BlockDomain.STORY,
        content={
            "workspace_role": "story_root",
            "workspace_scope": "project",
            "storage_root_id": "src_storage_root",
        },
        contains=["src_shot"],
    )
    source_shot = Block(
        id="src_shot",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Opening",
        domain=BlockDomain.STORY,
        container_paths={"src_story_root": ""},
    )
    library_storage.save_blocks(library_path, [source_storage_root, source_story_root, source_shot])

    mounted = project_storage.add_mounted_library(host_project, library_path=library_path, label="Source Library")

    service = MountedStorageProjectionService(project_storage=project_storage, library_storage=library_storage)
    projected = service.load_project_blocks(host_project)
    by_id = {block.id: block for block in projected}

    projected_storage_root_id = f"blk_mount_{mounted['id']}_src_storage_root"
    projected_story_root_id = f"blk_mount_{mounted['id']}_src_story_root"
    projected_shot_id = f"blk_mount_{mounted['id']}_src_shot"

    assert projected_storage_root_id in by_id
    assert projected_story_root_id in by_id
    assert projected_shot_id in by_id
    assert by_id[projected_storage_root_id].profile == "storage_root"
    assert by_id[projected_storage_root_id].as_container().storage_kind == "mounted_lib"
    assert by_id[projected_storage_root_id].as_container().mount_id == mounted["id"]
    assert by_id[projected_story_root_id].as_container().workspace_scope == f"mount:{mounted['id']}"
    assert by_id[projected_story_root_id].as_container().storage_root_id == projected_storage_root_id
    assert by_id[projected_shot_id].access_mode is BlockAccessMode.LINK
    assert by_id[projected_shot_id].provenance.get("projected_mount") is True
    assert by_id[projected_shot_id].provenance.get("source_block_id") == "src_shot"


def test_mounted_storage_projection_service_persistable_blocks_skip_projected_mounts() -> None:
    service = MountedStorageProjectionService()
    local = Block(id="local_1", type=BlockType.TEXT, profile="note", name="Local")
    projected = Block(
        id="mount_1",
        type=BlockType.TEXT,
        profile="note",
        name="Projected",
        access_mode=BlockAccessMode.LINK,
        provenance={"kind": "lib_link", "projected_mount": True, "mount_id": "m1"},
    )

    persisted = service.persistable_blocks([local, projected])

    assert [block.id for block in persisted] == ["local_1"]
