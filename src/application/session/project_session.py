from __future__ import annotations

from pathlib import Path

from application.use_case_service import UseCaseService
from domain import Block, BlockType
from infrastructure.repositories import BlockRepository
from infrastructure.storage import ProjectStorageService
from services import BlockService


class ProjectSession:
    """Live project state shared by application services and UI coordinators."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        blocks: list[Block] | None = None,
        storage: ProjectStorageService | None = None,
    ) -> None:
        self._storage = storage or ProjectStorageService()
        self._project_root = project_root.expanduser().resolve() if project_root is not None else None
        self._blocks = list(blocks or [])

    @property
    def project_root(self) -> Path | None:
        return self._project_root

    @property
    def blocks(self) -> list[Block]:
        return self._blocks

    def set_state(self, *, project_root: Path | None, blocks: list[Block]) -> None:
        self._project_root = project_root.expanduser().resolve() if project_root is not None else None
        self._blocks = list(blocks)

    def clear(self) -> None:
        self._project_root = None
        self._blocks = []

    def load(self, project_root: Path) -> list[Block]:
        resolved_root = project_root.expanduser().resolve()
        blocks = list(self._storage.load_blocks(resolved_root))
        self.set_state(project_root=resolved_root, blocks=blocks)
        return self._blocks

    def persist(self) -> None:
        if self._project_root is None:
            return
        self._storage.save_blocks(self._project_root, self._blocks)

    def rebuild_use_case(self) -> UseCaseService:
        repository = BlockRepository()
        for block in self._blocks:
            repository.add(block)
        return UseCaseService(BlockService(repository))

    def replace_blocks(self, blocks: list[Block]) -> None:
        self._blocks = list(blocks)

    def find_block(self, block_id: str) -> Block | None:
        target = str(block_id or "").strip()
        if not target:
            return None
        return next((block for block in self._blocks if block.id == target), None)

    def find_container(self, container_id: str) -> Block | None:
        candidate = self.find_block(container_id)
        if candidate is None or candidate.type != BlockType.CONTAINER:
            return None
        return candidate
