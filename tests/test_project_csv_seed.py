import json
from pathlib import Path

from domain import BlockType
from infrastructure.storage import ProjectStorageService, ensure_test_project_from_data_dir, seed_project_from_csv


def _write_minimal_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "Tree,container,id,type,domain,profile,name,shared,description,tags,content_json,contains_ids,input_links",
                "Root,,blk_root,container,lib,workspace_root,Root,false,Root node,root|lib,{},blk_img,",
                'Root/Images,blk_root,blk_img,image,lib,asset,Ref,true,Image ref,asset|image,"{""storage_path"": ""storage/files/ref.png""}",,',
            ]
        ),
        encoding="utf-8",
    )


def test_seed_project_from_csv_creates_blocks_and_copies_assets(tmp_path: Path) -> None:
    data_dir = tmp_path / "DataProject"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "example_project_blocks.csv"
    _write_minimal_csv(csv_path)

    source_project = data_dir / "PROJET"
    source_files = source_project / "storage" / "files"
    source_files.mkdir(parents=True, exist_ok=True)
    (source_files / "ref.png").write_bytes(b"pngdata")

    project_path = data_dir / "TESTPROJ"
    blocks = seed_project_from_csv(
        project_path=project_path,
        project_name="TESTPROJ",
        csv_path=csv_path,
        assets_source_project_path=source_project,
    )

    assert len(blocks) == 2
    assert blocks[0].type is BlockType.CONTAINER
    assert blocks[1].content["storage_path"] == "storage/files/ref.png"
    assert (project_path / "storage" / "files" / "ref.png").exists()

    payload_size = 0
    for blocks_file in (project_path / "workspaces").glob("*/blocks.json"):
        payload_size += len(json.loads(blocks_file.read_text(encoding="utf-8")))
    assert payload_size == 2


def test_ensure_test_project_from_data_dir_uses_existing_project_assets_folder(tmp_path: Path) -> None:
    data_dir = tmp_path / "DataProject"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "example_project_blocks.csv"
    _write_minimal_csv(csv_path)

    source_project = data_dir / "project"
    source_files = source_project / "storage" / "files"
    source_files.mkdir(parents=True, exist_ok=True)
    (source_files / "ref.png").write_bytes(b"pngdata")

    project_path = ensure_test_project_from_data_dir(data_dir, project_name="TESTPROJ")
    loaded = ProjectStorageService().load_blocks(project_path)

    assert project_path == (data_dir / "TESTPROJ")
    assert len(loaded) == 2
    assert (project_path / "storage" / "files" / "ref.png").exists()
