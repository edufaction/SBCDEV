from __future__ import annotations

"""Core domain models.

The design stays intentionally generic:
- Block is the single business object
- FreeTree organizes what a container contains
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


"""Profiles for Block objects. Profiles are not strictly required, but they help guide the content and usage of blocks. They are also used for filtering and organization in the UI."""

PROFILES = {
    # containers
    "workspace_root",
    "container",
    "shot",
    "character",
    "character_form",
    "location",
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
    "internal_lib_empty",
    "template_slot",
}

class BlockType(str, Enum):
    EMPTY = "empty"
    CONTAINER = "container"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    PROMPT = "prompt"


class BlockDomain(str, Enum):
    CHARACTERS = "characters"
    STORY = "story"
    LOCATION = "location"
    LIB = "lib"


class BlockAccessMode(str, Enum):
    OWNED = "owned"
    LINK = "link"


class BlockProvenanceKind(str, Enum):
    LOCAL = "local"
    LIB_CLONE = "lib_clone"
    LIB_LINK = "lib_link"


class PortType(str, Enum):
    IN = "in"
    TOP = "top"
    BOTTOM = "bottom"
    OUT = "out"



@dataclass(slots=True)
class InputConnection:
    """Incoming connection for a target block."""

    source_block_id: str
    port: PortType
    name: str = ""
    enabled: bool = True
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Block:
    """Single generic business entity used by the whole app."""

    id: str
    type: BlockType
    profile: str
    name: str
    description: str = ""
    prompt_ref: str = ""
    prompt_generated: str = ""
    comment: str = ""
    shared: bool = False
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
        return self.type == BlockType.CONTAINER

    def is_link(self) -> bool:
        return self.access_mode == BlockAccessMode.LINK

    def is_editable(self) -> bool:
        return not self.is_link()


@dataclass(slots=True)
class FreeTreeNode:
    """Node used to organize a container content tree."""

    id: str
    kind: str  # "folder" | "block_ref"
    name: str
    block_id: str | None = None
    children: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FreeTree:
    """Single tree attached to one container block."""

    root_ids: list[str] = field(default_factory=list)
    nodes: dict[str, FreeTreeNode] = field(default_factory=dict)


@dataclass(slots=True)
class FreeGraphNode:
    id: str
    block_id: str
    x: float = 0.0
    y: float = 0.0


@dataclass(slots=True)
class FreeGraphEdge:
    id: str
    source_node_id: str
    target_node_id: str
    label: str = ""


@dataclass(slots=True)
class FreeGraph:
    nodes: dict[str, FreeGraphNode] = field(default_factory=dict)
    edges: dict[str, FreeGraphEdge] = field(default_factory=dict)
