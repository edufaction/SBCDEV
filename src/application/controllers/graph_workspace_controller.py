from __future__ import annotations

from typing import Callable

from application.session import ProjectSession
from domain import ValidationError


class GraphWorkspaceController:
    """Transverse UI orchestration for graph interactions across workspaces."""

    def __init__(
        self,
        *,
        session: ProjectSession,
        persist_blocks: Callable[[object], None],
        set_feedback: Callable[[str, str], None],
    ) -> None:
        self._session = session
        self._persist_blocks = persist_blocks
        self._set_feedback = set_feedback

    def create_link(
        self,
        *,
        container_id: str,
        source_block_id: str,
        target_block_id: str,
        target_port: str,
        name: str,
    ) -> None:
        if self._session.project_root is None:
            self._set_feedback(container_id, "Open a project first.")
            return
        try:
            use_case = self._session.rebuild_use_case()
            use_case.connect_blocks(
                target_block_id=target_block_id,
                source_block_id=source_block_id,
                port=target_port,
                name=name,
                container_id=container_id,
            )
        except ValidationError as exc:
            self._set_feedback(container_id, str(exc))
            return
        except Exception:
            self._set_feedback(container_id, "Link creation failed.")
            return
        self._persist_blocks(self._session.blocks)
        self._set_feedback(container_id, f"Link added: {source_block_id} -> {target_block_id} ({target_port})")

    def delete_link(
        self,
        *,
        container_id: str,
        source_block_id: str,
        target_block_id: str,
        target_port: str,
        name: str,
    ) -> None:
        if self._session.project_root is None:
            self._set_feedback(container_id, "Open a project first.")
            return
        try:
            use_case = self._session.rebuild_use_case()
            use_case.disconnect_blocks(
                target_block_id=target_block_id,
                source_block_id=source_block_id,
                port=target_port,
                name=name or None,
                container_id=container_id,
            )
        except ValidationError as exc:
            self._set_feedback(container_id, str(exc))
            return
        except Exception:
            self._set_feedback(container_id, "Link deletion failed.")
            return
        self._persist_blocks(self._session.blocks)
        self._set_feedback(container_id, f"Link removed: {source_block_id} -> {target_block_id} ({target_port})")

    def move_block(self, *, container_id: str, block_id: str, x: float, y: float) -> None:
        if self._session.project_root is None:
            self._set_feedback(container_id, "Open a project first.")
            return
        try:
            use_case = self._session.rebuild_use_case()
            use_case.move_block_in_graph(container_id, block_id, x=x, y=y)
        except ValidationError as exc:
            self._set_feedback(container_id, str(exc))
            return
        except Exception:
            self._set_feedback(container_id, "Block move persistence failed.")
            return
        self._persist_blocks(self._session.blocks)

    def initialize_layout(self, *, container_id: str, positions: object) -> None:
        if self._session.project_root is None:
            return
        if not isinstance(positions, list) or not positions:
            return
        try:
            use_case = self._session.rebuild_use_case()
            for entry in positions:
                if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                    continue
                block_id = str(entry[0] or "").strip()
                try:
                    x = float(entry[1])
                    y = float(entry[2])
                except (TypeError, ValueError):
                    continue
                if not block_id:
                    continue
                use_case.move_block_in_graph(container_id, block_id, x=x, y=y)
        except ValidationError as exc:
            self._set_feedback(container_id, str(exc))
            return
        except Exception:
            self._set_feedback(container_id, "Graph layout initialization failed.")
            return
        self._persist_blocks(self._session.blocks)

    def resize_block(self, *, container_id: str, block_id: str, width: float, height: float) -> None:
        if self._session.project_root is None:
            self._set_feedback(container_id, "Open a project first.")
            return
        try:
            use_case = self._session.rebuild_use_case()
            use_case.resize_block_in_graph(container_id, block_id, width=width, height=height)
        except ValidationError as exc:
            self._set_feedback(container_id, str(exc))
            return
        except Exception:
            self._set_feedback(container_id, "Block resize persistence failed.")
            return
        self._persist_blocks(self._session.blocks)
