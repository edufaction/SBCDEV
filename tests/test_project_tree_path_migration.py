import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from domain import Block, BlockType
from infrastructure.storage import ProjectStorageService
from UI.windows.main_window import MainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_legacy_tree_payload_parser_keeps_only_real_roots() -> None:
    payload = {
        "root_ids": ["node_folder_1", "node_block_1"],
        "nodes": {
            "node_folder_1": {
                "id": "node_folder_1",
                "kind": "folder",
                "name": "Folder",
                "block_id": None,
                "children": ["node_block_1"],
            },
            "node_block_1": {
                "id": "node_block_1",
                "kind": "block_ref",
                "name": "Image",
                "block_id": "img_1",
                "children": [],
            },
        },
    }

    tree = MainWindow._legacy_tree_from_payload(payload)
    assert tree is not None
    assert tree.root_ids == ["node_folder_1"]


def test_open_project_migrates_legacy_project_tree_to_container_paths(tmp_path: Path) -> None:
    app = _app()
    storage = ProjectStorageService()
    project_path = tmp_path / "project_tree_path_migration"
    storage.create_project(project_path, "Project Tree Path Migration")
    storage.save_blocks(
        project_path,
        [
            Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container", contains=["img_1"]),
            Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
        ],
    )
    storage.save_ui_state(
        project_path,
        {
            "project_free_tree": {
                "root_ids": ["node_container_cnt_1"],
                "nodes": {
                    "node_container_cnt_1": {
                        "id": "node_container_cnt_1",
                        "kind": "folder",
                        "name": "Container",
                        "block_id": "cnt_1",
                        "children": ["node_folder_user_1"],
                    },
                    "node_folder_user_1": {
                        "id": "node_folder_user_1",
                        "kind": "folder",
                        "name": "Principaux",
                        "block_id": None,
                        "children": ["node_folder_user_2"],
                    },
                    "node_folder_user_2": {
                        "id": "node_folder_user_2",
                        "kind": "folder",
                        "name": "Heros",
                        "block_id": None,
                        "children": ["node_block_img_1"],
                    },
                    "node_block_img_1": {
                        "id": "node_block_img_1",
                        "kind": "block_ref",
                        "name": "Image 1",
                        "block_id": "img_1",
                        "children": [],
                    },
                },
            }
        },
    )

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    blocks = storage.load_blocks(project_path)
    image = next(block for block in blocks if block.id == "img_1")
    assert image.container_paths.get("cnt_1") == "Principaux/Heros"

    ui_state = storage.load_ui_state(project_path)
    assert "project_free_tree" not in ui_state
