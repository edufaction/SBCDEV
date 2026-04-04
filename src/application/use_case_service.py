from __future__ import annotations

"""Application-level generic workflows built on top of block services."""

from typing import Any
from uuid import uuid4

from application.container_resolver import ContainerResolver
from domain import Block, BlockAccessMode, BlockDomain, BlockProvenanceKind, BlockType, PortType
from services import BlockService, FreeGraphService, FreeTreeService


class UseCaseService:
    """Thin orchestration layer for product use cases."""

    def __init__(
        self,
        block_service: BlockService,
        resolver: ContainerResolver | None = None,
        free_tree_service: FreeTreeService | None = None,
        free_graph_service: FreeGraphService | None = None,
    ) -> None:
        self._block_service = block_service
        self._resolver = resolver or ContainerResolver(block_service)
        self._free_tree_service = free_tree_service or FreeTreeService()
        self._free_graph_service = free_graph_service or FreeGraphService()

    def create_block(
        self,
        *,
        type: str | BlockType,
        domain: str | BlockDomain = BlockDomain.LIB,
        profile: str = "generic",
        name: str,
        shared: bool = False,
        block_id: str | None = None,
        description: str = "",
        prompt_ref: str = "",
        prompt_generated: str = "",
        comment: str = "",
        functional_name: str = "",
        tags: list[str] | None = None,
        content: dict[str, Any] | None = None,
        access_mode: str | BlockAccessMode = BlockAccessMode.OWNED,
        provenance: dict[str, Any] | None = None,
    ) -> Block:
        """Create a generic block."""
        resolved_type = self._as_block_type(type)
        resolved_block_id = block_id or f"blk_{uuid4().hex[:12]}"

        return self._block_service.create_block(
            block_type=resolved_type,
            domain=self._as_block_domain(domain),
            profile=profile,
            name=name,
            shared=shared,
            block_id=resolved_block_id,
            description=description,
            prompt_ref=prompt_ref,
            prompt_generated=prompt_generated,
            comment=comment,
            access_mode=self._as_block_access_mode(access_mode),
            provenance=dict(provenance or {}),
            functional_name=functional_name,
            tags=tags,
            content=content,
        )

    def add_to_container(self, container_id: str, block_id: str) -> Block:
        """Add block id to container.contains and mirror it in container tree."""
        updated_container = self._block_service.add_to_container(container_id, block_id)
        block = self._block_service.get_block(block_id)
        self._free_tree_service.add_block_ref(updated_container, block_id, name=block.name)
        return self._block_service.update_block(updated_container)

    def remove_from_container(self, container_id: str, block_id: str) -> Block:
        """Remove block id from container and cleanup its tree refs."""
        updated_container = self._block_service.remove_from_container(container_id, block_id)
        self._free_tree_service.remove_block_refs(updated_container, block_id)
        return self._block_service.update_block(updated_container)

    def create_block_in_container(
        self,
        *,
        parent_container_id: str,
        type: str | BlockType,
        name: str,
        domain: str | BlockDomain = BlockDomain.LIB,
        profile: str = "generic",
        shared: bool = False,
        description: str = "",
        prompt_ref: str = "",
        prompt_generated: str = "",
        comment: str = "",
        functional_name: str = "",
        tags: list[str] | None = None,
        content: dict[str, Any] | None = None,
    ) -> Block:
        """Create a block and immediately attach it to a parent container."""
        block = self.create_block(
            type=type,
            domain=domain,
            profile=profile,
            name=name,
            shared=shared,
            description=description,
            prompt_ref=prompt_ref,
            prompt_generated=prompt_generated,
            comment=comment,
            functional_name=functional_name,
            tags=tags,
            content=content,
        )
        self.add_to_container(parent_container_id, block.id)
        return block

    def create_block_from_library_source(
        self,
        *,
        source_block: Block,
        mount_id: str,
        source_workspace_id: str = "",
        source_workspace_path: str = "",
        as_link: bool = False,
        parent_container_id: str | None = None,
        name: str | None = None,
    ) -> Block:
        """Create a local block from an external library block, either as clone or as read-only link."""
        access_mode = BlockAccessMode.LINK if as_link else BlockAccessMode.OWNED
        provenance_kind = BlockProvenanceKind.LIB_LINK if as_link else BlockProvenanceKind.LIB_CLONE
        provenance: dict[str, Any] = {
            "kind": provenance_kind.value,
            "mount_id": mount_id.strip(),
            "source_workspace_id": source_workspace_id.strip(),
            "source_workspace_path": source_workspace_path.strip(),
            "source_block_id": source_block.id,
            "source_block_name": source_block.name,
        }
        block = self.create_block(
            type=source_block.type,
            domain=source_block.domain,
            profile=source_block.profile,
            name=(name or source_block.name or source_block.id),
            description=source_block.description,
            prompt_ref=source_block.prompt_ref,
            prompt_generated=source_block.prompt_generated,
            comment=source_block.comment,
            shared=False,
            functional_name=source_block.functional_name,
            tags=list(source_block.tags),
            content=dict(source_block.content),
            access_mode=access_mode,
            provenance=provenance,
        )
        if parent_container_id:
            self.add_to_container(parent_container_id, block.id)
        return block

    def connect_input(
        self,
        *,
        target_block_id: str,
        source_block_id: str,
        port: str | PortType,
        name: str = "",
        enabled: bool = True,
        order: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Block:
        """Connect source block as input of target block."""
        return self._block_service.add_input(
            target_id=target_block_id,
            source_block_id=source_block_id,
            port=self._as_port_type(port),
            name=name,
            enabled=enabled,
            order=order,
            metadata=metadata,
        )

    def list_blocks_by_domain(self, domain: str | BlockDomain) -> list[Block]:
        """Filter blocks by domain."""
        target_domain = self._as_block_domain(domain)
        return [block for block in self._block_service.list_blocks() if block.domain == target_domain]

    def list_shared_blocks(self, domain: str | BlockDomain | None = None) -> list[Block]:
        """List shared blocks, optionally filtered by domain."""
        blocks = [block for block in self._block_service.list_blocks() if block.shared]
        if domain is None:
            return blocks
        target_domain = self._as_block_domain(domain)
        return [block for block in blocks if block.domain == target_domain]

    def resolve_container(self, container_id: str) -> dict[str, Any]:
        """Build a UI-friendly resolved view of one container."""
        return self._resolver.resolve(container_id)

    def get_tree(self, container_id: str):
        """Expose container FreeTree for caller/UI/testing."""
        container = self._block_service.get_block(container_id)
        had_no_tree = container.tree is None
        tree = self._free_tree_service.ensure_tree(container)
        if had_no_tree:
            self._block_service.update_block(container)
        return tree

    def get_graph(self, container_id: str):
        """Expose container FreeGraph for caller/UI/testing."""
        container = self._block_service.get_block(container_id)
        had_no_graph = container.graph is None
        graph = self._free_graph_service.ensure_graph(container)
        if had_no_graph:
            self._block_service.update_block(container)
        return graph

    def add_block_to_graph(self, container_id: str, block_id: str, x: float = 0, y: float = 0):
        """Add a graph node for an already-contained block."""
        container = self._block_service.get_block(container_id)
        _ = self._block_service.get_block(block_id)
        node = self._free_graph_service.add_block_node(container=container, block_id=block_id, x=x, y=y)
        self._block_service.update_block(container)
        return node

    def add_graph_edge(self, container_id: str, source_node_id: str, target_node_id: str, label: str = ""):
        """Add edge between existing graph nodes in the container graph."""
        container = self._block_service.get_block(container_id)
        edge = self._free_graph_service.add_edge(
            container=container,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            label=label,
        )
        self._block_service.update_block(container)
        return edge

    @staticmethod
    def _as_block_type(value: str | BlockType) -> BlockType:
        """Accept enum or string value for type."""
        if isinstance(value, BlockType):
            return value
        return BlockType(value.strip().lower())

    @staticmethod
    def _as_block_domain(value: str | BlockDomain) -> BlockDomain:
        """Accept enum or string value for domain."""
        if isinstance(value, BlockDomain):
            return value
        return BlockDomain(value.strip().lower())

    @staticmethod
    def _as_port_type(value: str | PortType) -> PortType:
        """Accept enum or string value for port."""
        if isinstance(value, PortType):
            return value
        return PortType(value.strip().lower())

    @staticmethod
    def _as_block_access_mode(value: str | BlockAccessMode) -> BlockAccessMode:
        if isinstance(value, BlockAccessMode):
            return value
        try:
            return BlockAccessMode(value.strip().lower())
        except ValueError:
            return BlockAccessMode.OWNED
