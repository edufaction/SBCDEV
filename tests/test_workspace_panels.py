import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from domain import Block, BlockType
from infrastructure.storage import LibraryStorageService, ProjectStorageService
from UI.Frames import CharacterWorkspacePanel, LibraryWorkspacePanel, StoryWorkspacePanel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_character_workspace_panel_emits_create_request(monkeypatch) -> None:
    app = _app()
    panel = CharacterWorkspacePanel()
    panel.show()
    app.processEvents()

    monkeypatch.setattr(
        "UI.Frames.workspaces.character_workspace_panel.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Nova", True),
    )

    received: list[str] = []
    panel.character_create_requested.connect(received.append)

    QTest.mouseClick(panel._create_character_button, Qt.LeftButton)
    app.processEvents()

    assert received == ["Nova"]


def test_character_workspace_panel_emits_update_request_for_selected_character() -> None:
    app = _app()
    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Ariane",
        contains=["form_1"],
        tags=["character", "hero"],
    )
    form = Block(id="form_1", type=BlockType.CONTAINER, profile="character_form", name="Sheet")

    panel = CharacterWorkspacePanel()
    panel.set_blocks([root, character, form], project_root=None)
    panel.show()
    app.processEvents()

    received: list[dict] = []
    panel.character_update_requested.connect(received.append)

    panel._on_tree_block_selected(form, character.id)
    panel._character_name_edit.setText("Nova")
    panel._character_tags_edit.setText("character, lead")
    QTest.mouseClick(panel._save_character_button, Qt.LeftButton)
    app.processEvents()

    assert len(received) == 1
    assert received[0]["character_id"] == "char_1"
    assert received[0]["name"] == "Nova"
    assert received[0]["tags"] == ["character", "lead"]


def test_character_workspace_panel_keeps_parent_free_tree_context_for_container_path_edit() -> None:
    app = _app()
    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Ariane",
        container_paths={"blk_characters_root": "Principaux"},
    )

    panel = CharacterWorkspacePanel()
    panel.set_blocks([root, character], project_root=None)
    panel.show()
    app.processEvents()

    panel._on_tree_block_selected(character, root.id)
    app.processEvents()
    assert panel.current_property_container_id() == "blk_characters_root"

    panel._on_graph_node_selected(character.id)
    app.processEvents()
    assert panel.current_property_container_id() == "blk_characters_root"

    received: list[tuple[str, str, str]] = []
    panel.relative_path_changed.connect(lambda block_id, container_id, relative_path: received.append((block_id, container_id, relative_path)))

    path_item = panel._property_widget._editor._items_by_key["container_path"]
    path_item.setText("Principaux/Heroine")
    app.processEvents()

    assert received == [("char_1", "blk_characters_root", "Principaux/Heroine")]


def test_character_workspace_panel_graph_inspection_does_not_change_tree_selection() -> None:
    app = _app()
    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Ariane",
        contains=["form_1"],
        container_paths={"blk_characters_root": ""},
    )
    form = Block(id="form_1", type=BlockType.CONTAINER, profile="character_form", name="Sheet")

    panel = CharacterWorkspacePanel()
    panel.set_blocks([root, character, form], project_root=None)
    panel.show()
    app.processEvents()

    assert panel.select_tree_block("char_1") is True
    app.processEvents()
    assert panel.current_tree_block_id() == "char_1"

    assert panel.inspect_block("form_1", container_id="char_1") is True
    app.processEvents()

    assert panel.current_tree_block_id() == "char_1"
    assert panel.current_block_id() == "form_1"


def test_story_workspace_panel_graph_inspection_does_not_change_tree_selection() -> None:
    app = _app()
    root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story Root",
        contains=["shot_1"],
        content={"workspace_role": "story_root"},
    )
    shot = Block(
        id="shot_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        contains=["note_1"],
        container_paths={"blk_story_root": ""},
    )
    note = Block(id="note_1", type=BlockType.TEXT, profile="note", name="Note 1", container_paths={"shot_1": ""})

    panel = StoryWorkspacePanel()
    panel.set_blocks([root, shot, note], project_root=None)
    panel.show()
    app.processEvents()

    assert panel.select_tree_block("shot_1") is True
    app.processEvents()
    assert panel.current_tree_block_id() == "shot_1"

    assert panel.inspect_block("note_1", container_id="shot_1") is True
    app.processEvents()

    assert panel.current_tree_block_id() == "shot_1"
    assert panel.current_block_id() == "note_1"


def test_library_workspace_panel_discovers_mounts_and_loads_blocks(tmp_path: Path) -> None:
    app = _app()
    project_path = tmp_path / "project"
    user_root = tmp_path / "LIBRARIES" / "USER"
    app_root = tmp_path / "LIBRARIES" / "APPLICATION"
    ProjectStorageService().create_project(project_path, "Demo")

    library_path = user_root / "CharactersLib"
    storage = LibraryStorageService()
    storage.create_library(library_path, "CharactersLib")
    storage.save_blocks(
        library_path,
        [Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image One")],
    )

    panel = LibraryWorkspacePanel()
    panel.set_context(
        project_root=project_path,
        user_libraries_root=user_root,
        application_libraries_root=app_root,
    )
    panel.show()
    app.processEvents()

    assert panel._library_list.count() == 1
    assert [block.id for block in panel._asset_grid._blocks] == ["img_1"]
    assert panel._mount_button.isEnabled() is True

    QTest.mouseClick(panel._mount_button, Qt.LeftButton)
    app.processEvents()
    mounts = ProjectStorageService().list_mounted_libraries(project_path)
    assert len(mounts) == 1
    assert mounts[0]["path"] == str(library_path.resolve())
    assert panel._unmount_button.isEnabled() is True

    QTest.mouseClick(panel._unmount_button, Qt.LeftButton)
    app.processEvents()
    assert ProjectStorageService().list_mounted_libraries(project_path) == []
