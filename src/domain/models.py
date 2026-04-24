from __future__ import annotations

"""Core domain model for SBC2.

This module centralizes the canonical entities manipulated everywhere in the
application (services, storage, and UI). The design goal is to keep the domain
small and stable:

- ``Block`` is the single business object.
- ``FreeTree`` and ``FreeGraph`` are optional embedded structures attached to a
  container block to represent organization and layout views.
- Enum types define constrained values used for persistence and behavior.

Keeping these definitions in one place reduces drift between UI assumptions,
storage schema, and service rules.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


"""Profiles for ``Block`` objects.

Profiles are lightweight semantic tags used to refine behavior, filtering,
and rendering beyond the base ``BlockType``. They are intentionally open-ended,
but this set documents the currently recognized values.
"""

PROFILES = {
    "storage_root",
    # containers
    "workspace_root",
    "container",
    "shot",
    "character",
    "character_form",
    "location",
    "location_scene"
    "library",
    "library_folder",

    # assets
    "asset",
    "reference",
    "generated",
    "variation",

    # text
    "note",
    "description",
    "dialogue",
    "prompt",
    "preset",

    # audio
    "voice",
    "music",
    "sfx",

    # technical (optional)
    "metadata",
    "config",
    "placeholder",
    "template_slot",
}


class BlockType(str, Enum):
    """Physical/media nature of a block.

    ``CONTAINER`` indicates a structural node able to own children.
    Other values represent content blocks.
    """

    EMPTY = "empty"
    CONTAINER = "container"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    PROMPT = "prompt"


class BlockDomain(str, Enum):
    """Functional workspace domain used for organization and filtering."""

    CHARACTERS = "characters"
    STORY = "story"
    LOCATION = "location"
    LIB = "lib"


class BlockAccessMode(str, Enum):
    """Mutability policy for a block.

    - ``OWNED``: block can be modified locally.
    - ``LINK``: block is read-only because it references external origin.
    """

    OWNED = "owned"
    LINK = "link"


class BlockProvenanceKind(str, Enum):
    """Origin category used to track where a block comes from."""

    LOCAL = "local"
    LIB_CLONE = "lib_clone"
    LIB_LINK = "lib_link"


class PortType(str, Enum):
    """Allowed logical ports for block input connections."""

    IN = "in"
    TOP = "top"
    BOTTOM = "bottom"
    OUT = "out"


@dataclass(slots=True)
class InputConnection:
    """Incoming link targeting one block.

    Attributes:
        source_block_id: Upstream block identifier.
        port: Logical target port on the receiving block.
        name: Optional user-facing label for this connection.
        enabled: Whether this link should be considered active.
        order: Stable ordering index for deterministic rendering.
        metadata: Extra per-connection payload for UI/use-case specific needs.
    """

    source_block_id: str
    port: PortType
    name: str = ""
    enabled: bool = True
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Block:
    """Single generic business entity used by the whole application.

    A ``Block`` can represent either a structural container or a final content
    item (image, video, prompt, etc.). This unified model is intentional: it
    enables composable tooling (tree, inspector, import/export, links) without
    per-domain object hierarchies.

    Key invariants:
        - ``id`` is globally unique inside one workspace.
        - ``contains`` is only meaningful for container blocks.
        - ``tree`` and ``graph`` are optional embedded views, typically present
          for container blocks.
        - ``access_mode`` and ``provenance`` jointly express editability and
          origin tracking.
        - ``container_paths`` stores virtual free-tree paths per parent
          container id.
    """

    id: str
    type: BlockType
    profile: str
    name: str
    description: str = ""
    prompt_ref: str = ""
    prompt_generated: str = ""
    comment: str = ""
    exposed: bool = False
    domain: BlockDomain = BlockDomain.LIB
    access_mode: BlockAccessMode = BlockAccessMode.OWNED
    provenance: dict[str, Any] = field(default_factory=lambda: {"kind": BlockProvenanceKind.LOCAL.value})
    container_paths: dict[str, str] = field(default_factory=dict)
    functional_name: str = ""
    tags: list[str] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    contains: list[str] = field(default_factory=list)
    inputs: list[InputConnection] = field(default_factory=list)
    tree: FreeTree | None = None
    graph: FreeGraph | None = None

    def is_container(self) -> bool:
        """Return ``True`` when this block can contain child blocks."""

        return self.type == BlockType.CONTAINER

    def is_link(self) -> bool:
        """Return ``True`` when this block is a read-only external link."""

        return self.access_mode == BlockAccessMode.LINK

    def is_editable(self) -> bool:
        """Return ``True`` when local mutations are allowed."""

        return not self.is_link()

    @property
    def shared(self) -> bool:
        """Temporary compatibility alias for the old `shared` field name."""

        return self.exposed

    @shared.setter
    def shared(self, value: bool) -> None:
        self.exposed = bool(value)

    def as_media(self) -> "MediaContent":
        """Return a typed view of ``content`` for IMAGE, VIDEO and AUDIO blocks.

        Values are read from the backing ``content`` dict; the returned object
        is a snapshot and is **not** kept in sync with later dict mutations.
        """

        from .block_content import MediaContent  # local import avoids circular refs

        return MediaContent(
            storage_path=str(self.content.get("storage_path") or ""),
            thumbnail_path=str(self.content.get("thumbnail_path") or ""),
            preview_path=str(self.content.get("preview_path") or ""),
            width=int(self.content.get("width") or 0),
            height=int(self.content.get("height") or 0),
            duration_ms=int(self.content.get("duration_ms") or 0),
        )

    def as_container(self) -> "ContainerContent":
        """Return a typed view of ``content`` for CONTAINER / workspace-root blocks.

        ``workspace_role`` is normalised to lowercase and stripped so callers
        can compare directly without defensive casting.

        The returned object is a snapshot and is **not** kept in sync with
        later dict mutations.
        """

        from .block_content import ContainerContent  # local import avoids circular refs

        return ContainerContent(
            workspace_role=str(self.content.get("workspace_role") or "").strip().lower(),
            workspace_scope=str(self.content.get("workspace_scope") or "").strip().lower(),
            storage_root_id=str(self.content.get("storage_root_id") or "").strip(),
            storage_kind=str(self.content.get("storage_kind") or "").strip().lower(),
            source_kind=str(self.content.get("source_kind") or "").strip().lower(),
            mount_id=str(self.content.get("mount_id") or "").strip(),
            library_enabled=bool(self.content.get("library_enabled")),
            read_only=bool(self.content.get("read_only")),
            internal_lib=bool(self.content.get("internal_lib")),
            drop_target=bool(self.content.get("drop_target")),
        )


@dataclass(slots=True)
class FreeTreeNode:
    """Node used in a container embedded tree view.

    ``kind`` follows the lightweight convention:
        - ``folder``: virtual grouping node
        - ``block_ref``: reference to a block id

    ``block_id`` is optional to support both pure virtual folders and container
    folder nodes bound to a block.
    """

    id: str
    kind: str  # "folder" | "block_ref"
    name: str
    block_id: str | None = None
    children: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FreeTree:
    """Single tree attached to one container block.

    The tree is intentionally denormalized for UI speed:
        - ``root_ids`` keeps top-level ordering.
        - ``nodes`` stores full node payload indexed by node id.
    """

    root_ids: list[str] = field(default_factory=list)
    nodes: dict[str, FreeTreeNode] = field(default_factory=dict)


@dataclass(slots=True)
class FreeGraphNode:
    """Positioned node used by a container embedded graph view."""

    id: str
    block_id: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass(slots=True)
class FreeGraphEdge:
    """Directed edge connecting two ``FreeGraphNode`` identifiers."""

    id: str
    source_node_id: str
    target_node_id: str
    label: str = ""


@dataclass(slots=True)
class FreeGraph:
    """Graph payload attached to one container block for spatial views."""

    nodes: dict[str, FreeGraphNode] = field(default_factory=dict)
    edges: dict[str, FreeGraphEdge] = field(default_factory=dict)
