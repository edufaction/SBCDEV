from __future__ import annotations

"""Typed content views for ``Block.content``.

``Block.content`` is a flexible ``dict[str, Any]`` kept as the persistence
format for backward-compatibility and serialisation simplicity.  These
dataclasses provide a *typed read layer* on top of that dict so that callsites
can use attribute access and static-analysis tooling instead of raw string key
lookups.

Usage pattern::

    # Read
    media = block.as_media()
    path  = media.storage_path          # str, never KeyError

    role  = block.as_container().workspace_role   # str, stripped+lowered

    # Write – still goes directly into the backing dict so serialisation is
    # unaffected.  Use the canonical key names defined below.
    block.content["storage_path"] = str(destination)
    block.content["workspace_role"] = "story_root"
"""

from dataclasses import dataclass


@dataclass
class MediaContent:
    """Typed view of ``Block.content`` for IMAGE, VIDEO and AUDIO blocks.

    Canonical content keys:
        ``storage_path``   – primary file path (relative to project root or absolute)
        ``thumbnail_path`` – pre-generated thumbnail / poster frame
        ``preview_path``   – lightweight preview (e.g. low-res video preview)
        ``width``          – pixel width (0 = unknown)
        ``height``         – pixel height (0 = unknown)
        ``duration_ms``    – media duration in milliseconds (0 = N/A)
    """

    storage_path: str = ""
    thumbnail_path: str = ""
    preview_path: str = ""
    width: int = 0
    height: int = 0
    duration_ms: int = 0

    def candidate_paths(self) -> tuple[str, ...]:
        """Return non-empty path strings in lookup-priority order.

        Callers should try each candidate in sequence and stop at the first
        one that resolves to an existing file.
        """
        return tuple(p for p in (self.thumbnail_path, self.preview_path, self.storage_path) if p)


@dataclass
class ContainerContent:
    """Typed view of ``Block.content`` for CONTAINER and workspace-root blocks.

    Canonical content keys:
        ``workspace_role`` – semantic role string (e.g. ``"story_root"``,
                             ``"characters_root"``, ``"internal_lib"``).
                             Always lowercase and stripped.
        ``internal_lib``   – ``True`` when this block belongs to the internal
                             library workspace.
        ``drop_target``    – ``True`` when this block acts as a drag-and-drop
                             landing zone in the UI.
    """

    workspace_role: str = ""
    internal_lib: bool = False
    drop_target: bool = False
