import json
from collections import defaultdict
from pathlib import Path

from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree
from infrastructure.storage import ProjectStorageService


def _sample_blocks() -> list[Block]:
    container = Block(
        id="blk_container",
        type=BlockType.CONTAINER,
        profile="container",
        name="Root",
        tree=FreeTree(),
        graph=FreeGraph(),
    )
    text = Block(
        id="blk_text",
        type=BlockType.TEXT,
        profile="note",
        name="Note A",
        content={"text": "hello"},
    )
    file_like = Block(
        id="blk_file",
        type=BlockType.IMAGE,
        profile="asset",
        name="Reference",
        content={"storage_path": "storage/files/ref.png", "mime_type": "image/png"},
    )
    return [container, text, file_like]


def test_create_project_creates_folder_structure(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"

    service.create_project(project_path, "My Project")

    assert project_path.exists()
    assert (project_path / "storage" / "files").exists()
    assert (project_path / "storage" / "thumbs").exists()
    assert (project_path / "cache" / "previews").exists()


def test_create_project_creates_required_json_files(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"

    service.create_project(project_path, "My Project")

    assert (project_path / "project.json").exists()
    assert (project_path / "workspaces").exists()
    assert (project_path / "ui_state.json").exists()

    metadata = json.loads((project_path / "project.json").read_text(encoding="utf-8"))
    assert metadata["name"] == "My Project"
    assert metadata["version"] == 1
    assert metadata["kind"] == "project"
    assert metadata["storage_layout_version"] == 2
    assert "created_at" in metadata
    assert "updated_at" in metadata
    assert "author_email" in metadata
    assert "description" in metadata
    assert list((project_path / "workspaces").glob("*/blocks.json")) == []
    assert json.loads((project_path / "ui_state.json").read_text(encoding="utf-8")) == {}


def test_save_blocks_writes_valid_json(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    blocks = _sample_blocks()
    service.save_blocks(project_path, blocks)

    payload = json.loads((project_path / "workspaces" / "default" / "blocks.json").read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) == 3
    assert payload[0]["id"] == "blk_container"
    assert payload[1]["type"] == "text"


def test_load_blocks_restores_blocks_correctly(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    service.save_blocks(project_path, _sample_blocks())
    loaded = service.load_blocks(project_path)

    assert len(loaded) == 3
    assert loaded[0].type is BlockType.CONTAINER
    assert loaded[0].tree is not None
    assert loaded[0].graph is not None
    assert loaded[1].type is BlockType.TEXT
    assert loaded[1].content["text"] == "hello"
    assert loaded[2].content["storage_path"] == "storage/files/ref.png"


def test_import_file_copies_file_into_storage_files(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    source_file = tmp_path / "caroline_ref.png"
    source_file.write_bytes(b"pngdata")

    file_meta = service.import_file(project_path, source_file)
    target = service.resolve_path(project_path, file_meta["storage_path"])

    assert target.exists()
    assert target.read_bytes() == b"pngdata"


def test_import_file_returns_relative_storage_metadata(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    source_file = tmp_path / "caroline_ref.png"
    source_file.write_bytes(b"pngdata")

    file_meta = service.import_file(project_path, source_file)

    assert file_meta["storage_path"].startswith("storage/files/")
    assert file_meta["original_name"] == "caroline_ref.png"
    assert file_meta["mime_type"] == "image/png"


def test_import_file_normalizes_video_to_mp4_when_available(tmp_path: Path, monkeypatch) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    source_file = tmp_path / "ai_video.mov"
    source_file.write_bytes(b"raw-video")

    def _fake_normalize(self, source: Path, target: Path) -> bool:
        target.write_bytes(b"normalized-video")
        return True

    monkeypatch.setattr(ProjectStorageService, "_normalize_video_for_ui", _fake_normalize)

    file_meta = service.import_file(project_path, source_file)
    target = service.resolve_path(project_path, file_meta["storage_path"])

    assert file_meta["storage_path"].startswith("storage/files/")
    assert file_meta["storage_path"].endswith(".mp4")
    assert file_meta["original_name"] == "ai_video.mov"
    assert file_meta["mime_type"] == "video/mp4"
    assert target.exists()
    assert target.read_bytes() == b"normalized-video"


def test_import_file_keeps_original_when_video_normalization_fails(tmp_path: Path, monkeypatch) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    source_file = tmp_path / "ai_video.mp4"
    source_file.write_bytes(b"raw-video")

    def _fake_normalize_fail(self, source: Path, target: Path) -> bool:
        return False

    monkeypatch.setattr(ProjectStorageService, "_normalize_video_for_ui", _fake_normalize_fail)

    file_meta = service.import_file(project_path, source_file)
    target = service.resolve_path(project_path, file_meta["storage_path"])

    assert file_meta["storage_path"].startswith("storage/files/")
    assert file_meta["storage_path"].endswith(".mp4")
    assert file_meta["original_name"] == "ai_video.mp4"
    assert target.exists()
    assert target.read_bytes() == b"raw-video"


def test_resolve_path_returns_absolute_path(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    resolved = service.resolve_path(project_path, "storage/files/a.png")
    assert resolved == (project_path / "storage" / "files" / "a.png").resolve()


def test_importing_same_filename_twice_generates_unique_names(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_path = tmp_path / "project_a"
    service.create_project(project_path, "My Project")

    source_file = tmp_path / "same_name.txt"
    source_file.write_text("first", encoding="utf-8")
    file_meta_1 = service.import_file(project_path, source_file)

    source_file.write_text("second", encoding="utf-8")
    file_meta_2 = service.import_file(project_path, source_file)

    assert file_meta_1["storage_path"] != file_meta_2["storage_path"]
    assert service.resolve_path(project_path, file_meta_1["storage_path"]).exists()
    assert service.resolve_path(project_path, file_meta_2["storage_path"]).exists()


def test_create_project_file_with_three_domains_and_content_blocks(tmp_path: Path) -> None:
    service = ProjectStorageService()
    project_name = "Creative Project"
    project_path = tmp_path / "DataProject" / f"{project_name}.sbc"
    service.create_project(project_path, project_name)

    domain_specs = [
        ("characters", BlockDomain.CHARACTERS, "Caractere"),
        ("story", BlockDomain.STORY, "Story"),
        ("location", BlockDomain.LOCATION, "Location"),
    ]

    blocks: list[Block] = []
    for key, domain, label in domain_specs:
        root_id = f"{key}_root"
        container_id = f"{key}_container"
        image_id = f"{key}_image"
        video_id = f"{key}_video"
        text_id = f"{key}_text"

        root = Block(
            id=root_id,
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name=label,
            domain=domain,
            contains=[container_id],
            tree=FreeTree(),
            graph=FreeGraph(),
        )
        container = Block(
            id=container_id,
            type=BlockType.CONTAINER,
            profile="container",
            name=f"{label} Container",
            domain=domain,
            contains=[image_id, video_id, text_id],
            tree=FreeTree(),
            graph=FreeGraph(),
        )
        image = Block(
            id=image_id,
            type=BlockType.IMAGE,
            profile="asset",
            name=f"{label} Image",
            domain=domain,
            content={"storage_path": f"storage/files/{key}_image.png"},
        )
        video = Block(
            id=video_id,
            type=BlockType.VIDEO,
            profile="asset",
            name=f"{label} Video",
            domain=domain,
            content={"storage_path": f"storage/files/{key}_video.mp4"},
        )
        text = Block(
            id=text_id,
            type=BlockType.TEXT,
            profile="note",
            name=f"{label} Text",
            domain=domain,
            content={"text": f"Notes for {label}"},
        )

        blocks.extend([root, container, image, video, text])

    service.save_blocks(project_path, blocks)
    raw_payload_size = 0
    for blocks_file in (project_path / "workspaces").glob("*/blocks.json"):
        payload = json.loads(blocks_file.read_text(encoding="utf-8"))
        raw_payload_size += len(payload)
    assert raw_payload_size == 15

    loaded_blocks = service.load_blocks(project_path)
    assert len(loaded_blocks) == 15

    by_domain_and_type: dict[BlockDomain, set[BlockType]] = defaultdict(set)
    for block in loaded_blocks:
        by_domain_and_type[block.domain].add(block.type)

    assert by_domain_and_type[BlockDomain.CHARACTERS] >= {
        BlockType.CONTAINER,
        BlockType.IMAGE,
        BlockType.VIDEO,
        BlockType.TEXT,
    }
    assert by_domain_and_type[BlockDomain.STORY] >= {
        BlockType.CONTAINER,
        BlockType.IMAGE,
        BlockType.VIDEO,
        BlockType.TEXT,
    }
    assert by_domain_and_type[BlockDomain.LOCATION] >= {
        BlockType.CONTAINER,
        BlockType.IMAGE,
        BlockType.VIDEO,
        BlockType.TEXT,
    }

