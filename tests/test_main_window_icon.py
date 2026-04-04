import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SBC2_USER_CONFIG_FILE"] = f"/tmp/sbc2_user_config_test_{os.getpid()}.json"
Path(os.environ["SBC2_USER_CONFIG_FILE"]).unlink(missing_ok=True)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

import UI.windows.main_window as main_window_module
from domain import Block, BlockDomain, BlockType
from infrastructure.storage import ProjectStorageService
from UI.Widgets import BlockPropertyWidget, ThumbnailListView
from UI.windows.main_window import (
    FreeTreeWindow,
    MainWindow,
    ThumbnailListWindow,
    _resolve_app_icon_path,
    _resolve_data_project_dir,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_main_window_uses_icon_from_appicons_folder() -> None:
    _ = _app()
    icon_path = _resolve_app_icon_path()
    assert icon_path is not None
    assert icon_path.exists()

    window = MainWindow()
    assert not window.windowIcon().isNull()


def test_main_window_resolves_local_data_project_directory() -> None:
    path = _resolve_data_project_dir()
    assert path.name == "DataProject"
    assert path.exists()


def test_thumbnail_list_window_has_thumbnail_list_view() -> None:
    _ = _app()
    window = ThumbnailListWindow()
    assert not window.windowIcon().isNull()
    assert isinstance(window._list_view, ThumbnailListView)
    assert isinstance(window._property_widget, BlockPropertyWidget)
    assert window._content_splitter.count() == 2


def test_free_tree_window_contains_widget() -> None:
    _ = _app()
    window = FreeTreeWindow()
    assert not window.windowIcon().isNull()
    assert window._free_tree_widget is not None


def test_main_window_button_opens_thumbnail_list_window() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    tools_button = window._sidebar.nav_button("tools")
    assert tools_button is not None
    QTest.mouseClick(tools_button, Qt.LeftButton)
    app.processEvents()
    assert window._workspace_stack.currentWidget() is window._workspace_tools_page

    assert window._thumbnail_window is None
    assert len(window._open_thumbnail_buttons) >= 5

    first_window = None
    for button in window._open_thumbnail_buttons:
        assert not button.icon().isNull()
        QTest.mouseClick(button, Qt.LeftButton)
        app.processEvents()
        assert window._thumbnail_window is not None
        assert window._thumbnail_window.isVisible()
        if first_window is None:
            first_window = window._thumbnail_window
        else:
            assert window._thumbnail_window is first_window


def test_main_window_button_opens_free_tree_window() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window._free_tree_window is None
    project_button = window._sidebar.nav_button("project")
    assert project_button is not None
    QTest.mouseClick(project_button, Qt.LeftButton)
    app.processEvents()
    assert window._open_free_tree_button.text() == "PROJECT TREE"
    assert window._open_free_tree_button.property("primary") is True
    QTest.mouseClick(window._open_free_tree_button, Qt.LeftButton)
    app.processEvents()
    assert window._free_tree_window is not None
    assert window._free_tree_window.isVisible()


def test_main_window_button_opens_media_carousel_window() -> None:
    app = _app()
    blocks = [
        Block(id="img", type=BlockType.IMAGE, profile="asset", name="IMG"),
        Block(id="vid", type=BlockType.VIDEO, profile="asset", name="VID"),
    ]
    window = MainWindow(blocks=blocks, project_root=None)
    window.show()
    app.processEvents()

    tools_button = window._sidebar.nav_button("tools")
    assert tools_button is not None
    QTest.mouseClick(tools_button, Qt.LeftButton)
    app.processEvents()
    assert window._workspace_stack.currentWidget() is window._workspace_tools_page

    assert window._media_carousel_window is None
    QTest.mouseClick(window._open_media_carousel_button, Qt.LeftButton)
    app.processEvents()

    assert window._media_carousel_window is not None
    assert window._media_carousel_window.isVisible()
    assert "Items: 2" in window._media_carousel_window._subtitle.text()

    first_window = window._media_carousel_window
    QTest.mouseClick(window._open_media_carousel_button, Qt.LeftButton)
    app.processEvents()
    assert window._media_carousel_window is first_window


def test_create_new_project_appends_sbcprj_suffix(tmp_path, monkeypatch) -> None:
    _ = _app()
    projects_root = tmp_path / "projects"
    monkeypatch.setenv("SBC2_PROJECTS_DIR", str(projects_root))
    monkeypatch.setenv("SBC2_USER_LIBRARIES_DIR", str(tmp_path / "libraries_user"))
    monkeypatch.setenv("SBC2_APPLICATION_LIBRARIES_DIR", str(tmp_path / "libraries_app"))
    monkeypatch.setattr(
        "UI.windows.main_window.QInputDialog.getText",
        lambda *_args, **_kwargs: ("My Film Project", True),
    )

    window = MainWindow()
    window._create_new_project()

    assert window._project_root is not None
    assert window._project_root.name.endswith(".sbcprj")
    assert window._project_root.exists()


def test_open_project_dialog_lists_only_sbcprj_directories(tmp_path, monkeypatch) -> None:
    _ = _app()
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SBC2_PROJECTS_DIR", str(projects_root))
    monkeypatch.setenv("SBC2_USER_LIBRARIES_DIR", str(tmp_path / "libraries_user"))
    monkeypatch.setenv("SBC2_APPLICATION_LIBRARIES_DIR", str(tmp_path / "libraries_app"))

    storage = ProjectStorageService()
    valid_project = projects_root / "project_a.sbcprj"
    legacy_project = projects_root / "project_legacy"
    storage.create_project(valid_project, "Project A")
    storage.create_project(legacy_project, "Project Legacy")

    captured: dict[str, list[str]] = {}

    def _fake_get_item(_parent, _title, _label, items, _current, _editable):
        captured["items"] = list(items)
        return "project_a.sbcprj", True

    monkeypatch.setattr("UI.windows.main_window.QInputDialog.getItem", _fake_get_item)

    window = MainWindow()
    window._open_project_from_dialog()

    assert captured.get("items") == ["project_a.sbcprj"]
    assert window._project_root == valid_project.resolve()


def test_closing_main_window_closes_all_secondary_windows() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    window._open_thumbnail_window()
    window._open_media_carousel_window()
    window._open_free_tree_window()
    app.processEvents()

    assert window._thumbnail_window is not None
    assert window._media_carousel_window is not None
    assert window._free_tree_window is not None

    window.close()
    app.processEvents()

    assert window._thumbnail_window is None
    assert window._media_carousel_window is None
    assert window._free_tree_window is None


def test_main_window_has_project_action_buttons() -> None:
    _ = _app()
    window = MainWindow()
    assert window._new_project_button.text() == "NEW PROJECT"
    assert window._open_project_button.text() == "OPEN PROJECT"
    assert window._close_project_button.text() == "CLOSE PROJECT"
    assert window._open_free_tree_button.text() == "PROJECT TREE"
    assert window._new_project_button not in window._workspace_action_buttons
    assert window._open_project_button not in window._workspace_action_buttons
    assert window._close_project_button not in window._workspace_action_buttons
    assert window._open_free_tree_button not in window._workspace_action_buttons
    assert window._select_project_visual_button.text() == "SELECT VISUAL"
    assert window._select_project_visual_button not in window._workspace_action_buttons


def test_dashboard_shows_project_workspace_and_stats() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window._workspace_stack.currentWidget() is window._workspace_dashboard_page
    assert window._project_workspace.isVisible()
    assert window._dashboard_stats_frame.isVisible()
    assert "images" in window._dashboard_stat_tiles
    assert "videos" in window._dashboard_stat_tiles


def test_close_project_clears_current_project_and_footer(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_to_close"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project To Close")

    window = MainWindow()
    window.show()
    app.processEvents()
    window._load_project(project_path)
    app.processEvents()

    assert window._project_root == project_path.resolve()
    assert "Project:" in window._workspace_footer.text()
    assert window._close_project_button.isEnabled()

    QTest.mouseClick(window._close_project_button, Qt.LeftButton)
    app.processEvents()

    assert window._project_root is None
    assert window._blocks == []
    assert window._workspace_footer.text() == "Application is running"
    assert not window._close_project_button.isEnabled()


def test_sidebar_project_navigation_shows_project_workspace() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    project_button = window._sidebar.nav_button("project")
    assert project_button is not None
    QTest.mouseClick(project_button, Qt.LeftButton)
    app.processEvents()

    assert window._workspace_stack.currentWidget() is window._workspace_project_page
    assert window._workspace_header.text() == "PROJECT"
    assert window._project_page_empty_state._title_label.text() == "PROJECT WORKSPACE MOVED"
    assert window._project_page_empty_state._action_button.text() == "OPEN DASHBOARD"

    QTest.mouseClick(window._project_page_empty_state._action_button, Qt.LeftButton)
    app.processEvents()

    assert window._workspace_stack.currentWidget() is window._workspace_dashboard_page
    assert window._project_workspace._value_labels["name"].text()
    assert window._project_workspace._value_labels["created_at"].text()
    assert window._project_workspace._value_labels["updated_at"].text()
    assert window._project_workspace._save_button.property("primary") is True
    assert not window._project_workspace._description_text.isReadOnly()


def test_project_workspace_save_persists_author_email_description(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_editable"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Editable")
    window = MainWindow(blocks=[], project_root=project_path)
    window.show()
    app.processEvents()

    window._project_workspace._author_name_edit.setText("Alice")
    window._project_workspace._author_email_edit.setText("alice@example.com")
    window._project_workspace._description_text.setPlainText("Project description")
    preview_size_before = window._project_workspace._preview_label.size()
    QTest.mouseClick(window._project_workspace._save_button, Qt.LeftButton)
    app.processEvents()
    preview_size_after = window._project_workspace._preview_label.size()

    metadata = storage.load_project_metadata(project_path)
    assert metadata["author_name"] == "Alice"
    assert metadata["author_email"] == "alice@example.com"
    assert metadata["description"] == "Project description"
    assert window._project_workspace._save_status_label.text() == "Saved"
    assert preview_size_before == preview_size_after


def test_select_project_visual_button_updates_project_preview_metadata(tmp_path, monkeypatch) -> None:
    app = _app()
    project_path = tmp_path / "project_visual_picker"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Visual Picker")
    (project_path / "storage" / "files").mkdir(parents=True, exist_ok=True)
    (project_path / "storage" / "files" / "ref.png").write_bytes(b"pngdata")

    image_block = Block(
        id="blk_img_preview",
        type=BlockType.IMAGE,
        profile="asset",
        name="Preview Candidate",
        content={"storage_path": "storage/files/ref.png"},
    )
    storage.save_blocks(project_path, [image_block])

    class _AcceptedPicker:
        def __init__(self, *, blocks, **_kwargs):
            self._blocks = list(blocks)

        def exec(self) -> int:
            return 1

        def selected_block(self):
            return self._blocks[0] if self._blocks else None

    monkeypatch.setattr(main_window_module, "ProjectVisualPickerDialog", _AcceptedPicker)

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    QTest.mouseClick(window._select_project_visual_button, Qt.LeftButton)
    app.processEvents()

    metadata = storage.load_project_metadata(project_path)
    assert metadata.get("preview_image_path") == "storage/files/ref.png"
    assert window._project_workspace._save_status_label.text() == "Project visual updated"


def test_new_project_workspace_structure_defaults_are_seeded(tmp_path) -> None:
    _ = _app()
    project_path = tmp_path / "project_virtual_seed"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Virtual Seed")

    window = MainWindow()
    window._seed_workspace_structure_defaults(project_path)

    blocks = storage.load_blocks(project_path)
    by_id = {block.id: block for block in blocks}
    assert "blk_project_root" in by_id
    assert "blk_characters_root" in by_id
    assert "blk_story_root" in by_id
    assert "blk_lib_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert "blk_internal_lib_empty" in by_id

    assert by_id["blk_project_root"].type is BlockType.CONTAINER
    assert by_id["blk_project_root"].profile == "workspace_root"
    assert by_id["blk_project_root"].name == "PROJET"
    assert by_id["blk_internal_lib_root"].type is BlockType.CONTAINER
    assert by_id["blk_internal_lib_root"].profile == "workspace_root"
    assert by_id["blk_internal_lib_root"].name == "INTERNALLIB"
    assert by_id["blk_internal_lib_empty"].type is BlockType.EMPTY
    assert by_id["blk_internal_lib_empty"].id in by_id["blk_internal_lib_root"].contains
    assert by_id["blk_internal_lib_root"].id in by_id["blk_project_root"].contains


def test_open_project_creates_workspace_structure_defaults_when_missing(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_without_virtual"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Without Virtual")
    storage.save_blocks(
        project_path,
        [Block(id="blk_img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", content={"path": "a.png"})],
    )

    window = MainWindow()
    window.show()
    app.processEvents()
    window._load_project(project_path)
    app.processEvents()

    loaded = storage.load_blocks(project_path)
    by_id = {block.id: block for block in loaded}
    assert "blk_project_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert "blk_internal_lib_empty" in by_id
    assert by_id["blk_project_root"].type is BlockType.CONTAINER
    assert by_id["blk_project_root"].profile == "workspace_root"
    assert by_id["blk_project_root"].name == "PROJET"
    assert by_id["blk_internal_lib_root"].type is BlockType.CONTAINER
    assert by_id["blk_internal_lib_root"].profile == "workspace_root"
    assert by_id["blk_internal_lib_root"].name == "INTERNALLIB"
    assert by_id["blk_internal_lib_empty"].type is BlockType.EMPTY
    assert by_id["blk_internal_lib_empty"].id in by_id["blk_internal_lib_root"].contains
    assert by_id["blk_internal_lib_root"].id in by_id["blk_project_root"].contains


def test_constructor_load_project_creates_workspace_structure_defaults_when_missing(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_without_virtual_ctor"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Without Virtual Ctor")
    storage.save_blocks(
        project_path,
        [Block(id="blk_img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", content={"path": "a.png"})],
    )

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    loaded = storage.load_blocks(project_path)
    by_id = {block.id: block for block in loaded}
    assert "blk_project_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert "blk_internal_lib_empty" in by_id
    assert by_id["blk_project_root"].type is BlockType.CONTAINER
    assert by_id["blk_project_root"].profile == "workspace_root"
    assert by_id["blk_project_root"].name == "PROJET"
    assert by_id["blk_internal_lib_root"].type is BlockType.CONTAINER
    assert by_id["blk_internal_lib_root"].profile == "workspace_root"
    assert by_id["blk_internal_lib_root"].name == "INTERNALLIB"
    assert by_id["blk_internal_lib_empty"].type is BlockType.EMPTY
    assert by_id["blk_internal_lib_empty"].id in by_id["blk_internal_lib_root"].contains
    assert by_id["blk_internal_lib_root"].id in by_id["blk_project_root"].contains


def test_open_project_migrates_legacy_virtual_to_project_root_and_internallib(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_legacy_virtual_layout"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Legacy Virtual")
    storage.save_blocks(
        project_path,
        [
            Block(
                id="blk_characters_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="Characters Root",
                domain=BlockDomain.CHARACTERS,
                contains=[],
            ),
            Block(
                id="blk_story_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="Story Root",
                domain=BlockDomain.STORY,
                contains=[],
            ),
            Block(
                id="blk_lib_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="Library Root",
                domain=BlockDomain.LIB,
                contains=[],
            ),
            Block(
                id="blk_virtual_root",
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name="VIRTUAL",
                domain=BlockDomain.LIB,
                contains=["blk_virtual_empty"],
            ),
            Block(
                id="blk_virtual_empty",
                type=BlockType.EMPTY,
                profile="virtual_empty",
                name="Drop Resources Here",
                domain=BlockDomain.LIB,
            ),
        ],
    )

    window = MainWindow()
    window.show()
    app.processEvents()
    window._load_project(project_path)
    app.processEvents()

    loaded = storage.load_blocks(project_path)
    by_id = {block.id: block for block in loaded}
    assert "blk_project_root" in by_id
    assert "blk_internal_lib_root" in by_id
    assert "blk_internal_lib_empty" in by_id
    assert "blk_virtual_root" not in by_id
    assert "blk_virtual_empty" not in by_id
    assert by_id["blk_internal_lib_root"].name == "INTERNALLIB"
    assert by_id["blk_internal_lib_empty"].id in by_id["blk_internal_lib_root"].contains
    for child_id in ("blk_characters_root", "blk_story_root", "blk_lib_root", "blk_internal_lib_root"):
        assert child_id in by_id["blk_project_root"].contains

def test_settings_workspace_is_shown_and_theme_changes_dynamically() -> None:
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    settings_button = window._sidebar.nav_button("settings")
    assert settings_button is not None
    QTest.mouseClick(settings_button, Qt.LeftButton)
    app.processEvents()

    assert window._workspace_stack.currentWidget() is window._workspace_settings_page
    assert not window._settings_workspace._tabs.tabIcon(0).isNull()
    assert not window._settings_workspace._tabs.tabIcon(1).isNull()
    assert not window._settings_workspace._tabs.tabIcon(2).isNull()
    assert window._settings_workspace._tabs.count() == 3
    assert "DataProject" in window._settings_workspace._storage_value_labels["projects"].text()
    assert "LIBRARIES" in window._settings_workspace._storage_value_labels["libraries_user"].text()
    assert "LIBRARIES" in window._settings_workspace._storage_value_labels["libraries_application"].text()

    theme_combo = window._settings_workspace._theme_combo
    target_theme = "light" if theme_combo.findData("light") >= 0 else str(theme_combo.itemData(0) or "")
    assert target_theme
    target_index = theme_combo.findData(target_theme)
    if target_index < 0:
        target_index = 0
    theme_combo.setCurrentIndex(target_index)
    app.processEvents()

    assert str(app.property("sbc2_theme_name") or "") == target_theme

    dark_index = theme_combo.findData("dark")
    if dark_index >= 0:
        theme_combo.setCurrentIndex(dark_index)
        app.processEvents()


def test_thumbnail_list_window_filters_by_tags_type_and_profile() -> None:
    app = _app()
    blocks = [
        Block(id="a", type=BlockType.IMAGE, profile="asset", name="A", tags=["hero", "sunset"]),
        Block(id="b", type=BlockType.VIDEO, profile="asset", name="B", tags=["night"]),
        Block(id="c", type=BlockType.TEXT, profile="note", name="C", tags=["hero_notes"]),
    ]
    window = ThumbnailListWindow(blocks=blocks, project_root=None)
    window.show()
    app.processEvents()

    model = window._list_view.model()
    assert model is not None
    assert model.rowCount() == 3

    window._tag_search_input.setText("hero")
    app.processEvents()
    assert model.rowCount() == 2

    image_index = window._type_filter_combo.findData(BlockType.IMAGE.value)
    assert image_index >= 0
    window._type_filter_combo.setCurrentIndex(image_index)
    app.processEvents()
    assert model.rowCount() == 1

    window._tag_search_input.clear()
    note_index = window._profile_filter_combo.findData("note")
    assert note_index >= 0
    window._profile_filter_combo.setCurrentIndex(note_index)
    app.processEvents()
    assert model.rowCount() == 0


def test_thumbnail_list_window_click_updates_property_widget() -> None:
    app = _app()
    blocks = [
        Block(id="a", type=BlockType.IMAGE, profile="asset", name="A", tags=["hero"], content={"path": "a.png"}),
        Block(id="b", type=BlockType.VIDEO, profile="asset", name="B", tags=["night"]),
    ]
    window = ThumbnailListWindow(blocks=blocks, project_root=None)
    window.show()
    app.processEvents()

    model = window._list_view.model()
    assert model is not None
    index = model.index(0, 0)
    assert index.isValid()

    window._list_view._handle_clicked(index)
    app.processEvents()

    assert window._property_widget.current_block_id() == "a"


def test_project_free_tree_state_is_persisted_and_restored(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_tree_state"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Tree State")
    storage.save_blocks(
        project_path,
        [
            Block(id="cnt_1", type=BlockType.CONTAINER, profile="container", name="Container", contains=["img_1", "txt_1"]),
            Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
            Block(id="txt_1", type=BlockType.TEXT, profile="note", name="Note 1"),
        ],
    )

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    QTest.mouseClick(window._open_free_tree_button, Qt.LeftButton)
    app.processEvents()

    assert window._free_tree_window is not None
    container_node_id = next(
        node_id
        for node_id, node in window._free_tree_window._free_tree_widget._tree.nodes.items()
        if node.kind == "folder" and node.block_id == "cnt_1"
    )
    folder_id = window._free_tree_window._free_tree_widget.add_folder("User Folder", parent_node_id=container_node_id)
    assert folder_id is not None
    image_node_id = window._free_tree_window._free_tree_widget.find_node_id_for_block("img_1")
    assert image_node_id is not None
    window._free_tree_window._free_tree_widget.move_node(image_node_id, folder_id)
    app.processEvents()
    window._free_tree_window.close()
    app.processEvents()

    persisted_blocks = storage.load_blocks(project_path)
    image_block = next(block for block in persisted_blocks if block.id == "img_1")
    assert image_block.container_paths.get("cnt_1") == "User Folder"

    restored = MainWindow(project_root=project_path)
    restored.show()
    app.processEvents()
    QTest.mouseClick(restored._open_free_tree_button, Qt.LeftButton)
    app.processEvents()

    assert restored._free_tree_window is not None
    assert any(
        node.kind == "folder" and node.name == "User Folder"
        for node in restored._free_tree_window._free_tree_widget._tree.nodes.values()
    )


def test_dashboard_stats_counts_project_blocks(tmp_path) -> None:
    app = _app()
    project_path = tmp_path / "project_dashboard_stats"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project Dashboard Stats")
    storage.save_blocks(
        project_path,
        [
            Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1"),
            Block(id="img_2", type=BlockType.IMAGE, profile="asset", name="Image 2"),
            Block(id="vid_1", type=BlockType.VIDEO, profile="asset", name="Video 1"),
            Block(id="aud_1", type=BlockType.AUDIO, profile="voice", name="Audio 1"),
            Block(id="pr_1", type=BlockType.PROMPT, profile="prompt", name="Prompt 1"),
            Block(id="char_1", type=BlockType.CONTAINER, profile="character", name="Character 1"),
            Block(id="shot_1", type=BlockType.CONTAINER, profile="shot", name="Shot 1"),
            Block(id="form_1", type=BlockType.CONTAINER, profile="character_form", name="Form 1"),
        ],
    )

    window = MainWindow(project_root=project_path)
    window.show()
    app.processEvents()

    assert window._dashboard_stat_tiles["images"]._value_label.text() == "2"
    assert window._dashboard_stat_tiles["videos"]._value_label.text() == "1"
    assert window._dashboard_stat_tiles["audio"]._value_label.text() == "1"
    assert window._dashboard_stat_tiles["prompts"]._value_label.text() == "1"
    assert window._dashboard_stat_tiles["characters"]._value_label.text() == "1"
    assert window._dashboard_stat_tiles["shots"]._value_label.text() == "1"
    assert window._dashboard_stat_tiles["forms"]._value_label.text() == "1"
