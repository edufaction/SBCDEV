from pathlib import Path

from application import (
    BlockWorkspaceService,
    CharacterWorkspaceController,
    CharacterWorkspaceService,
    ContainerContentService,
    GraphWorkspaceController,
    ProjectLifecycleController,
    ProjectWindowController,
    ProjectWorkspaceController,
    ProjectSession,
    SecondaryWindowsController,
    StoryWorkspaceController,
    StoryWorkspaceService,
    WindowNavigationController,
)
from application.workspaces import ProjectWorkspaceService
from domain import Block, BlockDomain, BlockType, FreeGraph, InputConnection, PortType
from infrastructure.storage import ProjectStorageService


class _FakePanel:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.selected: list[tuple[str, str | None]] = []

    def set_message(self, message: str) -> None:
        self.messages.append(message)

    def select_block(self, block_id: str, *, container_id: str | None = None) -> bool:
        self.selected.append((block_id, container_id))
        return True


def test_character_workspace_controller_creates_note_and_selects_it(tmp_path: Path) -> None:
    project_path = tmp_path / "controller_char.sbcprj"
    ProjectStorageService().create_project(project_path, "Controller Char")

    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters",
        domain=BlockDomain.CHARACTERS,
        contains=["form_1"],
        content={"workspace_role": "characters_root"},
    )
    form = Block(
        id="form_1",
        type=BlockType.CONTAINER,
        profile="character_form",
        name="Main Form",
        domain=BlockDomain.CHARACTERS,
        container_paths={"blk_characters_root": ""},
    )
    session = ProjectSession(project_root=project_path, blocks=[root, form])
    panel = _FakePanel()
    persisted: list[int] = []

    controller = CharacterWorkspaceController(
        panel=panel,
        session=session,
        content_service=ContainerContentService(),
        block_workspace_service=BlockWorkspaceService(),
        character_workspace_service=CharacterWorkspaceService(),
        persist_blocks=lambda blocks: persisted.append(len(list(blocks))),
    )

    controller.create_note("form_1")

    note = next(block for block in session.blocks if block.type == BlockType.TEXT and block.profile == "note")
    assert note.id in form.contains
    assert panel.selected == [(note.id, "form_1")]
    assert persisted
    assert panel.messages[-1] == f"Note created: {note.name or note.id}"


def test_story_workspace_controller_updates_block_message(tmp_path: Path) -> None:
    project_path = tmp_path / "controller_story.sbcprj"
    ProjectStorageService().create_project(project_path, "Controller Story")

    note = Block(
        id="note_1",
        type=BlockType.TEXT,
        profile="note",
        name="Old",
        domain=BlockDomain.STORY,
        content={"text": "Body"},
    )
    session = ProjectSession(project_root=project_path, blocks=[note])
    panel = _FakePanel()
    persisted: list[int] = []

    controller = StoryWorkspaceController(
        panel=panel,
        session=session,
        content_service=ContainerContentService(),
        block_workspace_service=BlockWorkspaceService(),
        story_workspace_service=StoryWorkspaceService(),
        persist_blocks=lambda blocks: persisted.append(len(list(blocks))),
    )

    controller.update_block({"block_id": "note_1", "name": "Updated"})

    assert note.name == "Updated"
    assert persisted == [1]
    assert panel.messages[-1] == "Block saved: Updated"


def test_graph_workspace_controller_creates_link_and_reports_feedback(tmp_path: Path) -> None:
    project_path = tmp_path / "controller_graph.sbcprj"
    ProjectStorageService().create_project(project_path, "Controller Graph")

    image = Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", domain=BlockDomain.STORY)
    text = Block(id="txt_1", type=BlockType.TEXT, profile="preset", name="Preset 1", domain=BlockDomain.STORY)
    shot = Block(
        id="shot_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        domain=BlockDomain.STORY,
        contains=[image.id, text.id],
        graph=FreeGraph(),
    )
    session = ProjectSession(project_root=project_path, blocks=[shot, image, text])
    persisted: list[int] = []
    feedback: list[tuple[str, str]] = []

    controller = GraphWorkspaceController(
        session=session,
        persist_blocks=lambda blocks: persisted.append(len(list(blocks))),
        set_feedback=lambda container_id, message: feedback.append((container_id, message)),
    )

    controller.create_link(
        container_id="shot_1",
        source_block_id="img_1",
        target_block_id="txt_1",
        target_port=PortType.IN.value,
        name="ref",
    )

    updated_text = next(block for block in session.blocks if block.id == "txt_1")
    assert updated_text.inputs == [InputConnection(source_block_id="img_1", port=PortType.IN, name="ref")]
    assert persisted == [3]
    assert feedback[-1] == ("shot_1", "Link added: img_1 -> txt_1 (in)")


def test_graph_workspace_controller_initializes_layout_positions(tmp_path: Path) -> None:
    project_path = tmp_path / "controller_graph_layout.sbcprj"
    ProjectStorageService().create_project(project_path, "Controller Graph Layout")

    image = Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1", domain=BlockDomain.STORY)
    shot = Block(
        id="shot_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        domain=BlockDomain.STORY,
        contains=[image.id],
        graph=FreeGraph(),
    )
    session = ProjectSession(project_root=project_path, blocks=[shot, image])
    persisted: list[int] = []

    controller = GraphWorkspaceController(
        session=session,
        persist_blocks=lambda blocks: persisted.append(len(list(blocks))),
        set_feedback=lambda *_args: None,
    )

    controller.initialize_layout(container_id="shot_1", positions=[("img_1", 40.0, 60.0)])

    updated_shot = next(block for block in session.blocks if block.id == "shot_1")
    node = next(iter(updated_shot.graph.nodes.values()))
    assert node.block_id == "img_1"
    assert node.x == 40.0
    assert node.y == 60.0
    assert persisted == [2]


class _FakeProjectPanel:
    def __init__(self) -> None:
        self.metadata: list[tuple[Path | None, dict]] = []
        self.feedback: list[str] = []

    def set_project_metadata(self, *, project_path: Path | None, metadata: dict) -> None:
        self.metadata.append((project_path, metadata))

    def set_save_feedback(self, message: str) -> None:
        self.feedback.append(message)


class _AcceptedPicker:
    def __init__(self, *, blocks, **_kwargs):
        self._blocks = list(blocks)

    def exec(self) -> int:
        return 1

    def selected_block(self):
        return self._blocks[0] if self._blocks else None


class _FakeSecondaryWindow:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.blocks_changed = _Signal()
        self.destroyed = _Signal()
        self.show_count = 0
        self.closed = False
        self.deleted = False
        self.synced: list[tuple[list[Block], Path | None]] = []

    def show(self) -> None:
        self.show_count += 1

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def deleteLater(self) -> None:
        self.deleted = True

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None = None) -> None:
        self.synced.append((list(blocks), project_root))


class _Signal:
    def __init__(self) -> None:
        self._callbacks: list = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeWorkspacePanel:
    def __init__(self) -> None:
        self._graph_widget = type("GraphStub", (), {"active_container_id": lambda self: ""})()
        self._tree_block_id = ""
        self._block_id = ""
        self._container_id: str | None = None
        self.set_blocks_calls: list[tuple[list[Block], Path | None, str | None]] = []
        self.selected_tree: list[str] = []
        self.inspected: list[tuple[str, str | None]] = []

    def current_tree_block_id(self) -> str | None:
        return self._tree_block_id or None

    def current_block_id(self) -> str | None:
        return self._block_id or None

    def current_property_container_id(self) -> str | None:
        return self._container_id

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None, active_container_id: str | None = None) -> None:
        self.set_blocks_calls.append((list(blocks), project_root, active_container_id))

    def select_tree_block(self, block_id: str) -> bool:
        self.selected_tree.append(block_id)
        return True

    def inspect_block(self, block_id: str, *, container_id: str | None = None) -> bool:
        self.inspected.append((block_id, container_id))
        return True


class _FakeLibraryPanel:
    def __init__(self) -> None:
        self.calls: list[tuple[Path | None, Path, Path]] = []

    def set_context(
        self,
        *,
        project_root: Path | None,
        user_libraries_root: Path,
        application_libraries_root: Path,
    ) -> None:
        self.calls.append((project_root, user_libraries_root, application_libraries_root))


class _FakeStack:
    def __init__(self) -> None:
        self.current_widget = None

    def setCurrentWidget(self, widget) -> None:
        self.current_widget = widget


class _FakeHeader:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class _FakeNavButton:
    def __init__(self) -> None:
        self.click_count = 0

    def click(self) -> None:
        self.click_count += 1


class _FakeSidebar:
    def __init__(self, buttons: dict[str, _FakeNavButton] | None = None) -> None:
        self._buttons = buttons or {}
        self.active_keys: list[str] = []

    def nav_button(self, key: str):
        return self._buttons.get(key)

    def set_active(self, key: str) -> None:
        self.active_keys.append(key)


def test_project_window_controller_loads_and_refreshes_workspace(tmp_path: Path) -> None:
    storage = ProjectStorageService()
    project_path = tmp_path / "controller_project.sbcprj"
    storage.create_project(project_path, "Controller Project")
    root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story",
        domain=BlockDomain.STORY,
        content={"workspace_role": "story_root"},
    )
    storage.save_blocks(project_path, [root])

    session = ProjectSession()
    project_panel = _FakeProjectPanel()
    character_panel = _FakeWorkspacePanel()
    story_panel = _FakeWorkspacePanel()
    library_panel = _FakeLibraryPanel()
    footer_updates: list[str] = []
    closed: list[bool] = []
    saved_paths: list[Path | None] = []
    dashboard_refreshes: list[bool] = []

    controller = ProjectWindowController(
        session=session,
        project_workspace_service=ProjectWorkspaceService(),
        project_workspace_panel=project_panel,
        character_workspace_panel=character_panel,
        story_workspace_panel=story_panel,
        library_workspace_panel=library_panel,
        update_workspace_footer=lambda: footer_updates.append("footer"),
        close_secondary_windows=lambda: closed.append(True),
        save_last_project_path=saved_paths.append,
        ensure_workspace_structure_on_open=lambda _project_root, blocks: blocks,
        load_blocks_safely=lambda path: list(storage.load_blocks(path)),
        refresh_dashboard_stats=lambda: dashboard_refreshes.append(True),
        get_user_libraries_root=lambda: tmp_path / "user_libs",
        get_application_libraries_root=lambda: tmp_path / "app_libs",
    )

    loaded = controller.load_project(project_path)

    assert loaded is True
    assert session.project_root == project_path.resolve()
    assert project_panel.metadata
    assert character_panel.set_blocks_calls
    assert story_panel.set_blocks_calls
    assert library_panel.calls
    assert footer_updates == ["footer"]
    assert closed == [True]
    assert saved_paths == [project_path.resolve()]
    assert dashboard_refreshes == [True]


def test_window_navigation_controller_routes_page_and_header() -> None:
    stack = _FakeStack()
    header = _FakeHeader()
    sidebar = _FakeSidebar()
    section_keys: list[str] = []
    dashboard_page = object()
    tools_page = object()

    controller = WindowNavigationController(
        workspace_stack=stack,
        workspace_header=header,
        sidebar=sidebar,
        set_section_key=section_keys.append,
        default_page=dashboard_page,
        pages_by_key={"dashboard": dashboard_page, "tools": tools_page},
        header_overrides={"project": "PROJETS"},
    )

    controller.navigate("tools")
    controller.navigate("project")

    assert section_keys == ["tools", "project"]
    assert header.text == "PROJETS"
    assert stack.current_widget is dashboard_page


def test_window_navigation_controller_clicks_sidebar_button_when_available() -> None:
    button = _FakeNavButton()
    stack = _FakeStack()
    header = _FakeHeader()
    sidebar = _FakeSidebar(buttons={"tools": button})

    controller = WindowNavigationController(
        workspace_stack=stack,
        workspace_header=header,
        sidebar=sidebar,
        set_section_key=lambda _key: None,
        default_page=object(),
        pages_by_key={},
    )

    controller.navigate_to_section("tools")

    assert button.click_count == 1
    assert sidebar.active_keys == []


def test_project_window_controller_closes_project_and_resets_feedback(tmp_path: Path) -> None:
    project_path = tmp_path / "controller_project_close.sbcprj"
    ProjectStorageService().create_project(project_path, "Controller Project Close")
    session = ProjectSession(project_root=project_path, blocks=[Block(id="x", type=BlockType.TEXT, profile="note", name="X")])
    project_panel = _FakeProjectPanel()
    character_panel = _FakeWorkspacePanel()
    story_panel = _FakeWorkspacePanel()
    library_panel = _FakeLibraryPanel()
    footer_updates: list[str] = []
    closed: list[bool] = []
    saved_paths: list[Path | None] = []

    controller = ProjectWindowController(
        session=session,
        project_workspace_service=ProjectWorkspaceService(),
        project_workspace_panel=project_panel,
        character_workspace_panel=character_panel,
        story_workspace_panel=story_panel,
        library_workspace_panel=library_panel,
        update_workspace_footer=lambda: footer_updates.append("footer"),
        close_secondary_windows=lambda: closed.append(True),
        save_last_project_path=saved_paths.append,
        ensure_workspace_structure_on_open=lambda _project_root, blocks: blocks,
        load_blocks_safely=lambda _path: [],
        refresh_dashboard_stats=lambda: None,
        get_user_libraries_root=lambda: tmp_path / "user_libs",
        get_application_libraries_root=lambda: tmp_path / "app_libs",
    )

    controller.close_current_project()

    assert session.project_root is None
    assert session.blocks == []
    assert footer_updates == ["footer"]
    assert closed == [True]
    assert saved_paths == [None]
    assert project_panel.feedback == [""]


def test_project_workspace_controller_saves_metadata(tmp_path: Path) -> None:
    storage = ProjectStorageService()
    project_path = tmp_path / "controller_project_meta.sbcprj"
    storage.create_project(project_path, "Controller Project Meta")
    session = ProjectSession(project_root=project_path, blocks=[])
    feedback: list[str] = []
    refreshed: list[bool] = []

    controller = ProjectWorkspaceController(
        session=session,
        project_workspace_service=ProjectWorkspaceService(),
        storage=storage,
        refresh_workspace=lambda: refreshed.append(True),
        set_feedback=feedback.append,
        visual_picker_dialog_cls=_AcceptedPicker,
        dialog_parent=None,
    )

    controller.save_project_metadata({"author_name": "Alice", "author_email": "alice@example.com", "description": "Demo"})

    metadata = storage.load_project_metadata(project_path)
    assert metadata["author_name"] == "Alice"
    assert metadata["author_email"] == "alice@example.com"
    assert metadata["description"] == "Demo"
    assert refreshed == [True]
    assert feedback == ["Saved"]


def test_secondary_windows_controller_opens_syncs_and_closes_windows(tmp_path: Path) -> None:
    blocks = [Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1")]
    project_root = tmp_path / "controller_secondary.sbcprj"
    persisted: list[object] = []

    controller = SecondaryWindowsController(
        thumbnail_window_cls=_FakeSecondaryWindow,
        media_carousel_window_cls=_FakeSecondaryWindow,
        free_tree_window_cls=_FakeSecondaryWindow,
        persist_blocks=persisted.append,
        parent=None,
    )

    controller.open_thumbnail_window(blocks=blocks, project_root=project_root)
    controller.open_media_carousel_window(blocks=blocks, project_root=project_root)
    controller.open_free_tree_window(blocks=blocks, project_root=project_root)
    controller.sync_project_blocks(blocks=blocks, project_root=project_root)

    assert controller.thumbnail_window is not None
    assert controller.media_carousel_window is not None
    assert controller.free_tree_window is not None
    assert controller.thumbnail_window.show_count == 1
    assert controller.media_carousel_window.show_count == 1
    assert controller.free_tree_window.show_count == 1
    assert controller.thumbnail_window.synced[-1][1] == project_root
    assert controller.media_carousel_window.synced[-1][1] == project_root

    controller.close_all()

    assert controller.thumbnail_window is None
    assert controller.media_carousel_window is None
    assert controller.free_tree_window is None


def test_project_lifecycle_controller_creates_project_and_loads_it(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    storage_roots = type("StorageRootsStub", (), {"projects_root": projects_root})()
    storage = ProjectStorageService()
    session = ProjectSession()
    loaded_paths: list[Path] = []

    settings_service = type(
        "SettingsWorkspaceStub",
        (),
        {"apply_projects_root": lambda _self, projects_root: type("StorageRootsStub", (), {"projects_root": projects_root})()},
    )()

    lifecycle = ProjectLifecycleController(
        project_window_controller=type(
            "ProjectWindowStub",
            (),
            {"load_project": lambda _self, path: loaded_paths.append(path) or session.set_state(project_root=path, blocks=[]) or True},
        )(),
        settings_workspace_service=settings_service,
        storage=storage,
        get_storage_roots=lambda: storage_roots,
        set_storage_roots=lambda roots: None,
        save_projects_root_path=lambda _path: None,
        set_storage_paths=lambda _roots: None,
        prompt_new_project_name=lambda: ("My Film Project", True),
        prompt_project_choice=lambda _items: ("", False),
        prompt_projects_root=lambda _current: "",
        show_open_project_info=lambda *_args: None,
        seed_workspace_structure_defaults=lambda project_path, storage=None: None,
    )

    lifecycle.create_new_project()

    assert loaded_paths
    assert loaded_paths[0].name.endswith(".sbcprj")
    assert loaded_paths[0].exists()


def test_project_lifecycle_controller_opens_project_from_selected_root(tmp_path: Path) -> None:
    initial_root = tmp_path / "projects_a"
    initial_root.mkdir(parents=True, exist_ok=True)
    selected_root = tmp_path / "projects_b"
    selected_root.mkdir(parents=True, exist_ok=True)
    project_path = selected_root / "project_b.sbcprj"
    storage = ProjectStorageService()
    storage.create_project(project_path, "Project B")
    storage_roots_holder = {"value": type("StorageRootsStub", (), {"projects_root": initial_root, "user_libraries_root": tmp_path / 'u', "application_libraries_root": tmp_path / 'a'})()}
    loaded_paths: list[Path] = []
    saved_roots: list[Path] = []

    settings_service = type(
        "SettingsWorkspaceStub",
        (),
        {
            "apply_projects_root": lambda _self, projects_root: type(
                "StorageRootsStub",
                (),
                {
                    "projects_root": projects_root.expanduser().resolve(),
                    "user_libraries_root": tmp_path / "u",
                    "application_libraries_root": tmp_path / "a",
                },
            )(),
        },
    )()

    lifecycle = ProjectLifecycleController(
        project_window_controller=type(
            "ProjectWindowStub",
            (),
            {"load_project": lambda _self, path: loaded_paths.append(path) or True},
        )(),
        settings_workspace_service=settings_service,
        storage=storage,
        get_storage_roots=lambda: storage_roots_holder["value"],
        set_storage_roots=lambda roots: storage_roots_holder.__setitem__("value", roots),
        save_projects_root_path=saved_roots.append,
        set_storage_paths=lambda _roots: None,
        prompt_new_project_name=lambda: ("", False),
        prompt_project_choice=lambda items: (items[0], True),
        prompt_projects_root=lambda _current: str(selected_root),
        show_open_project_info=lambda *_args: None,
        seed_workspace_structure_defaults=lambda project_path, storage=None: None,
    )

    lifecycle.open_project_from_dialog()

    assert loaded_paths == [project_path.resolve()]
    assert storage_roots_holder["value"].projects_root == selected_root.resolve()
    assert saved_roots == [selected_root.resolve()]
