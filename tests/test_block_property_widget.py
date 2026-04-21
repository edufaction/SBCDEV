import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from domain import Block, BlockDomain, BlockType, FreeGraph, FreeGraphNode
from infrastructure.storage import ProjectStorageService
from UI.Widgets import BlockPropertyWidget
from UI.windows.free_tree_window import FreeTreeWindow
from UI.windows.main_window import MainWindow
from UI.windows.thumbnail_list_window import ThumbnailListWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _set_property_value(widget: BlockPropertyWidget, key: str, value: str) -> None:
    item = widget._editor._items_by_key[key]
    item.setText(value)


def test_block_property_widget_emits_property_change_requested_for_editable_field() -> None:
    app = _app()
    block = Block(id="blk_note", type=BlockType.TEXT, profile="note", name="Old Name")
    widget = BlockPropertyWidget()
    captured: list[dict] = []
    widget.property_change_requested.connect(captured.append)

    widget.set_block(block)
    _set_property_value(widget, "name", "New Name")
    app.processEvents()

    assert captured == [{"block_id": "blk_note", "name": "New Name"}]
    assert widget.current_block_id() == "blk_note"


def test_block_property_widget_emits_text_content_change_for_note_blocks() -> None:
    app = _app()
    block = Block(id="blk_note", type=BlockType.TEXT, profile="note", name="Note", content={"text": "Old body"})
    widget = BlockPropertyWidget()
    captured: list[dict] = []
    widget.property_change_requested.connect(captured.append)

    widget.set_block(block)
    _set_property_value(widget, "text_content", "Updated body")
    app.processEvents()

    assert captured == [{"block_id": "blk_note", "text_content": "Updated body"}]


def test_block_property_widget_uses_group_icons_and_distinct_value_styles() -> None:
    app = _app()
    block = Block(id="blk_note", type=BlockType.TEXT, profile="note", name="Old Name")
    widget = BlockPropertyWidget()
    widget.set_block(block)
    app.processEvents()

    model = widget._editor._model
    general_group_item = model.item(0, 0)
    assert general_group_item is not None
    assert not general_group_item.icon().isNull()
    icon_pixmap = general_group_item.icon().pixmap(16, 16)
    icon_image = icon_pixmap.toImage()
    sampled = None
    for y in range(icon_image.height()):
        for x in range(icon_image.width()):
            color = icon_image.pixelColor(x, y)
            if color.alpha() > 0:
                sampled = color
                break
        if sampled is not None:
            break
    assert sampled is not None
    expected = widget._editor._theme_tokens["on_surface_variant"]
    expected_color = type(sampled)(expected)
    assert abs(sampled.red() - expected_color.red()) <= 2
    assert abs(sampled.green() - expected_color.green()) <= 2
    assert abs(sampled.blue() - expected_color.blue()) <= 2

    editable_item = widget._editor._items_by_key["name"]
    readonly_item = widget._editor._items_by_key["id"]

    assert editable_item.foreground().color() != readonly_item.foreground().color()
    assert readonly_item.font().fixedPitch() is True


def test_block_property_widget_delegate_gives_editable_values_enough_height() -> None:
    app = _app()
    block = Block(id="blk_note", type=BlockType.TEXT, profile="note", name="Old Name")
    widget = BlockPropertyWidget()
    widget.set_block(block)
    widget.show()
    app.processEvents()

    name_item = widget._editor._items_by_key["name"]
    name_index = name_item.index()
    option = QStyleOptionViewItem()
    option.rect = widget._editor._tree_view.visualRect(name_index)
    delegate = widget._editor._tree_view.itemDelegateForColumn(1)
    size_hint = delegate.sizeHint(option, name_index)

    assert size_hint.height() >= 34


def test_thumbnail_list_window_property_edit_updates_blocks_and_preserves_selection() -> None:
    app = _app()
    blocks = [
        Block(id="img_a", type=BlockType.IMAGE, profile="asset", name="Image A", tags=["hero"]),
        Block(id="img_b", type=BlockType.IMAGE, profile="asset", name="Image B", tags=["night"]),
    ]
    window = ThumbnailListWindow(blocks=blocks, project_root=None)
    emitted: list[list[Block]] = []
    window.blocks_changed.connect(emitted.append)

    window._on_block_selected(blocks[0])
    _set_property_value(window._property_widget, "name", "Updated A")
    app.processEvents()

    assert blocks[0].name == "Updated A"
    assert emitted
    assert any(block.id == "img_a" and block.name == "Updated A" for block in emitted[-1])
    assert window._property_widget.current_block_id() == "img_a"


def test_free_tree_window_property_edit_updates_blocks_and_emits_blocks_changed() -> None:
    app = _app()
    container = Block(
        id="cnt_assets",
        type=BlockType.CONTAINER,
        profile="container",
        name="Assets",
        domain=BlockDomain.LIB,
        contains=["img_a"],
    )
    block = Block(
        id="img_a",
        type=BlockType.IMAGE,
        profile="asset",
        name="Image A",
        domain=BlockDomain.LIB,
        container_paths={"cnt_assets": ""},
    )
    window = FreeTreeWindow(blocks=[container, block], project_root=None)
    emitted: list[list[Block]] = []
    window.blocks_changed.connect(emitted.append)

    window._property_widget.set_block(block, container_id="cnt_assets")
    _set_property_value(window._property_widget, "name", "Updated Image A")
    app.processEvents()

    assert block.name == "Updated Image A"
    assert emitted
    assert any(candidate.id == "img_a" and candidate.name == "Updated Image A" for candidate in emitted[-1])
    assert window._property_widget.current_block_id() == "img_a"


def test_main_window_character_block_property_update_persists_and_preserves_selection(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_props.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Props")

    characters_root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters",
        domain=BlockDomain.CHARACTERS,
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Alice",
        domain=BlockDomain.CHARACTERS,
        container_paths={"blk_characters_root": ""},
    )
    storage.save_blocks(project_path, [characters_root, character])

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    assert window._character_workspace_panel.select_block("char_1") is True
    app.processEvents()
    assert window._character_workspace_panel.current_block_id() == "char_1"

    window._character_workspace_panel.block_update_requested.emit({"block_id": "char_1", "name": "Alice Updated"})
    app.processEvents()

    persisted_blocks = storage.load_blocks(project_path)
    updated_character = next(block for block in persisted_blocks if block.id == "char_1")
    assert updated_character.name == "Alice Updated"
    assert window._character_workspace_panel.current_block_id() == "char_1"


def test_main_window_creates_postit_note_in_story_container_and_selects_it(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_notes.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Notes")

    story_root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story",
        domain=BlockDomain.STORY,
        contains=["shot_1"],
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
    storage.save_blocks(project_path, [story_root, shot])

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    window._story_workspace_controller.create_note("shot_1")
    app.processEvents()

    persisted_blocks = storage.load_blocks(project_path)
    note_blocks = [block for block in persisted_blocks if block.type == BlockType.TEXT and block.profile == "note"]
    assert len(note_blocks) == 1
    note = note_blocks[0]
    updated_shot = next(block for block in persisted_blocks if block.id == "shot_1")

    assert note.id in updated_shot.contains
    assert note.content["note_style"] == "postit"
    assert note.content["text"] == ""
    assert note.container_paths["shot_1"] == ""
    assert window._story_workspace_panel.current_block_id() == note.id


def test_main_window_creates_placeholder_block_in_character_form(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_placeholders.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Placeholders")

    characters_root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters",
        domain=BlockDomain.CHARACTERS,
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Alice",
        domain=BlockDomain.CHARACTERS,
        contains=["form_1"],
        container_paths={"blk_characters_root": ""},
    )
    form = Block(
        id="form_1",
        type=BlockType.CONTAINER,
        profile="character_form",
        name="Main Form",
        domain=BlockDomain.CHARACTERS,
        container_paths={"char_1": ""},
    )
    storage.save_blocks(project_path, [characters_root, character, form])

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    window._character_workspace_controller.create_placeholder("form_1")
    app.processEvents()

    persisted_blocks = storage.load_blocks(project_path)
    placeholders = [block for block in persisted_blocks if block.type == BlockType.EMPTY and block.profile == "placeholder"]
    assert len(placeholders) == 1
    placeholder = placeholders[0]
    updated_form = next(block for block in persisted_blocks if block.id == "form_1")

    assert placeholder.id in updated_form.contains
    assert placeholder.container_paths["form_1"] == ""
    assert placeholder.content["placeholder"] is True
    assert window._character_workspace_panel.current_block_id() == placeholder.id


def test_main_window_imports_file_into_character_form(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_imports.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Imports")

    characters_root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters",
        domain=BlockDomain.CHARACTERS,
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Alice",
        domain=BlockDomain.CHARACTERS,
        contains=["form_1"],
        container_paths={"blk_characters_root": ""},
    )
    form = Block(
        id="form_1",
        type=BlockType.CONTAINER,
        profile="character_form",
        name="Main Form",
        domain=BlockDomain.CHARACTERS,
        container_paths={"char_1": ""},
    )
    storage.save_blocks(project_path, [characters_root, character, form])

    source_file = tmp_path / "pose.png"
    source_file.write_bytes(b"fake-png-content")

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    window._character_workspace_controller.import_blocks("form_1", [str(source_file)])
    app.processEvents()

    persisted_blocks = storage.load_blocks(project_path)
    imported_assets = [block for block in persisted_blocks if block.type == BlockType.IMAGE and block.profile == "asset"]
    assert len(imported_assets) == 1
    imported = imported_assets[0]
    updated_form = next(block for block in persisted_blocks if block.id == "form_1")

    assert imported.id in updated_form.contains
    assert imported.container_paths["form_1"] == ""
    assert imported.content["storage_path"].startswith("storage/files/")
    assert window._character_workspace_panel.current_block_id() == imported.id


def test_main_window_graph_drop_replaces_placeholder_with_imported_asset(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_drop_replace.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Drop Replace")

    characters_root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters",
        domain=BlockDomain.CHARACTERS,
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Alice",
        domain=BlockDomain.CHARACTERS,
        contains=["form_1"],
        container_paths={"blk_characters_root": ""},
    )
    placeholder = Block(
        id="slot_front",
        type=BlockType.EMPTY,
        profile="template_slot",
        name="Front View",
        domain=BlockDomain.CHARACTERS,
        container_paths={"form_1": ""},
        content={"template_slot": True, "expected_types": ["image"]},
    )
    form = Block(
        id="form_1",
        type=BlockType.CONTAINER,
        profile="character_form",
        name="Main Form",
        domain=BlockDomain.CHARACTERS,
        contains=[placeholder.id],
        container_paths={"char_1": ""},
        graph=FreeGraph(
            nodes={
                "n1": FreeGraphNode(id="n1", block_id=placeholder.id, x=48.0, y=84.0),
            }
        ),
    )
    storage.save_blocks(project_path, [characters_root, character, form, placeholder])

    source_file = tmp_path / "front.png"
    source_file.write_bytes(b"fake-png-content")

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    window._on_graph_files_drop_requested("form_1", "slot_front", [str(source_file)], 260.0, 310.0)
    app.processEvents()

    persisted_blocks = storage.load_blocks(project_path)
    replaced = next(block for block in persisted_blocks if block.id == "slot_front")
    updated_form = next(block for block in persisted_blocks if block.id == "form_1")
    node = updated_form.graph.nodes["n1"]

    assert replaced.type == BlockType.IMAGE
    assert replaced.profile == "asset"
    assert replaced.container_paths["form_1"] == ""
    assert replaced.content["storage_path"].startswith("storage/files/")
    assert replaced.id in updated_form.contains
    assert node.block_id == replaced.id
    assert node.x == 48.0
    assert node.y == 84.0
    assert window._character_workspace_panel.current_block_id() == replaced.id


def test_main_window_graph_drop_creates_imported_block_and_positions_it(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_drop_create.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Drop Create")

    characters_root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters",
        domain=BlockDomain.CHARACTERS,
        contains=["char_1"],
        content={"workspace_role": "characters_root"},
    )
    character = Block(
        id="char_1",
        type=BlockType.CONTAINER,
        profile="character",
        name="Alice",
        domain=BlockDomain.CHARACTERS,
        contains=["form_1"],
        container_paths={"blk_characters_root": ""},
    )
    form = Block(
        id="form_1",
        type=BlockType.CONTAINER,
        profile="character_form",
        name="Main Form",
        domain=BlockDomain.CHARACTERS,
        container_paths={"char_1": ""},
        graph=FreeGraph(),
    )
    storage.save_blocks(project_path, [characters_root, character, form])

    source_file = tmp_path / "pose.png"
    source_file.write_bytes(b"fake-png-content")

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    window._on_graph_files_drop_requested("form_1", "", [str(source_file)], 222.0, 333.0)
    app.processEvents()

    persisted_blocks = storage.load_blocks(project_path)
    imported = next(
        block for block in persisted_blocks if block.type == BlockType.IMAGE and block.profile == "asset"
    )
    updated_form = next(block for block in persisted_blocks if block.id == "form_1")
    node = next(item for item in updated_form.graph.nodes.values() if item.block_id == imported.id)

    assert imported.id in updated_form.contains
    assert imported.container_paths["form_1"] == ""
    assert imported.content["storage_path"].startswith("storage/files/")
    assert node.x == 222.0
    assert node.y == 333.0
    assert window._character_workspace_panel.current_block_id() == imported.id
