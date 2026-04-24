from __future__ import annotations

from domain import Block, BlockType


class RootLocatorService:
    """Centralized lookup for storage roots and workspace roots.

    This service provides one explicit place to resolve technical storage roots
    and logical workspace roots, so application services stop depending on
    hardcoded ids and name heuristics spread across the codebase.
    """

    def list_storage_roots(self, blocks: list[Block]) -> list[Block]:
        return [block for block in blocks if block.type == BlockType.CONTAINER and block.profile == "storage_root"]

    def find_storage_root(
        self,
        blocks: list[Block],
        *,
        storage_root_id: str | None = None,
        storage_kind: str | None = None,
        mount_id: str | None = None,
    ) -> Block | None:
        target_id = str(storage_root_id or "").strip()
        target_kind = str(storage_kind or "").strip().lower()
        target_mount_id = str(mount_id or "").strip()
        for block in self.list_storage_roots(blocks):
            content = block.as_container()
            if target_id and block.id != target_id:
                continue
            if target_kind and content.storage_kind != target_kind:
                continue
            if target_mount_id and content.mount_id != target_mount_id:
                continue
            return block
        return None

    def list_workspace_roots(
        self,
        blocks: list[Block],
        *,
        storage_root_id: str | None = None,
    ) -> list[Block]:
        target_storage_root_id = str(storage_root_id or "").strip()
        roots = [
            block
            for block in blocks
            if block.type == BlockType.CONTAINER and block.profile == "workspace_root"
        ]
        if not target_storage_root_id:
            return roots
        return [block for block in roots if block.as_container().storage_root_id == target_storage_root_id]

    def find_workspace_root(
        self,
        blocks: list[Block],
        *,
        role: str,
        scope: str | None = None,
        storage_root_id: str | None = None,
    ) -> Block | None:
        target_role = str(role or "").strip().lower()
        target_scope = str(scope or "").strip().lower()
        target_storage_root_id = str(storage_root_id or "").strip()
        for block in self.list_workspace_roots(blocks, storage_root_id=target_storage_root_id or None):
            content = block.as_container()
            if content.workspace_role != target_role:
                continue
            if target_scope and content.workspace_scope not in {"", target_scope}:
                continue
            return block
        return None
