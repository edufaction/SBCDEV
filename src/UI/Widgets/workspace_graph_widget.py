from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFocusEvent, QIcon, QMouseEvent, QNativeGestureEvent, QPainter, QPainterPath, QPen, QPixmap, QTransform, QWheelEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid as shiboken_is_valid

from domain import Block, BlockType, PortType
from UI.block_icon_resolver import block_icon_name
from UI.themes import active_theme_tokens_ref, initialize_widget_primitives, resolve_type_color, type_badge_label
from UI.Widgets.thumbnail_utils import extract_video_preview, load_image_safe, resolve_block_asset_path

_ICONS_DIR = Path(__file__).resolve().parents[2] / "icons"
_ICON_CACHE: dict[tuple[str, str], QIcon] = {}
GRAPH_BLOCK_MEDIA_WIDTH = 320.0
GRAPH_BLOCK_MEDIA_HEIGHT = 180.0
GRAPH_BLOCK_COMPACT_WIDTH = GRAPH_BLOCK_MEDIA_WIDTH / 2.0
GRAPH_BLOCK_COMPACT_HEIGHT = GRAPH_BLOCK_MEDIA_HEIGHT / 2.0
GRAPH_BLOCK_NOTE_WIDTH = 220.0
GRAPH_BLOCK_NOTE_HEIGHT = 180.0
GRAPH_BLOCK_NOTE_MIN_WIDTH = 180.0
GRAPH_BLOCK_NOTE_MIN_HEIGHT = 140.0
GRAPH_BLOCK_NOTE_MAX_WIDTH = 520.0
GRAPH_BLOCK_NOTE_MAX_HEIGHT = 420.0

_TARGET_PORTS = (PortType.IN, PortType.TOP, PortType.BOTTOM)
_PORT_COLORS: dict[PortType, str] = {
    PortType.IN: "#3fb950",
    PortType.OUT: "#f85149",
    PortType.TOP: "#58a6ff",
    PortType.BOTTOM: "#f2cc60",
}


def _icon_for(path: Path, color_hex: str) -> QIcon:
    key = (str(path), color_hex)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    if not path.exists():
        return QIcon()
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QIcon()

    icon = QIcon()
    tint = QColor(color_hex)
    for size in (16, 18, 20, 24):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), tint)
        painter.end()
        icon.addPixmap(pixmap)
    _ICON_CACHE[key] = icon
    return icon


def _is_compact_block(block: Block) -> bool:
    return block.type in {BlockType.TEXT, BlockType.PROMPT} or block.profile.strip().lower() == "preset"


def _is_note_block(block: Block) -> bool:
    return block.type == BlockType.TEXT and block.profile.strip().lower() == "note"


def _block_badge_label(block: Block) -> str:
    if _is_note_block(block):
        return "NOTE"
    return type_badge_label(block.type)


def _block_preview_text(block: Block) -> str:
    if _is_note_block(block):
        for value in (
            str(block.content.get("text", "") or ""),
            block.description or "",
            block.comment or "",
        ):
            if value.strip():
                return value.strip()
        return "Sticky note"
    return type_badge_label(block.type)


class _WorkspaceGraphView(QGraphicsView):
    delete_pressed = Signal()
    external_files_dropped = Signal(object, object)
    _MIN_SCALE = 0.08
    _MAX_SCALE = 20.0
    _INFINITE_SCENE_HALF = 1_000_000.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(
            QPainter.Antialiasing
            | QPainter.SmoothPixmapTransform
            | QPainter.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self._zoom_steps = 0
        self._set_infinite_scene_rect()

    @staticmethod
    def _file_paths_from_mime(event) -> list[str]:
        mime = event.mimeData()
        if mime is None:
            return []
        paths: list[str] = []
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            local = url.toLocalFile().strip()
            if local:
                paths.append(local)
        return paths

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.setFocus()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._file_paths_from_mime(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._file_paths_from_mime(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        file_paths = self._file_paths_from_mime(event)
        if file_paths:
            drop_point = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self.external_files_dropped.emit(file_paths, self.mapToScene(drop_point))
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt naming)
        # Natural interaction:
        # - pinch/native gestures handle zoom on trackpad
        # - wheel/trackpad scroll keeps default panning behavior
        # - Ctrl/Cmd + wheel remains a zoom shortcut
        if not (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        next_step = self._zoom_steps + (1 if delta > 0 else -1)
        if next_step < -20 or next_step > 20:
            event.accept()
            return
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        self._apply_zoom_factor(factor)
        self._zoom_steps = next_step
        event.accept()

    def event(self, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() == QEvent.NativeGesture:
            return self._handle_native_gesture(event)
        return super().event(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() in {Qt.Key_Delete, Qt.Key_Backspace}:
            focus_widget = QApplication.focusWidget()
            focus_item = self.scene().focusItem() if self.scene() is not None else None
            if (
                (focus_widget is not None and focus_widget not in {self, self.viewport()})
                or isinstance(focus_item, QGraphicsProxyWidget)
            ):
                super().keyPressEvent(event)
                return
            self.delete_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def reset_zoom_to_scene(self) -> None:
        scene = self.scene()
        if scene is None:
            return
        bounds = scene.itemsBoundingRect()
        if not bounds.isValid() or bounds.isNull():
            self._set_infinite_scene_rect()
            return
        padded = bounds.adjusted(-120, -80, 120, 80)
        self.resetTransform()
        self._zoom_steps = 0
        self.setSceneRect(padded)
        self.fitInView(padded, Qt.KeepAspectRatio)
        self._set_infinite_scene_rect(center=bounds.center())

    def _handle_native_gesture(self, event) -> bool:
        if not isinstance(event, QNativeGestureEvent):
            return super().event(event)
        gesture_type = event.gestureType()
        if gesture_type in {Qt.BeginNativeGesture, Qt.EndNativeGesture}:
            event.accept()
            return True
        if gesture_type == Qt.ZoomNativeGesture:
            value = float(event.value())
            factor = 1.0 + value
            if factor <= 0.0:
                factor = 0.01
            self._apply_zoom_factor(factor)
            event.accept()
            return True
        if gesture_type == Qt.PanNativeGesture:
            delta = event.delta() if hasattr(event, "delta") else QPointF()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return True
        return super().event(event)

    def _apply_zoom_factor(self, factor: float) -> None:
        if factor <= 0.0:
            return
        current_scale = max(0.0001, self.transform().m11())
        target_scale = max(self._MIN_SCALE, min(self._MAX_SCALE, current_scale * factor))
        effective = target_scale / current_scale
        if abs(effective - 1.0) < 1e-6:
            return
        self.scale(effective, effective)

    def _set_infinite_scene_rect(self, *, center: QPointF | None = None) -> None:
        half = self._INFINITE_SCENE_HALF
        self.setSceneRect(-half, -half, half * 2.0, half * 2.0)
        if center is not None:
            self.centerOn(center)


class _InlineNoteEditor(QPlainTextEdit):
    text_commit_requested = Signal(str)
    activated = Signal()

    def __init__(self, *, initial_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_committed_text = str(initial_text or "")
        self.setPlainText(self._last_committed_text)
        self.setPlaceholderText("Sticky note")
        self.setFrameStyle(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrapMode(self.wordWrapMode())
        self.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none; color: #3D3320; selection-background-color: rgba(61,51,32,0.18); }"
        )

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (Qt naming)
        self.activated.emit()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (Qt naming)
        super().focusOutEvent(event)
        self._commit_if_needed()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        self.activated.emit()
        super().mousePressEvent(event)

    def set_note_text(self, text: str) -> None:
        normalized = str(text or "")
        self._last_committed_text = normalized
        if self.toPlainText() != normalized:
            self.setPlainText(normalized)

    def _commit_if_needed(self) -> None:
        if not shiboken_is_valid(self):
            return
        try:
            normalized = self.toPlainText().strip()
        except RuntimeError:
            return
        if normalized == self._last_committed_text:
            return
        self._last_committed_text = normalized
        self.text_commit_requested.emit(normalized)


class _GraphBlockItem(QGraphicsObject):
    _MOVE_THRESHOLD = 3.0

    clicked = Signal(str)
    start_link_drag = Signal(str, object)
    link_drag_moved = Signal(object)
    link_drag_released = Signal(object)
    position_changed = Signal(str, object)
    move_finished = Signal(str, object)
    size_changed = Signal(str)
    resize_finished = Signal(str, float, float)
    note_text_commit_requested = Signal(str, str)

    def __init__(
        self,
        *,
        block: Block,
        pixmap: QPixmap | None,
        width: float,
        height: float,
        theme_tokens: dict[str, str],
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._block = block
        self._pixmap = pixmap
        self._rect = QRectF(0, 0, width, height)
        self._theme_tokens = dict(theme_tokens)
        self._profile_icon_name = block_icon_name(block)
        self._active = False
        self._hover_port: PortType | None = None
        self._dragging_link = False
        self._drag_start_pos = QPointF()
        self._moved_since_press = False
        self._suspend_position_signals = False
        self._resizing = False
        self._resize_start_scene_pos = QPointF()
        self._resize_start_size = QPointF(width, height)
        self._note_editor_proxy: QGraphicsProxyWidget | None = None
        self._note_editor: _InlineNoteEditor | None = None
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        if _is_note_block(self._block):
            self._install_note_editor()

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt naming)
        return QRectF(self._rect)

    def set_graph_position(self, position: QPointF) -> None:
        self._suspend_position_signals = True
        self.setPos(position)
        self._drag_start_pos = QPointF(self.pos())
        self._moved_since_press = False
        self._suspend_position_signals = False

    def set_hover_port(self, port: PortType | None) -> None:
        if self._hover_port == port:
            return
        self._hover_port = port
        self.update()

    def set_active(self, active: bool) -> None:
        normalized = bool(active)
        if self._active == normalized:
            return
        self._active = normalized
        self.setSelected(normalized)
        self.update()

    def connector_scene_pos(self, port: PortType) -> QPointF:
        return self.mapToScene(self._connector_pos(port))

    def connector_port_at_scene(
        self,
        scene_pos: QPointF,
        *,
        allowed_ports: tuple[PortType, ...],
        tolerance: float = 12.0,
    ) -> tuple[PortType | None, float]:
        local_pos = self.mapFromScene(scene_pos)
        tolerance_sq = tolerance * tolerance
        best_port: PortType | None = None
        best_distance_sq = float("inf")
        for port in allowed_ports:
            center = self._connector_pos(port)
            dx = center.x() - local_pos.x()
            dy = center.y() - local_pos.y()
            distance_sq = (dx * dx) + (dy * dy)
            if distance_sq <= tolerance_sq and distance_sq < best_distance_sq:
                best_port = port
                best_distance_sq = distance_sq
        return best_port, best_distance_sq

    def _connector_pos(self, port: PortType) -> QPointF:
        width = self._rect.width()
        height = self._rect.height()
        if port == PortType.OUT:
            return QPointF(width, height / 2.0)
        if port == PortType.TOP:
            return QPointF(width / 2.0, 0.0)
        if port == PortType.BOTTOM:
            return QPointF(width / 2.0, height)
        return QPointF(0.0, height / 2.0)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.LeftButton:
            if _is_note_block(self._block) and self._resize_handle_rect().contains(event.pos()):
                self._resizing = True
                self._resize_start_scene_pos = QPointF(event.scenePos())
                self._resize_start_size = QPointF(self._rect.width(), self._rect.height())
                self.clicked.emit(self._block.id)
                event.accept()
                return
            self._drag_start_pos = QPointF(self.pos())
            self._moved_since_press = False
            port, _distance = self.connector_port_at_scene(
                event.scenePos(),
                allowed_ports=(PortType.OUT,),
                tolerance=12.0,
            )
            if port == PortType.OUT:
                self._dragging_link = True
                self.start_link_drag.emit(self._block.id, self.connector_scene_pos(PortType.OUT))
                event.accept()
                return
            self.clicked.emit(self._block.id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if self._resizing:
            delta = event.scenePos() - self._resize_start_scene_pos
            self._set_size(
                width=self._resize_start_size.x() + delta.x(),
                height=self._resize_start_size.y() + delta.y(),
            )
            event.accept()
            return
        if self._dragging_link:
            self.link_drag_moved.emit(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if self._resizing:
            self._resizing = False
            self.resize_finished.emit(self._block.id, self._rect.width(), self._rect.height())
            event.accept()
            return
        if self._dragging_link:
            self._dragging_link = False
            self.link_drag_released.emit(event.scenePos())
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if not self._is_alive():
            return
        position = self._safe_scene_position()
        if position is None:
            return
        if not self._moved_since_press:
            self._restore_click_position_if_needed(position)
            position = self._safe_scene_position()
            if position is None:
                return
        if self._moved_since_press:
            self.move_finished.emit(self._block.id, position)
            if not self._is_alive():
                return
        self._drag_start_pos = position
        self._moved_since_press = False

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # noqa: N802 (Qt naming)
        result = super().itemChange(change, value)
        if change == QGraphicsItem.ItemPositionHasChanged and not self._suspend_position_signals and self._is_alive():
            position = self._safe_scene_position()
            if position is None:
                return result
            self._moved_since_press = (position - self._drag_start_pos).manhattanLength() > self._MOVE_THRESHOLD
            self.position_changed.emit(self._block.id, position)
        return result

    def _restore_click_position_if_needed(self, position: QPointF) -> None:
        if (position - self._drag_start_pos).manhattanLength() > self._MOVE_THRESHOLD:
            return
        if position == self._drag_start_pos:
            return
        self._suspend_position_signals = True
        self.setPos(self._drag_start_pos)
        self._suspend_position_signals = False

    def _safe_scene_position(self) -> QPointF | None:
        if not self._is_alive():
            return None
        try:
            return QPointF(self.pos())
        except RuntimeError:
            return None

    def _is_alive(self) -> bool:
        try:
            return bool(shiboken_is_valid(self))
        except Exception:
            return False

    def paint(self, painter: QPainter, _option, _widget=None) -> None:  # noqa: N802 (Qt naming)
        tokens = self._theme_tokens
        base_type_color = resolve_type_color(self._block.type, tokens=tokens)
        border_color = QColor(tokens.get("outline_20", "#3b3f47"))
        panel_color = QColor(tokens.get("surface_container_high", "#2b2e35"))
        text_color = QColor(tokens.get("on_surface", "#f9f9fd"))
        muted_text_color = QColor(tokens.get("on_surface_variant", "#aaabaf"))
        is_note = _is_note_block(self._block)
        note_fill_color = QColor("#F6E27A")
        note_fold_color = QColor("#E6CC57")
        note_border_color = QColor("#B89C31")
        note_text_color = QColor("#3D3320")
        active_outline_color = QColor(tokens.get("primary", "#8dacff"))
        active_fill_color = QColor(tokens.get("primary", "#8dacff"))
        active_fill_color.setAlpha(28)

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        frame_rect = self._rect.adjusted(1, 1, -1, -1)
        if is_note:
            painter.setPen(QPen(note_border_color, 1.2))
            painter.setBrush(note_fill_color)
            painter.drawRoundedRect(frame_rect, 8.0, 8.0)

            fold_size = min(28.0, frame_rect.width() * 0.18)
            fold_path = QPainterPath()
            fold_path.moveTo(frame_rect.right() - fold_size, frame_rect.top())
            fold_path.lineTo(frame_rect.right(), frame_rect.top())
            fold_path.lineTo(frame_rect.right(), frame_rect.top() + fold_size)
            fold_path.closeSubpath()
            painter.fillPath(fold_path, note_fold_color)
            painter.setPen(QPen(note_border_color, 1.0))
            painter.drawLine(
                QPointF(frame_rect.right() - fold_size, frame_rect.top()),
                QPointF(frame_rect.right(), frame_rect.top() + fold_size),
            )
        else:
            painter.setPen(QPen(border_color, 1.0))
            painter.setBrush(panel_color)
            painter.drawRoundedRect(frame_rect, 10.0, 10.0)
        if self._active:
            highlight_rect = frame_rect.adjusted(-2.0, -2.0, 2.0, 2.0)
            painter.setPen(QPen(active_outline_color, 2.2))
            painter.setBrush(active_fill_color)
            painter.drawRoundedRect(highlight_rect, 9.0 if is_note else 11.0, 9.0 if is_note else 11.0)

        if self._block.is_link():
            link_badge = frame_rect.adjusted(10, 28, -10, -6)
            painter.setPen(QColor(tokens.get("warning", "#f59f00")))
            painter.drawText(link_badge, Qt.AlignTop | Qt.AlignLeft, "LINK")

        icon_color = note_text_color.name() if is_note else base_type_color.name()
        profile_icon = _icon_for(_ICONS_DIR / self._profile_icon_name, icon_color)
        if not profile_icon.isNull():
            icon_pixmap = profile_icon.pixmap(QSize(18, 18))
            painter.drawPixmap(int(frame_rect.x() + 8.0), int(frame_rect.y() + 8.0), icon_pixmap)

        content_rect = frame_rect.adjusted(8, 8, -8, -32)
        if is_note:
            pass
        elif self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                int(max(1.0, content_rect.width())),
                int(max(1.0, content_rect.height())),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            x = content_rect.x() + ((content_rect.width() - scaled.width()) / 2.0)
            y = content_rect.y() + ((content_rect.height() - scaled.height()) / 2.0)
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            painter.setPen(muted_text_color)
            painter.drawText(
                content_rect,
                Qt.AlignCenter | Qt.TextWordWrap,
                _block_badge_label(self._block),
            )

        name_rect = QRectF(frame_rect.x() + 8.0, frame_rect.bottom() - 22.0, frame_rect.width() - 16.0, 16.0)
        painter.setPen(note_text_color if is_note else text_color)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, self._block.name or self._block.id)

        badge_rect = frame_rect.adjusted(8, 8, -8, -8)
        painter.setPen(QColor("#6C5609") if is_note else base_type_color)
        painter.drawText(badge_rect, Qt.AlignTop | Qt.AlignRight, _block_badge_label(self._block))

        connector_outline = QColor(tokens.get("surface_container_highest", "#23262a"))
        radius = 5.0 if frame_rect.width() >= 240.0 else 4.0
        for port, color_value in _PORT_COLORS.items():
            center = self._connector_pos(port)
            if self._hover_port == port:
                painter.setPen(QPen(QColor(tokens.get("primary", "#8dacff")), 1.6))
                painter.setBrush(QColor(color_value).lighter(115))
                painter.drawEllipse(center, radius + 2.2, radius + 2.2)
            painter.setPen(QPen(connector_outline, 1.0))
            painter.setBrush(QColor(color_value))
            painter.drawEllipse(center, radius, radius)
        if is_note:
            self._paint_resize_handle(painter, frame_rect)

    def _paint_resize_handle(self, painter: QPainter, frame_rect: QRectF) -> None:
        handle_rect = self._resize_handle_rect().translated(frame_rect.topLeft())
        painter.setPen(QPen(QColor("#8A7222"), 1.2))
        painter.drawLine(handle_rect.left() + 4.0, handle_rect.bottom() - 4.0, handle_rect.right() - 4.0, handle_rect.top() + 4.0)
        painter.drawLine(handle_rect.left() + 8.0, handle_rect.bottom() - 4.0, handle_rect.right() - 4.0, handle_rect.top() + 8.0)

    def _install_note_editor(self) -> None:
        editor = _InlineNoteEditor(initial_text=str(self._block.content.get("text", "") or ""))
        editor.activated.connect(lambda: self.clicked.emit(self._block.id))
        editor.text_commit_requested.connect(lambda text: self._note_text_commit_requested(text))
        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(editor)
        proxy.setZValue(1.0)
        self._note_editor = editor
        self._note_editor_proxy = proxy
        self._update_note_editor_geometry()

    def _note_text_commit_requested(self, text: str) -> None:
        self._block.content["text"] = text
        self.note_text_commit_requested.emit(self._block.id, text)

    def _update_note_editor_geometry(self) -> None:
        if self._note_editor_proxy is None:
            return
        self._note_editor_proxy.setGeometry(self._note_content_rect())

    def _note_content_rect(self) -> QRectF:
        frame_rect = self._rect.adjusted(1, 1, -1, -1)
        return frame_rect.adjusted(16.0, 28.0, -16.0, -38.0)

    def _resize_handle_rect(self) -> QRectF:
        size = 18.0
        return QRectF(self._rect.width() - size - 6.0, self._rect.height() - size - 6.0, size, size)

    def _set_size(self, *, width: float, height: float) -> None:
        bounded_width = min(max(width, GRAPH_BLOCK_NOTE_MIN_WIDTH), GRAPH_BLOCK_NOTE_MAX_WIDTH)
        bounded_height = min(max(height, GRAPH_BLOCK_NOTE_MIN_HEIGHT), GRAPH_BLOCK_NOTE_MAX_HEIGHT)
        if abs(self._rect.width() - bounded_width) < 0.1 and abs(self._rect.height() - bounded_height) < 0.1:
            return
        self.prepareGeometryChange()
        self._rect = QRectF(0, 0, bounded_width, bounded_height)
        self._update_note_editor_geometry()
        self.update()
        self.size_changed.emit(self._block.id)


class _GraphEdgeItem(QGraphicsPathItem):
    def __init__(
        self,
        *,
        path: QPainterPath,
        source_block_id: str,
        target_block_id: str,
        port: PortType,
        name: str,
        color: QColor,
    ) -> None:
        super().__init__(path)
        self.source_block_id = source_block_id
        self.target_block_id = target_block_id
        self.port = port
        self.name = name
        self._color = QColor(color)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(-10.0)
        self._hovered = False

    def hoverEnterEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        self._hovered = False
        self.update()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:  # noqa: N802 (Qt naming)
        width = 2.0
        if self.isSelected():
            width = 3.2
        elif self._hovered:
            width = 2.6
        color = QColor(self._color)
        color.setAlpha(220 if self.isSelected() else 185)
        self.setPen(QPen(color, width))
        super().paint(painter, option, widget)


class WorkspaceGraphWidget(QWidget):
    """Generic graph projection for a selected container with link interactions."""

    node_selected = Signal(str)
    link_create_requested = Signal(str, str, str, str, str)
    link_delete_requested = Signal(str, str, str, str, str)
    graph_block_move_requested = Signal(str, str, float, float)
    graph_block_resize_requested = Signal(str, str, float, float)
    graph_layout_initialize_requested = Signal(str, object)
    graph_files_drop_requested = Signal(str, str, object, float, float)
    block_update_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panelAlt", True)
        self._theme_tokens = dict(active_theme_tokens_ref())
        self._project_root: Path | None = None
        self._blocks: list[Block] = []
        self._blocks_by_id: dict[str, Block] = {}
        self._active_container_id: str = ""
        self._active_block_id: str = ""
        self._block_items: dict[str, _GraphBlockItem] = {}
        self._edge_items_by_block_id: dict[str, list[_GraphEdgeItem]] = {}
        self._status = QLabel("Select a container to display its graph.", self)
        self._status.setProperty("muted", True)
        self._status.setProperty("technical", True)
        self._view = _WorkspaceGraphView(self)
        self._view.delete_pressed.connect(self._delete_selected_links)
        self._view.external_files_dropped.connect(self._on_external_files_dropped)

        self._drag_source_block_id: str = ""
        self._drag_start_scene_pos = QPointF()
        self._drag_preview_item: QGraphicsPathItem | None = None
        self._drag_candidate_block_id: str = ""
        self._drag_candidate_port: PortType | None = None
        self._drag_candidate_valid = False

        title = QLabel("CONTAINER GRAPH", self)
        title.setProperty("section", True)
        self._fit_view_button = QPushButton("", self)
        self._fit_view_button.setProperty("ghost", True)
        self._fit_view_button.setProperty("iconOnly", True)
        self._fit_view_button.setToolTip("Fit graph to view")
        self._fit_view_button.setAccessibleName("Fit graph to view")
        self._fit_view_button.setIcon(
            _icon_for(
                _ICONS_DIR / "navigation_arrows_maximize.svg",
                self._theme_tokens.get("on_surface", "#f3f5f8"),
            )
        )
        self._fit_view_button.setIconSize(QSize(16, 16))
        self._fit_view_button.clicked.connect(self.reset_view_to_scene)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(9)
        header_layout.addWidget(title, 0, Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addStretch(1)
        header_layout.addWidget(self._fit_view_button, 0, Qt.AlignRight | Qt.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(9)
        layout.addWidget(header)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._status)
        initialize_widget_primitives(self)

    def set_blocks(self, blocks: list[Block], *, project_root: Path | None) -> None:
        self._blocks = list(blocks)
        self._blocks_by_id = {block.id: block for block in self._blocks}
        self._project_root = project_root
        self._rebuild_scene()

    def set_active_container(self, container_id: str | None) -> None:
        normalized = str(container_id or "").strip()
        if normalized == self._active_container_id:
            return
        self._active_container_id = normalized
        self._rebuild_scene()

    def active_container_id(self) -> str:
        return self._active_container_id

    def set_active_block(self, block_id: str | None) -> None:
        self._active_block_id = str(block_id or "").strip()
        self._apply_active_block_selection()

    def reset_view_to_scene(self) -> None:
        self._view.reset_zoom_to_scene()

    def _schedule_graph_layout_initialization(self, positions: list[tuple[str, float, float]]) -> None:
        if not positions or not self._active_container_id:
            return
        container_id = self._active_container_id
        payload = [tuple(item) for item in positions]
        QTimer.singleShot(0, lambda: self._emit_graph_layout_initialization(container_id, payload))

    def _emit_graph_layout_initialization(self, container_id: str, payload: list[tuple[str, float, float]]) -> None:
        if not shiboken_is_valid(self):
            return
        if container_id != self._active_container_id:
            return
        self.graph_layout_initialize_requested.emit(container_id, payload)

    def _on_external_files_dropped(self, file_paths: object, scene_pos: object) -> None:
        if not self._active_container_id:
            return
        if not isinstance(file_paths, list) or not isinstance(scene_pos, QPointF):
            return
        target_block_id = self._block_id_at_scene_pos(scene_pos)
        self.graph_files_drop_requested.emit(
            self._active_container_id,
            target_block_id,
            list(file_paths),
            float(scene_pos.x()),
            float(scene_pos.y()),
        )

    def _rebuild_scene(self) -> None:
        scene = self._view.scene()
        if scene is None:
            scene = QGraphicsScene(self._view)
            self._view.setScene(scene)
        preserved_view_state = self._capture_view_state()
        self._reset_drag_state()
        scene.clear()
        self._block_items = {}
        self._edge_items_by_block_id = {}

        if not self._active_container_id:
            self._active_block_id = ""
            self._status.setText("Select a container to display its graph.")
            return

        container = self._blocks_by_id.get(self._active_container_id)
        if container is None:
            self._active_block_id = ""
            self._status.setText(f"Container not found: {self._active_container_id}")
            return
        if container.type != BlockType.CONTAINER:
            self._active_block_id = ""
            self._status.setText(f"Selected block is not a container: {container.name or container.id}")
            return

        positioned_nodes: dict[str, object] = {}
        if container.graph is not None:
            for node in container.graph.nodes.values():
                block = self._blocks_by_id.get(node.block_id)
                if block is None:
                    continue
                positioned_nodes[block.id] = node

        auto_index = 0
        missing_positions: list[tuple[str, float, float]] = []
        for child_id in container.contains:
            if child_id in positioned_nodes:
                continue
            child = self._blocks_by_id.get(child_id)
            if child is None:
                continue
            auto_position = self._auto_layout_position(auto_index)
            positioned_nodes[child.id] = type("_AutoNode", (), {"x": auto_position.x(), "y": auto_position.y(), "width": 0.0, "height": 0.0})()
            missing_positions.append((child.id, float(auto_position.x()), float(auto_position.y())))
            auto_index += 1

        for block_id, graph_node in positioned_nodes.items():
            block = self._blocks_by_id.get(block_id)
            if block is None:
                continue
            width, height = self._block_size(block, graph_node)
            item = _GraphBlockItem(
                block=block,
                pixmap=self._load_block_pixmap(block),
                width=width,
                height=height,
                theme_tokens=self._theme_tokens,
            )
            item.set_graph_position(QPointF(float(graph_node.x), float(graph_node.y)))
            item.clicked.connect(self.set_active_block)
            item.clicked.connect(self.node_selected.emit)
            item.start_link_drag.connect(self._on_start_link_drag)
            item.link_drag_moved.connect(self._on_link_drag_moved)
            item.link_drag_released.connect(self._on_link_drag_released)
            item.position_changed.connect(self._on_block_position_changed)
            item.move_finished.connect(self._on_block_move_finished)
            item.size_changed.connect(self._on_block_size_changed)
            item.resize_finished.connect(self._on_block_resize_finished)
            item.note_text_commit_requested.connect(self._on_note_text_commit_requested)
            scene.addItem(item)
            self._block_items[block.id] = item
        self._apply_active_block_selection()

        visible_edges = 0
        for source_block_id, target_block_id, port, name in self._iter_business_connections(container):
            source_item = self._block_items.get(source_block_id)
            target_item = self._block_items.get(target_block_id)
            if source_item is None or target_item is None:
                continue
            source_point = source_item.connector_scene_pos(PortType.OUT)
            target_point = target_item.connector_scene_pos(port)
            path = self._edge_path(source_point=source_point, target_point=target_point, port=port)
            color = QColor(_PORT_COLORS.get(port, "#8dacff"))
            edge_item = _GraphEdgeItem(
                path=path,
                source_block_id=source_block_id,
                target_block_id=target_block_id,
                port=port,
                name=name,
                color=color,
            )
            scene.addItem(edge_item)
            self._register_edge_item(edge_item)
            visible_edges += 1

        if self._block_items:
            if not self._restore_view_state(preserved_view_state):
                self._view.reset_zoom_to_scene()
            if missing_positions:
                self._schedule_graph_layout_initialization(missing_positions)
            self._status.setText(
                f"{len(self._block_items)} node(s), {visible_edges} edge(s) in '{container.name or container.id}'."
            )
            return

        self._status.setText(f"Container '{container.name or container.id}' has no graph block to display.")

    def _iter_business_connections(self, container: Block) -> list[tuple[str, str, PortType, str]]:
        results: list[tuple[str, str, PortType, str]] = []
        contained_ids = {child_id for child_id in container.contains}
        for target_id in container.contains:
            target_block = self._blocks_by_id.get(target_id)
            if target_block is None:
                continue
            for item in sorted(target_block.inputs, key=lambda input_item: (input_item.order, input_item.name)):
                if not item.enabled:
                    continue
                if item.source_block_id not in contained_ids:
                    continue
                results.append((item.source_block_id, target_block.id, item.port, item.name))
        return results

    def _block_id_at_scene_pos(self, scene_pos: QPointF) -> str:
        scene = self._view.scene()
        if scene is None:
            return ""
        for item in scene.items(scene_pos):
            if isinstance(item, _GraphBlockItem):
                return item._block.id
        return ""

    def _on_start_link_drag(self, source_block_id: str, source_scene_pos: QPointF) -> None:
        if not self._active_container_id:
            return
        self._reset_drag_state()
        scene = self._view.scene()
        if scene is None:
            return
        self._drag_source_block_id = source_block_id
        self._drag_start_scene_pos = QPointF(source_scene_pos)
        path = QPainterPath(self._drag_start_scene_pos)
        path.lineTo(self._drag_start_scene_pos)
        preview = QGraphicsPathItem(path)
        preview_pen = QPen(QColor(self._theme_tokens.get("primary", "#8dacff")), 2.0, Qt.DashLine)
        preview.setPen(preview_pen)
        preview.setZValue(20.0)
        scene.addItem(preview)
        self._drag_preview_item = preview

    def _on_block_position_changed(self, block_id: str, _position: QPointF) -> None:
        self._refresh_edges_for_block(block_id)

    def _on_block_size_changed(self, block_id: str) -> None:
        self._refresh_edges_for_block(block_id)

    def _on_block_move_finished(self, block_id: str, position: QPointF) -> None:
        if not self._active_container_id:
            return
        self.graph_block_move_requested.emit(
            self._active_container_id,
            block_id,
            float(position.x()),
            float(position.y()),
        )

    def _on_block_resize_finished(self, block_id: str, width: float, height: float) -> None:
        if not self._active_container_id:
            return
        self.graph_block_resize_requested.emit(self._active_container_id, block_id, float(width), float(height))

    def _on_note_text_commit_requested(self, block_id: str, text: str) -> None:
        self.block_update_requested.emit({"block_id": block_id, "text_content": text})

    def _apply_active_block_selection(self) -> None:
        active_id = self._active_block_id.strip()
        has_active_item = False
        for block_id, item in self._block_items.items():
            is_active = bool(active_id) and block_id == active_id
            item.set_active(is_active)
            has_active_item = has_active_item or is_active
        if active_id and not has_active_item:
            self._active_block_id = ""

    def _on_link_drag_moved(self, scene_pos: QPointF) -> None:
        if not self._drag_source_block_id or self._drag_preview_item is None:
            return
        target_id, target_port, valid = self._resolve_hover_target(scene_pos)
        self._drag_candidate_block_id = target_id
        self._drag_candidate_port = target_port
        self._drag_candidate_valid = valid
        self._apply_hover_feedback(target_id=target_id, port=target_port if valid else None)
        self._update_drag_preview(scene_pos=scene_pos, valid=valid, hovering_connector=bool(target_port))

    def _on_link_drag_released(self, scene_pos: QPointF) -> None:
        if not self._drag_source_block_id:
            self._reset_drag_state()
            return
        self._on_link_drag_moved(scene_pos)
        if self._drag_candidate_valid and self._drag_candidate_port is not None and self._drag_candidate_block_id:
            self.link_create_requested.emit(
                self._active_container_id,
                self._drag_source_block_id,
                self._drag_candidate_block_id,
                self._drag_candidate_port.value,
                "",
            )
        self._reset_drag_state()

    def _resolve_hover_target(self, scene_pos: QPointF) -> tuple[str, PortType | None, bool]:
        best_block_id = ""
        best_port: PortType | None = None
        best_distance = float("inf")
        for block_id, item in self._block_items.items():
            if block_id == self._drag_source_block_id:
                continue
            port, distance = item.connector_port_at_scene(scene_pos, allowed_ports=_TARGET_PORTS, tolerance=12.0)
            if port is None:
                continue
            if distance < best_distance:
                best_distance = distance
                best_block_id = block_id
                best_port = port
        if not best_block_id or best_port is None:
            return "", None, False
        return best_block_id, best_port, self._is_port_candidate_valid(best_block_id, best_port)

    def _is_port_candidate_valid(self, target_block_id: str, port: PortType) -> bool:
        source_block = self._blocks_by_id.get(self._drag_source_block_id)
        target_block = self._blocks_by_id.get(target_block_id)
        if source_block is None or target_block is None:
            return False
        if source_block.id == target_block.id:
            return False
        source_profile = source_block.profile.strip().lower()
        if port == PortType.TOP and source_profile != "preset":
            return False
        if port == PortType.BOTTOM and not (
            source_block.type == BlockType.PROMPT or source_profile == "prompt"
        ):
            return False
        if port in {PortType.TOP, PortType.BOTTOM}:
            for existing in target_block.inputs:
                if existing.port != port:
                    continue
                if existing.source_block_id == source_block.id and existing.name == "":
                    continue
                return False
        for existing in target_block.inputs:
            if (
                existing.source_block_id == source_block.id
                and existing.port == port
                and existing.name == ""
            ):
                return False
        return True

    def _apply_hover_feedback(self, *, target_id: str, port: PortType | None) -> None:
        for block_id, item in self._block_items.items():
            if block_id == target_id:
                item.set_hover_port(port)
            else:
                item.set_hover_port(None)

    def _update_drag_preview(self, *, scene_pos: QPointF, valid: bool, hovering_connector: bool) -> None:
        if self._drag_preview_item is None:
            return
        control_offset = max(40.0, abs(scene_pos.x() - self._drag_start_scene_pos.x()) * 0.4)
        path = QPainterPath(self._drag_start_scene_pos)
        path.cubicTo(
            QPointF(self._drag_start_scene_pos.x() + control_offset, self._drag_start_scene_pos.y()),
            QPointF(scene_pos.x() - control_offset, scene_pos.y()),
            scene_pos,
        )
        self._drag_preview_item.setPath(path)
        if valid:
            color = QColor(self._theme_tokens.get("success", "#40c057"))
        elif hovering_connector:
            color = QColor(self._theme_tokens.get("error_dim", "#d73357"))
        else:
            color = QColor(self._theme_tokens.get("primary", "#8dacff"))
        self._drag_preview_item.setPen(QPen(color, 2.0, Qt.DashLine))

    def _delete_selected_links(self) -> None:
        if not self._active_container_id:
            return
        scene = self._view.scene()
        if scene is None:
            return
        selected_edges = [item for item in scene.selectedItems() if isinstance(item, _GraphEdgeItem)]
        for edge in selected_edges:
            self.link_delete_requested.emit(
                self._active_container_id,
                edge.source_block_id,
                edge.target_block_id,
                edge.port.value,
                edge.name,
            )

    def _capture_view_state(self) -> dict[str, object] | None:
        scene = self._view.scene()
        if scene is None or not self._active_container_id:
            return None
        return {
            "container_id": self._active_container_id,
            "transform": QTransform(self._view.transform()),
            "horizontal_scroll": int(self._view.horizontalScrollBar().value()),
            "vertical_scroll": int(self._view.verticalScrollBar().value()),
        }

    def _restore_view_state(self, state: dict[str, object] | None) -> bool:
        if not state:
            return False
        if state.get("container_id") != self._active_container_id:
            return False
        transform = state.get("transform")
        horizontal_scroll = state.get("horizontal_scroll")
        vertical_scroll = state.get("vertical_scroll")
        if (
            not isinstance(transform, QTransform)
            or not isinstance(horizontal_scroll, int)
            or not isinstance(vertical_scroll, int)
        ):
            return False
        self._view.setTransform(transform)
        self._view._set_infinite_scene_rect()
        self._view.horizontalScrollBar().setValue(horizontal_scroll)
        self._view.verticalScrollBar().setValue(vertical_scroll)
        return True

    def _register_edge_item(self, edge_item: _GraphEdgeItem) -> None:
        self._edge_items_by_block_id.setdefault(edge_item.source_block_id, []).append(edge_item)
        self._edge_items_by_block_id.setdefault(edge_item.target_block_id, []).append(edge_item)

    def _refresh_edges_for_block(self, block_id: str) -> None:
        for edge_item in self._edge_items_by_block_id.get(block_id, []):
            self._refresh_edge_item(edge_item)

    def _refresh_edge_item(self, edge_item: _GraphEdgeItem) -> None:
        source_item = self._block_items.get(edge_item.source_block_id)
        target_item = self._block_items.get(edge_item.target_block_id)
        if source_item is None or target_item is None:
            return
        source_point = source_item.connector_scene_pos(PortType.OUT)
        target_point = target_item.connector_scene_pos(edge_item.port)
        path = self._edge_path(source_point=source_point, target_point=target_point, port=edge_item.port)
        edge_item.setPath(path)

    @staticmethod
    def _edge_path(*, source_point: QPointF, target_point: QPointF, port: PortType) -> QPainterPath:
        dx = target_point.x() - source_point.x()
        dy = target_point.y() - source_point.y()
        horizontal_control = max(40.0, abs(dx) * 0.4)
        vertical_control = max(40.0, abs(dy) * 0.4)
        source_control = QPointF(source_point.x() + horizontal_control, source_point.y())
        if port == PortType.TOP:
            target_control = QPointF(target_point.x(), target_point.y() - vertical_control)
        elif port == PortType.BOTTOM:
            target_control = QPointF(target_point.x(), target_point.y() + vertical_control)
        else:
            target_control = QPointF(target_point.x() - horizontal_control, target_point.y())
        path = QPainterPath(source_point)
        path.cubicTo(source_control, target_control, target_point)
        return path

    def _reset_drag_state(self) -> None:
        scene = self._view.scene()
        preview_item = self._drag_preview_item
        if scene is not None and preview_item is not None:
            try:
                scene.removeItem(preview_item)
            except RuntimeError:
                pass
        self._drag_preview_item = None
        self._drag_source_block_id = ""
        self._drag_start_scene_pos = QPointF()
        self._drag_candidate_block_id = ""
        self._drag_candidate_port = None
        self._drag_candidate_valid = False
        for item in self._block_items.values():
            item.set_hover_port(None)

    @staticmethod
    def _block_size(block: Block, graph_node: object | None = None) -> tuple[float, float]:
        if _is_note_block(block):
            node_width = float(getattr(graph_node, "width", 0.0) or 0.0)
            node_height = float(getattr(graph_node, "height", 0.0) or 0.0)
            width = node_width if node_width > 0.0 else GRAPH_BLOCK_NOTE_WIDTH
            height = node_height if node_height > 0.0 else GRAPH_BLOCK_NOTE_HEIGHT
            return width, height
        if _is_compact_block(block):
            return GRAPH_BLOCK_COMPACT_WIDTH, GRAPH_BLOCK_COMPACT_HEIGHT
        return GRAPH_BLOCK_MEDIA_WIDTH, GRAPH_BLOCK_MEDIA_HEIGHT

    @staticmethod
    def _auto_layout_position(index: int) -> QPointF:
        columns = 3
        row = index // columns
        col = index % columns
        x = 40.0 + (col * (GRAPH_BLOCK_MEDIA_WIDTH + 56.0))
        y = 40.0 + (row * (GRAPH_BLOCK_MEDIA_HEIGHT + 48.0))
        return QPointF(x, y)

    def _load_block_pixmap(self, block: Block) -> QPixmap | None:
        if block.type not in {BlockType.IMAGE, BlockType.VIDEO}:
            return None
        media_path = resolve_block_asset_path(block, self._project_root)
        if media_path is None:
            return None

        if block.type == BlockType.IMAGE:
            image = load_image_safe(media_path)
            if image is None:
                return None
            return QPixmap.fromImage(image)

        image = load_image_safe(media_path)
        if image is not None:
            return QPixmap.fromImage(image)
        preview_path = extract_video_preview(media_path, project_root=self._project_root)
        if preview_path is None:
            return None
        preview_image = load_image_safe(preview_path)
        if preview_image is None:
            return None
        return QPixmap.fromImage(preview_image)
