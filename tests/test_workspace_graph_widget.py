import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QGraphicsItem

from application import UseCaseService
from domain import Block, BlockType, FreeGraph, FreeGraphEdge, FreeGraphNode, InputConnection, PortType
from infrastructure.repositories import BlockRepository
from infrastructure.storage import ProjectStorageService
from UI.Frames import CharacterWorkspacePanel, StoryWorkspacePanel
from UI.Widgets import WorkspaceGraphWidget
from services import BlockService


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _sample_graph_blocks() -> tuple[Block, Block, Block]:
    image = Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1")
    text = Block(
        id="txt_1",
        type=BlockType.TEXT,
        profile="preset",
        name="Preset 1",
        inputs=[InputConnection(source_block_id=image.id, port=PortType.IN, name="ref")],
    )
    container = Block(
        id="cnt_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        contains=[image.id, text.id],
        graph=FreeGraph(
            nodes={
                "n1": FreeGraphNode(id="n1", block_id=image.id, x=40.0, y=80.0),
                "n2": FreeGraphNode(id="n2", block_id=text.id, x=460.0, y=120.0),
            },
            edges={
                "e1": FreeGraphEdge(id="e1", source_node_id="n1", target_node_id="n2", label="ref"),
            },
        ),
    )
    return container, image, text


def test_workspace_graph_widget_renders_nodes_and_edges_with_size_policy() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    scene = widget._view.scene()
    assert scene is not None
    block_items = [item for item in scene.items() if hasattr(item, "_block")]
    assert len(block_items) == 2

    widths = {
        item._block.id: round(item.boundingRect().width())  # type: ignore[attr-defined]
        for item in block_items
    }
    assert widths["img_1"] == 320
    assert widths["txt_1"] == 160
    assert "2 node(s), 1 edge(s)" in widget._status.text()


def test_workspace_graph_widget_uses_postit_size_for_note_blocks() -> None:
    app = _app()
    note = Block(id="note_1", type=BlockType.TEXT, profile="note", name="Note 1", content={"text": "Beat idea"})
    container = Block(
        id="cnt_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        contains=[note.id],
        graph=FreeGraph(
            nodes={
                "n1": FreeGraphNode(id="n1", block_id=note.id, x=40.0, y=80.0),
            }
        ),
    )
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, note], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    note_item = widget._block_items["note_1"]
    assert round(note_item.boundingRect().width()) == 220
    assert round(note_item.boundingRect().height()) == 180


def test_workspace_graph_widget_displays_contained_blocks_without_graph_nodes() -> None:
    app = _app()
    image = Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1")
    prompt = Block(id="pr_1", type=BlockType.PROMPT, profile="prompt", name="Prompt 1")
    container = Block(
        id="cnt_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        contains=[image.id, prompt.id],
        graph=FreeGraph(),
    )
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, prompt], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    scene = widget._view.scene()
    assert scene is not None
    block_items = [item for item in scene.items() if hasattr(item, "_block")]
    assert len(block_items) == 2
    assert "2 node(s), 0 edge(s)" in widget._status.text()


def test_workspace_graph_widget_emits_layout_initialization_for_missing_positions() -> None:
    app = _app()
    image = Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1")
    prompt = Block(id="pr_1", type=BlockType.PROMPT, profile="prompt", name="Prompt 1")
    container = Block(
        id="cnt_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        contains=[image.id, prompt.id],
        graph=FreeGraph(),
    )
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    scheduled: list[tuple[str, object]] = []
    widget.graph_layout_initialize_requested.connect(lambda container_id, positions: scheduled.append((container_id, positions)))
    widget.set_blocks([container, image, prompt], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    assert scheduled
    container_id, positions = scheduled[-1]
    assert container_id == container.id
    assert positions == [("img_1", 40.0, 40.0), ("pr_1", 416.0, 40.0)]


def test_workspace_graph_widget_marks_nodes_movable_and_refreshes_edge_path_on_move() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    image_item = widget._block_items["img_1"]
    assert image_item.flags() & QGraphicsItem.ItemIsMovable

    scene = widget._view.scene()
    assert scene is not None
    edge_item = next(item for item in scene.items() if hasattr(item, "source_block_id"))
    old_start = edge_item.path().elementAt(0)

    image_item.setPos(180.0, 240.0)
    app.processEvents()

    new_start = edge_item.path().elementAt(0)
    assert (new_start.x, new_start.y) != (old_start.x, old_start.y)


def test_workspace_graph_widget_uses_expected_port_positions() -> None:
    app = _app()
    container, image, _text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    item = widget._block_items["img_1"]
    out_pos = item.connector_scene_pos(PortType.OUT)
    in_pos = item.connector_scene_pos(PortType.IN)
    top_pos = item.connector_scene_pos(PortType.TOP)
    bottom_pos = item.connector_scene_pos(PortType.BOTTOM)

    assert in_pos.x() < out_pos.x()
    assert top_pos.y() < in_pos.y()
    assert bottom_pos.y() > in_pos.y()


def test_workspace_graph_widget_link_creation_rebuild_does_not_crash_drag_preview_cleanup() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    widget.link_create_requested.connect(lambda *_args: widget.set_active_container(container.id))
    source_item = widget._block_items["img_1"]
    target_item = widget._block_items["txt_1"]

    widget._on_start_link_drag("img_1", source_item.connector_scene_pos(PortType.OUT))
    widget._on_link_drag_released(target_item.connector_scene_pos(PortType.IN))
    app.processEvents()

    assert widget._drag_preview_item is None


def test_workspace_graph_widget_move_release_rebuild_does_not_access_deleted_item() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    widget.graph_block_move_requested.connect(lambda *_args: widget.set_active_container(container.id))

    item = widget._block_items["img_1"]
    start = widget._view.mapFromScene(item.sceneBoundingRect().center())
    target = start + QPoint(80, 40)

    QTest.mousePress(widget._view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(widget._view.viewport(), target, delay=20)
    QTest.mouseRelease(widget._view.viewport(), Qt.LeftButton, Qt.NoModifier, target)
    app.processEvents()

    assert "img_1" in widget._block_items


def test_workspace_graph_widget_click_does_not_emit_block_move_request() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    moved: list[tuple[str, str, float, float]] = []
    widget.graph_block_move_requested.connect(lambda *args: moved.append(args))

    item = widget._block_items["img_1"]
    start = widget._view.mapFromScene(item.sceneBoundingRect().center())
    original_pos = QPointF(item.pos())

    QTest.mouseClick(widget._view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    app.processEvents()

    assert moved == []
    assert item.pos() == original_pos


def test_workspace_graph_widget_emits_file_drop_request_with_target_block() -> None:
    app = _app()
    placeholder = Block(id="slot_1", type=BlockType.EMPTY, profile="template_slot", name="Slot 1")
    container = Block(
        id="cnt_1",
        type=BlockType.CONTAINER,
        profile="character_form",
        name="Character Form",
        contains=[placeholder.id],
        graph=FreeGraph(
            nodes={
                "n1": FreeGraphNode(id="n1", block_id=placeholder.id, x=140.0, y=90.0),
            }
        ),
    )
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, placeholder], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    emitted: list[tuple[str, str, object, float, float]] = []
    widget.graph_files_drop_requested.connect(lambda *args: emitted.append(args))

    target_item = widget._block_items["slot_1"]
    scene_pos = target_item.sceneBoundingRect().center()
    widget._on_external_files_dropped(["/tmp/ref.png"], scene_pos)
    app.processEvents()

    assert emitted == [(container.id, placeholder.id, ["/tmp/ref.png"], float(scene_pos.x()), float(scene_pos.y()))]


def test_workspace_graph_widget_emits_file_drop_request_without_target_block_on_empty_area() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    emitted: list[tuple[str, str, object, float, float]] = []
    widget.graph_files_drop_requested.connect(lambda *args: emitted.append(args))

    scene_pos = QPointF(-500.0, -500.0)
    widget._on_external_files_dropped(["/tmp/ref.png"], scene_pos)
    app.processEvents()

    assert emitted == [(container.id, "", ["/tmp/ref.png"], -500.0, -500.0)]


def test_workspace_graph_widget_fit_button_resets_view_to_scene() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    widget._view.scale(2.0, 2.0)
    before = widget._view.transform().m11()

    widget._fit_view_button.click()
    app.processEvents()

    after = widget._view.transform().m11()
    assert after != before


def test_workspace_graph_widget_rebuild_preserves_scrollbar_viewport_exactly() -> None:
    app = _app()
    container, image, text = _sample_graph_blocks()
    widget = WorkspaceGraphWidget()
    widget.resize(900, 500)
    widget.set_blocks([container, image, text], project_root=None)
    widget.set_active_container(container.id)
    widget.show()
    app.processEvents()

    widget._view.horizontalScrollBar().setValue(widget._view.horizontalScrollBar().value() + 37)
    widget._view.verticalScrollBar().setValue(widget._view.verticalScrollBar().value() + 23)
    before_h = widget._view.horizontalScrollBar().value()
    before_v = widget._view.verticalScrollBar().value()

    widget.set_blocks([container, image, text], project_root=None)
    app.processEvents()

    assert widget._view.horizontalScrollBar().value() == before_h
    assert widget._view.verticalScrollBar().value() == before_v


def test_moving_graph_block_position_is_persisted_in_storage(tmp_path: Path) -> None:
    storage = ProjectStorageService()
    project_path = tmp_path / "demo.sbcprj"
    storage.create_project(project_path, "Demo")

    root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story Root",
        content={"workspace_role": "story_root"},
    )
    shot = Block(
        id="shot_1",
        type=BlockType.CONTAINER,
        profile="shot",
        name="Shot 1",
        contains=["img_1"],
        domain=root.domain,
        content={"workspace_role": "shot"},
        graph=FreeGraph(),
    )
    image = Block(id="img_1", type=BlockType.IMAGE, profile="asset", name="Image 1")
    root.contains.append(shot.id)
    blocks = [root, shot, image]

    repository = BlockRepository()
    use_case = UseCaseService(BlockService(repository))
    for block in blocks:
        repository.add(block)
    use_case.move_block_in_graph(shot.id, image.id, x=222.0, y=333.0)

    storage.save_blocks(project_path, blocks)
    reloaded = storage.load_blocks(project_path)
    reloaded_shot = next(block for block in reloaded if block.id == shot.id)
    assert reloaded_shot.graph is not None
    assert len(reloaded_shot.graph.nodes) == 1
    node = next(iter(reloaded_shot.graph.nodes.values()))
    assert node.block_id == image.id
    assert node.x == 222.0
    assert node.y == 333.0


def test_story_workspace_panel_updates_graph_container_from_tree_selection() -> None:
    _ = _app()
    root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story Root",
        contains=["cnt_1"],
        graph=FreeGraph(),
        content={"workspace_role": "story_root"},
    )
    container, image, text = _sample_graph_blocks()
    panel = StoryWorkspacePanel()
    panel.set_blocks([root, container, image, text], project_root=None)

    panel._on_tree_block_selected(image, container.id)
    assert panel._graph_widget.active_container_id() == container.id

    panel._on_tree_block_selected(root, "")
    assert panel._graph_widget.active_container_id() == root.id


def test_story_workspace_panel_same_container_tree_selection_does_not_rebuild_graph() -> None:
    app = _app()
    root = Block(
        id="blk_story_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Story Root",
        contains=["cnt_1"],
        graph=FreeGraph(),
        content={"workspace_role": "story_root"},
    )
    container, image, text = _sample_graph_blocks()
    panel = StoryWorkspacePanel()
    panel.set_blocks([root, container, image, text], project_root=None)
    panel.show()
    app.processEvents()

    panel._graph_widget.set_active_container(container.id)
    original_item = panel._graph_widget._block_items["img_1"]

    panel._on_tree_block_selected(image, container.id)
    app.processEvents()

    assert panel._graph_widget.active_container_id() == container.id
    assert panel._graph_widget._block_items["img_1"] is original_item


def test_character_workspace_panel_updates_graph_container_from_tree_selection() -> None:
    _ = _app()
    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        contains=["cnt_1"],
        graph=FreeGraph(),
        content={"workspace_role": "characters_root"},
    )
    container, image, text = _sample_graph_blocks()
    panel = CharacterWorkspacePanel()
    panel.set_blocks([root, container, image, text], project_root=None)

    panel._on_tree_block_selected(text, container.id)
    assert panel._graph_widget.active_container_id() == container.id

    panel._on_tree_block_selected(root, "")
    assert panel._graph_widget.active_container_id() == root.id


def test_character_workspace_panel_preserves_active_graph_container_on_set_blocks() -> None:
    _ = _app()
    root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        contains=["cnt_1"],
        graph=FreeGraph(),
        content={"workspace_role": "characters_root"},
    )
    container, image, text = _sample_graph_blocks()
    panel = CharacterWorkspacePanel()
    panel.set_blocks([root, container, image, text], project_root=None)
    panel._graph_widget.set_active_container(container.id)

    panel.set_blocks([root, container, image, text], project_root=None, active_container_id=container.id)

    assert panel._graph_widget.active_container_id() == container.id
