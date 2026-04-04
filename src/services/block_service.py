from __future__ import annotations

"""Low-level CRUD/service operations on Block objects."""

from typing import Any
from uuid import uuid4

from domain import (
    Block,
    BlockAccessMode,
    BlockDomain,
    BlockProvenanceKind,
    BlockType,
    FreeGraph,
    FreeTree,
    InputConnection,
    NotFoundError,
    PortType,
    ValidationError,
)
from infrastructure.repositories import BlockRepository
from services.container_rules import ContainerRulesService


class BlockService:
    """Generic block service backed by BlockRepository."""

    def __init__(self, repository: BlockRepository, container_rules: ContainerRulesService | None = None) -> None:
        self._repository = repository
        self._container_rules = container_rules or ContainerRulesService()

    def create_block(
        self,
        *,
        block_type: BlockType,
        profile: str,
        name: str,
        block_id: str | None = None,
        description: str = "",
        prompt_ref: str = "",
        prompt_generated: str = "",
        comment: str = "",
        shared: bool = False,
        domain: BlockDomain = BlockDomain.LIB,
        access_mode: BlockAccessMode = BlockAccessMode.OWNED,
        provenance: dict[str, Any] | None = None,
        functional_name: str = "",
        tags: list[str] | None = None,
        content: dict[str, Any] | None = None,
    ) -> Block:
        """Create and persist a generic block."""
        if not profile.strip():
            raise ValidationError("profile is required")
        if not name.strip():
            raise ValidationError("name is required")

        block = Block(
            id=block_id or f"blk_{uuid4().hex[:12]}",
            type=block_type,
            profile=profile.strip(),
            name=name.strip(),
            description=description,
            prompt_ref=prompt_ref,
            prompt_generated=prompt_generated,
            comment=comment,
            shared=shared,
            domain=domain,
            access_mode=access_mode,
            provenance=self._normalize_provenance(provenance, access_mode=access_mode),
            functional_name=functional_name,
            tags=list(tags or []),
            content=dict(content or {}),
            tree=(FreeTree() if block_type == BlockType.CONTAINER else None),
            graph=(FreeGraph() if block_type == BlockType.CONTAINER else None),
        )
        return self._repository.add(block)

    def get_block(self, block_id: str) -> Block:
        return self._repository.get(block_id)

    def delete_block(self, block_id: str) -> None:
        """Delete a block and remove references from all other blocks."""
        if not self._repository.exists(block_id):
            raise NotFoundError(f"Block not found: {block_id}")

        for block in self._repository.list():
            changed = False
            if block_id in block.contains:
                block.contains = [child_id for child_id in block.contains if child_id != block_id]
                changed = True

            filtered_inputs = [item for item in block.inputs if item.source_block_id != block_id]
            if len(filtered_inputs) != len(block.inputs):
                block.inputs = filtered_inputs
                changed = True

            if changed:
                self._repository.update(block)

        self._repository.delete(block_id)

    def add_to_container(self, container_id: str, block_id: str) -> Block:
        """Attach block id to container.contains."""
        if container_id == block_id:
            raise ValidationError("a block cannot be child of itself")

        container = self._repository.get(container_id)
        child = self._repository.get(block_id)
        self._ensure_editable(container, operation="add child")
        self._container_rules.validate_child_link(parent=container, child=child)

        if block_id in container.contains:
            return container

        container.contains.append(block_id)
        return self._repository.update(container)

    def remove_from_container(self, container_id: str, block_id: str) -> Block:
        """Detach block id from container.contains."""
        container = self._repository.get(container_id)
        self._ensure_editable(container, operation="remove child")
        if block_id not in container.contains:
            raise NotFoundError(f"Child link not found: parent={container_id} child={block_id}")

        container.contains = [item for item in container.contains if item != block_id]
        return self._repository.update(container)

    def add_input(
        self,
        *,
        target_id: str,
        source_block_id: str,
        port: PortType,
        name: str = "",
        enabled: bool = True,
        order: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Block:
        """Add an incoming connection on target block."""
        target = self._repository.get(target_id)
        self._ensure_editable(target, operation="add input")
        _ = self._repository.get(source_block_id)

        already_exists = any(
            item.source_block_id == source_block_id and item.port == port and item.name == name
            for item in target.inputs
        )
        if already_exists:
            return target

        target.inputs.append(
            InputConnection(
                source_block_id=source_block_id,
                port=port,
                name=name,
                enabled=enabled,
                order=order,
                metadata=dict(metadata or {}),
            )
        )
        return self._repository.update(target)

    def remove_input(
        self,
        *,
        target_id: str,
        source_block_id: str,
        port: PortType | None = None,
        name: str | None = None,
    ) -> Block:
        """Remove incoming connection(s) on target block."""
        target = self._repository.get(target_id)
        self._ensure_editable(target, operation="remove input")
        before = len(target.inputs)
        target.inputs = [
            item
            for item in target.inputs
            if not (
                item.source_block_id == source_block_id
                and (port is None or item.port == port)
                and (name is None or item.name == name)
            )
        ]

        if len(target.inputs) == before:
            raise NotFoundError(
                f"Input connection not found: target={target_id} source={source_block_id} port={port} name={name}"
            )
        return self._repository.update(target)

    def get_inputs_for_port(
        self,
        block: Block,
        port: PortType,
        only_enabled: bool = True,
    ) -> list[InputConnection]:
        """Return inputs filtered by port and enabled flag."""
        result = [item for item in block.inputs if item.port == port]
        if only_enabled:
            result = [item for item in result if item.enabled]
        return sorted(result, key=lambda item: item.order)

    def list_blocks(self) -> list[Block]:
        return self._repository.list()

    def update_block(self, block: Block) -> Block:
        """Persist an already existing block instance."""
        self._ensure_editable(block, operation="update")
        return self._repository.update(block)

    @staticmethod
    def _ensure_editable(block: Block, *, operation: str) -> None:
        if block.is_editable():
            return
        raise ValidationError(
            f"Block '{block.id}' is read-only (access_mode={block.access_mode.value}); cannot {operation}."
        )

    @staticmethod
    def _normalize_provenance(
        provenance: dict[str, Any] | None,
        *,
        access_mode: BlockAccessMode,
    ) -> dict[str, Any]:
        payload = dict(provenance or {})
        raw_kind = str(payload.get("kind", "") or "").strip().lower()
        if raw_kind in {kind.value for kind in BlockProvenanceKind}:
            kind = raw_kind
        else:
            kind = (
                BlockProvenanceKind.LIB_LINK.value
                if access_mode == BlockAccessMode.LINK
                else BlockProvenanceKind.LOCAL.value
            )
        if access_mode == BlockAccessMode.LINK and kind == BlockProvenanceKind.LOCAL.value:
            kind = BlockProvenanceKind.LIB_LINK.value
        payload["kind"] = kind
        return payload
