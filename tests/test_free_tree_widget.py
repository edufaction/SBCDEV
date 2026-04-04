import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from domain import Block, BlockAccessMode, BlockProvenanceKind, BlockType
from infrastructure.storage import ProjectStorageService
from UI.Widgets import FreeTreeWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _select_node(widget: FreeTreeWidget, node_id: str) -> bool:
    items = widget._tree_view.findItems("", Qt.MatchContains | Qt.MatchRecursive, 0)
    for item in items:
        if str(item.data(0, Qt.UserRole + 300) or "") == node_id:
            widget._tree_view.setCurrentItem(item)
            return True
    return False


def test_free_tree_widget_displays_project_blocks() -> None:
    _ = _app()
    blocks = [
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
        Block(id="txt_1", type=BlockType.TEXT, profile="note", name="Note 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    assert widget._tree_view.topLevelItemCount() == 2
    assert widget.find_node_id_for_block("img_1") is not None
    assert widget.find_node_id_for_block("txt_1") is not None


def test_remove_folder_preserves_block_nodes() -> None:
    _ = _app()
    blocks = [
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
        Block(id="txt_1", type=BlockType.TEXT, profile="note", name="Note 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    image_node = widget.find_node_id_for_block("img_1")
    text_node = widget.find_node_id_for_block("txt_1")
    assert image_node is not None
    assert text_node is not None

    folder_id = widget.add_folder("Folder A")
    assert folder_id is not None

    widget.move_node(image_node, folder_id)
    assert image_node in widget._tree.nodes[folder_id].children

    widget.remove_folder(folder_id)
    assert folder_id not in widget._tree.nodes
    assert image_node in widget._tree.root_ids
    assert text_node in widget._tree.root_ids


def test_selecting_block_emits_container_context() -> None:
    app = _app()
    blocks = [
        Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container", contains=["img_1"]),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    captured: list[tuple[str | None, str]] = []
    widget.block_selected.connect(lambda block, container_id: captured.append((getattr(block, "id", None), container_id)))

    image_node_id = widget.find_node_id_for_block("img_1")
    assert image_node_id is not None
    assert _select_node(widget, image_node_id)
    app.processEvents()

    assert captured
    assert captured[-1] == ("img_1", "cnt_1")


def test_set_block_relative_path_updates_path_and_tree_hierarchy() -> None:
    _ = _app()
    blocks = [
        Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container", contains=["img_1"]),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    changed = widget.set_block_relative_path("img_1", "cnt_1", "Principaux/Heros")
    assert changed is True

    image_block = widget._blocks_by_id["img_1"]
    assert image_block.container_paths.get("cnt_1") == "Principaux/Heros"

    image_node_id = widget.find_node_id_for_block("img_1")
    assert image_node_id is not None
    parent_id = widget._controller.find_parent_id(image_node_id)
    assert parent_id is not None
    assert widget._tree.nodes[parent_id].name == "Heros"
    grand_parent_id = widget._controller.find_parent_id(parent_id)
    assert grand_parent_id is not None
    assert widget._tree.nodes[grand_parent_id].name == "Principaux"


def test_container_block_is_rendered_as_locked_folder_with_contains() -> None:
    _ = _app()
    blocks = [
        Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container A", contains=["img_1", "txt_1"]),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
        Block(id="txt_1", type=BlockType.TEXT, profile="note", name="Note 1"),
        Block(id="aud_1", type=BlockType.AUDIO, profile="voice", name="Audio 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    container_node_ids = [
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "cnt_1"
    ]
    assert len(container_node_ids) == 1
    container_node_id = container_node_ids[0]
    assert container_node_id in widget._locked_node_ids

    container_node = widget._tree.nodes[container_node_id]
    child_block_ids = {widget._tree.nodes[child_id].block_id for child_id in container_node.children}
    assert child_block_ids == {"img_1", "txt_1"}
    assert all(child_id not in widget._locked_node_ids for child_id in container_node.children)

    # Elements listed inside the container are not duplicated at root.
    root_block_ids = {
        widget._tree.nodes[node_id].block_id
        for node_id in widget._tree.root_ids
        if widget._tree.nodes[node_id].kind == "block_ref"
    }
    assert "img_1" not in root_block_ids
    assert "txt_1" not in root_block_ids
    assert "aud_1" in root_block_ids


def test_locked_container_folder_cannot_be_removed() -> None:
    _ = _app()
    blocks = [
        Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container A", contains=["img_1"]),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    container_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "cnt_1"
    )
    child_ids_before = list(widget._tree.nodes[container_node_id].children)
    widget.remove_folder(container_node_id)

    assert container_node_id in widget._tree.nodes
    assert widget._tree.nodes[container_node_id].children == child_ids_before


def test_folder_color_is_primary_only_for_user_folders() -> None:
    _ = _app()
    blocks = [
        Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container A", contains=["img_1"]),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)
    user_folder_id = widget.add_folder("User Folder")
    assert user_folder_id is not None

    container_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "cnt_1"
    )
    user_folder_node = widget._tree.nodes[user_folder_id]
    container_folder_node = widget._tree.nodes[container_node_id]

    assert widget._folder_icon_color(user_folder_node) == widget._primary_color()
    assert widget._folder_icon_color(container_folder_node) == widget._on_surface_color()


def test_external_thumbnail_drop_creates_new_block_inside_target_container() -> None:
    _ = _app()
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", content={"storage_path": "a.png"}),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    virtual_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "blk_internal_lib_root"
    )

    before_count = len(widget._blocks)
    widget._handle_external_block_drop(["img_1"], virtual_node_id)

    assert len(widget._blocks) == before_count + 1
    created_blocks = [block for block in widget._blocks if block.id not in {"blk_internal_lib_root", "blk_internal_lib_empty", "img_1"}]
    assert len(created_blocks) == 1
    created = created_blocks[0]
    assert created.type == BlockType.IMAGE
    assert created.id in widget._blocks_by_id["blk_internal_lib_root"].contains
    assert widget.find_node_id_for_block(created.id) is not None


def test_external_thumbnail_drop_from_link_source_creates_clone_with_lib_provenance() -> None:
    _ = _app()
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
        Block(
            id="img_link_1",
            type=BlockType.IMAGE,
            profile="asset",
            name="Linked Image",
            access_mode=BlockAccessMode.LINK,
            provenance={
                "kind": BlockProvenanceKind.LIB_LINK.value,
                "mount_id": "lib_mount_123",
                "source_block_id": "lib_img_9",
                "source_block_name": "LIB Image 9",
            },
            content={"storage_path": "a.png"},
        ),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    target_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "blk_internal_lib_root"
    )
    widget._handle_external_block_drop(["img_link_1"], target_node_id)

    created = next(
        block
        for block in widget._blocks
        if block.id not in {"blk_internal_lib_root", "blk_internal_lib_empty", "img_link_1"}
    )
    assert created.access_mode is BlockAccessMode.OWNED
    assert created.provenance.get("kind") == BlockProvenanceKind.LIB_CLONE.value
    assert created.provenance.get("mount_id") == "lib_mount_123"
    assert created.provenance.get("source_block_id") == "lib_img_9"


def test_external_finder_file_drop_imports_and_creates_block(tmp_path) -> None:
    _ = _app()
    storage = ProjectStorageService()
    project_path = tmp_path / "finder_drop_project"
    storage.create_project(project_path, "Finder Drop Project")

    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks, project_root=project_path)

    source_file = tmp_path / "new_asset.png"
    source_file.write_bytes(b"pngdata")

    virtual_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "blk_internal_lib_root"
    )
    before_count = len(widget._blocks)
    widget._handle_external_files_drop([str(source_file)], virtual_node_id)

    assert len(widget._blocks) == before_count + 1
    created_blocks = [block for block in widget._blocks if block.id not in {"blk_internal_lib_root", "blk_internal_lib_empty"}]
    assert len(created_blocks) == 1
    created = created_blocks[0]
    assert created.type == BlockType.IMAGE
    assert created.id in widget._blocks_by_id["blk_internal_lib_root"].contains
    storage_path = str(created.content.get("storage_path", ""))
    assert storage_path.startswith("storage/files/")
    imported_file = (project_path / storage_path).resolve()
    assert imported_file.exists()


def test_external_drop_on_user_subfolder_attaches_to_nearest_container() -> None:
    _ = _app()
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", content={"storage_path": "a.png"}),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    virtual_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "blk_internal_lib_root"
    )
    user_folder_id = widget.add_folder("Shots", parent_node_id=virtual_node_id)
    assert user_folder_id is not None

    before_contains = list(widget._blocks_by_id["blk_internal_lib_root"].contains)
    widget._handle_external_block_drop(["img_1"], user_folder_id)

    assert len(widget._blocks_by_id["blk_internal_lib_root"].contains) == len(before_contains) + 1
    created_block_ids = [bid for bid in widget._blocks_by_id["blk_internal_lib_root"].contains if bid not in before_contains]
    assert len(created_block_ids) == 1
    created_block = widget._blocks_by_id[created_block_ids[0]]
    assert created_block.type == BlockType.IMAGE


def test_external_drop_on_block_node_attaches_to_same_ancestor_container() -> None:
    _ = _app()
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", content={"storage_path": "a.png"}),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    empty_node_id = widget.find_node_id_for_block("blk_internal_lib_empty")
    assert empty_node_id is not None

    before_contains = list(widget._blocks_by_id["blk_internal_lib_root"].contains)
    widget._handle_external_block_drop(["img_1"], empty_node_id)

    assert len(widget._blocks_by_id["blk_internal_lib_root"].contains) == len(before_contains) + 1
    created_block_ids = [bid for bid in widget._blocks_by_id["blk_internal_lib_root"].contains if bid not in before_contains]
    assert len(created_block_ids) == 1
    created_block = widget._blocks_by_id[created_block_ids[0]]
    assert created_block.type == BlockType.IMAGE


def test_delete_block_button_removes_container_and_descendants(monkeypatch) -> None:
    _ = _app()
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty", "cnt_story"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
        Block(
            id="cnt_story",
            type=BlockType.CONTAINER,
            profile="container",
            name="Story Container",
            contains=["img_1", "vid_1"],
        ),
        Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
        Block(id="vid_1", type=BlockType.VIDEO, profile="asset", name="Video 1"),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    story_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "cnt_story"
    )
    assert _select_node(widget, story_node_id)
    monkeypatch.setattr(widget, "_confirm_block_deletion", lambda *_args, **_kwargs: True)
    widget._prompt_delete_selected_block()

    assert "cnt_story" not in widget._blocks_by_id
    assert "img_1" not in widget._blocks_by_id
    assert "vid_1" not in widget._blocks_by_id
    assert "cnt_story" not in widget._blocks_by_id["blk_internal_lib_root"].contains
    assert all(node.block_id not in {"cnt_story", "img_1", "vid_1"} for node in widget._tree.nodes.values())


def test_add_import_button_imports_into_selected_container(tmp_path, monkeypatch) -> None:
    _ = _app()
    storage = ProjectStorageService()
    project_path = tmp_path / "btn_import_project"
    storage.create_project(project_path, "Button Import Project")
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks, project_root=project_path)

    virtual_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "blk_internal_lib_root"
    )
    assert _select_node(widget, virtual_node_id)

    source_file = tmp_path / "button_import.png"
    source_file.write_bytes(b"pngdata")
    monkeypatch.setattr(
        "UI.Widgets.free_tree_widget.QFileDialog.getOpenFileNames",
        lambda *_args, **_kwargs: ([str(source_file)], "All Files (*)"),
    )

    before_contains = list(widget._blocks_by_id["blk_internal_lib_root"].contains)
    widget._prompt_import_into_selected_container()

    created_block_ids = [bid for bid in widget._blocks_by_id["blk_internal_lib_root"].contains if bid not in before_contains]
    assert len(created_block_ids) == 1
    created = widget._blocks_by_id[created_block_ids[0]]
    assert created.type == BlockType.IMAGE
    assert str(created.content.get("storage_path", "")).startswith("storage/files/")


def test_add_import_button_imports_when_block_inside_container_is_selected(tmp_path, monkeypatch) -> None:
    _ = _app()
    storage = ProjectStorageService()
    project_path = tmp_path / "btn_import_block_selected_project"
    storage.create_project(project_path, "Button Import Block Selected")
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks, project_root=project_path)

    empty_node_id = widget.find_node_id_for_block("blk_internal_lib_empty")
    assert empty_node_id is not None
    assert _select_node(widget, empty_node_id)

    source_file = tmp_path / "button_import_block_selected.png"
    source_file.write_bytes(b"pngdata")
    monkeypatch.setattr(
        "UI.Widgets.free_tree_widget.QFileDialog.getOpenFileNames",
        lambda *_args, **_kwargs: ([str(source_file)], "All Files (*)"),
    )

    before_contains = list(widget._blocks_by_id["blk_internal_lib_root"].contains)
    widget._prompt_import_into_selected_container()

    created_block_ids = [bid for bid in widget._blocks_by_id["blk_internal_lib_root"].contains if bid not in before_contains]
    assert len(created_block_ids) == 1
    created = widget._blocks_by_id[created_block_ids[0]]
    assert created.type == BlockType.IMAGE


def test_add_import_button_imports_into_internal_lib_when_no_selection(tmp_path, monkeypatch) -> None:
    _ = _app()
    storage = ProjectStorageService()
    project_path = tmp_path / "btn_import_no_selection_project"
    storage.create_project(project_path, "Button Import No Selection")
    blocks = [
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks, project_root=project_path)
    widget._tree_view.setCurrentItem(None)
    widget._refresh_action_state()

    source_file = tmp_path / "button_import_no_selection.png"
    source_file.write_bytes(b"pngdata")
    monkeypatch.setattr(
        "UI.Widgets.free_tree_widget.QFileDialog.getOpenFileNames",
        lambda *_args, **_kwargs: ([str(source_file)], "All Files (*)"),
    )

    before_contains = list(widget._blocks_by_id["blk_internal_lib_root"].contains)
    widget._prompt_import_into_selected_container()

    created_block_ids = [bid for bid in widget._blocks_by_id["blk_internal_lib_root"].contains if bid not in before_contains]
    assert len(created_block_ids) == 1
    created = widget._blocks_by_id[created_block_ids[0]]
    assert created.type == BlockType.IMAGE


def test_add_character_template_creates_character_hierarchy_in_characters_root(monkeypatch) -> None:
    _ = _app()
    blocks = [
        Block(
            id="blk_characters_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="Characters Root",
            contains=[],
        ),
        Block(
            id="blk_internal_lib_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="INTERNALLIB",
            contains=["blk_internal_lib_empty"],
        ),
        Block(
            id="blk_internal_lib_empty",
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
        ),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    characters_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "blk_characters_root"
    )
    assert _select_node(widget, characters_node_id)
    monkeypatch.setattr(
        "UI.Widgets.free_tree_widget.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Ariane", True),
    )

    widget._prompt_add_character_template()

    created_character = next(
        block
        for block in widget._blocks
        if block.profile == "character" and block.name == "Ariane"
    )
    assert created_character.id in widget._blocks_by_id["blk_characters_root"].contains

    created_form_ids = list(created_character.contains)
    assert created_form_ids
    for form_id in created_form_ids:
        form = widget._blocks_by_id[form_id]
        assert form.type == BlockType.CONTAINER
        assert form.profile == "character_form"
        assert form.contains
        for slot_id in form.contains:
            slot = widget._blocks_by_id[slot_id]
            assert slot.type == BlockType.EMPTY
            assert slot.profile == "template_slot"

    assert any(
        node.kind == "folder" and node.block_id == created_character.id
        for node in widget._tree.nodes.values()
    )


def test_add_character_template_falls_back_to_characters_root_when_selection_is_character_form(monkeypatch) -> None:
    _ = _app()
    blocks = [
        Block(
            id="blk_characters_root",
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name="Characters Root",
            contains=["blk_character_existing"],
        ),
        Block(
            id="blk_character_existing",
            type=BlockType.CONTAINER,
            profile="character",
            name="Existing Character",
            contains=["blk_character_existing_form"],
        ),
        Block(
            id="blk_character_existing_form",
            type=BlockType.CONTAINER,
            profile="character_form",
            name="Existing Form",
            contains=[],
        ),
    ]
    widget = FreeTreeWidget()
    widget.set_blocks(blocks)

    form_node_id = next(
        node_id
        for node_id, node in widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "blk_character_existing_form"
    )
    assert _select_node(widget, form_node_id)
    monkeypatch.setattr(
        "UI.Widgets.free_tree_widget.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Nova", True),
    )

    widget._prompt_add_character_template()

    created_character = next(
        block
        for block in widget._blocks
        if block.profile == "character" and block.name == "Nova"
    )
    assert created_character.id in widget._blocks_by_id["blk_characters_root"].contains
    assert created_character.id not in widget._blocks_by_id["blk_character_existing_form"].contains
