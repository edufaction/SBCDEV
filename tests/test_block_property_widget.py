import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from domain import Block, BlockDomain, BlockType
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
