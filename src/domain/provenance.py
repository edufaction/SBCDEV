from __future__ import annotations

from .models import BlockAccessMode, BlockProvenanceKind


def normalize_block_provenance(raw: object, *, access_mode: BlockAccessMode) -> dict:
    """Return a canonical provenance payload for one block.

    The function keeps parsing tolerant enough for incomplete or partially
    normalized payloads, but always returns a canonical ``kind`` aligned with
    the effective ``access_mode``.
    """

    payload = dict(raw) if isinstance(raw, dict) else {}
    raw_kind = str(payload.get("kind", "") or "").strip().lower()
    try:
        kind = BlockProvenanceKind(raw_kind)
    except ValueError:
        kind = BlockProvenanceKind.LIB_LINK if access_mode == BlockAccessMode.LINK else BlockProvenanceKind.LOCAL
    if access_mode == BlockAccessMode.LINK and kind == BlockProvenanceKind.LOCAL:
        kind = BlockProvenanceKind.LIB_LINK
    payload["kind"] = kind.value
    return payload
