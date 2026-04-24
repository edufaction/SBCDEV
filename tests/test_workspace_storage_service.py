import json
from pathlib import Path

from domain import Block, BlockType
from infrastructure.storage import LibraryStorageService, ProjectStorageService, WorkspaceStorageService


def test_workspace_storage_create_workspace_writes_kind_metadata(tmp_path: Path) -> None:
    service = WorkspaceStorageService(workspace_kind="library")
    workspace_path = tmp_path / "lib_a"
    service.create_workspace(workspace_path, "Library A")

    metadata = json.loads((workspace_path / "project.json").read_text(encoding="utf-8"))
    assert metadata["name"] == "Library A"
    assert metadata["kind"] == "library"
    assert metadata["storage_layout_version"] == 2
    assert metadata["mounted_libraries"] == []
    assert (workspace_path / "storage" / "files").exists()
    assert (workspace_path / "workspaces").exists()


def test_library_storage_service_uses_same_format_as_project(tmp_path: Path) -> None:
    library = LibraryStorageService()
    project = ProjectStorageService()
    library_path = tmp_path / "LIBRARIES" / "USER" / "MyLib"
    project_path = tmp_path / "MyProject"

    library.create_library(library_path, "MyLib")
    project.create_project(project_path, "MyProject")

    expected_files = {"project.json", "ui_state.json", "workspaces"}
    assert expected_files <= {path.name for path in library_path.iterdir()}
    assert expected_files <= {path.name for path in project_path.iterdir()}


def test_library_storage_service_can_save_and_load_blocks(tmp_path: Path) -> None:
    library = LibraryStorageService()
    library_path = tmp_path / "LIBRARIES" / "USER" / "CharactersLib"
    library.create_library(library_path, "CharactersLib")

    blocks = [Block(id="char_1", type=BlockType.TEXT, profile="character", name="Hero", content={"bio": "..."})]
    library.save_blocks(library_path, blocks)
    loaded = library.load_blocks(library_path)

    assert len(loaded) == 1
    assert loaded[0].id == "char_1"
    assert loaded[0].profile == "character"


def test_workspace_storage_ui_state_roundtrip(tmp_path: Path) -> None:
    service = WorkspaceStorageService(workspace_kind="project")
    workspace_path = tmp_path / "project_ui_state"
    service.create_workspace(workspace_path, "Project UI")

    payload = {"left_panel_width": 320, "section": "project"}
    service.save_ui_state(workspace_path, payload)

    loaded = service.load_ui_state(workspace_path)
    assert loaded == payload


def test_project_storage_mounted_libraries_add_and_remove_roundtrip(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_mounts"
    service.create_project(project_path, "Project Mounts")

    library_path = (tmp_path / "LIBRARIES" / "USER" / "CharactersLib").resolve()
    library_path.mkdir(parents=True, exist_ok=True)

    mounted = service.add_mounted_library(
        project_path,
        library_path=library_path,
        label="Characters Lib",
        enabled=True,
        read_only=True,
    )
    assert mounted["kind"] == "LIB"
    assert mounted["path"] == library_path.as_posix()
    assert mounted["label"] == "Characters Lib"
    assert mounted["enabled"] is True
    assert mounted["read_only"] is True
    assert mounted["id"]

    mounted_again = service.add_mounted_library(
        project_path,
        library_path=library_path,
        label="Characters Library",
        enabled=False,
        read_only=False,
    )
    assert mounted_again["id"] == mounted["id"]
    assert mounted_again["label"] == "Characters Library"
    assert mounted_again["enabled"] is False
    assert mounted_again["read_only"] is False

    mounts = service.list_mounted_libraries(project_path)
    assert len(mounts) == 1
    assert mounts[0]["id"] == mounted["id"]

    mounts_after_remove = service.remove_mounted_library(project_path, mount_id=mounted["id"])
    assert mounts_after_remove == []


def test_project_storage_normalizes_non_canonical_mounted_libraries_payload(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_mounts_non_canonical"
    service.create_project(project_path, "Project Mounts Non Canonical")

    a = (tmp_path / "LIBRARIES" / "USER" / "A").resolve()
    b = (tmp_path / "LIBRARIES" / "USER" / "B").resolve()
    a.mkdir(parents=True, exist_ok=True)
    b.mkdir(parents=True, exist_ok=True)

    metadata = service.load_project_metadata(project_path)
    metadata["mounted_libraries"] = [
        {"path": str(a), "enabled": "false", "read_only": "true"},
        {"path": str(a), "enabled": True, "read_only": False},
        {"path": str(b), "id": "mount_b", "label": "B"},
        {"foo": "invalid"},
    ]
    service.save_project_metadata(project_path, metadata)

    mounts = service.list_mounted_libraries(project_path)
    assert len(mounts) == 2

    first = mounts[0]
    assert first["path"] == a.as_posix()
    assert first["enabled"] is False
    assert first["read_only"] is True
    assert first["kind"] == "LIB"
    assert first["id"]

    second = mounts[1]
    assert second["id"] == "mount_b"
    assert second["path"] == b.as_posix()
    assert second["label"] == "B"
