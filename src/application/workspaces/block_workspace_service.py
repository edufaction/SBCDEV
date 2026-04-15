from __future__ import annotations

from domain import Block

EDITABLE_BLOCK_FIELDS = {
    "name",
    "description",
    "functional_name",
    "comment",
    "tags",
    "prompt_ref",
    "prompt_generated",
}


class BlockWorkspaceService:
    """Workspace-level update service for the generic block properties inspector."""

    def update_block_from_payload(self, blocks: list[Block], payload: dict) -> Block:
        block_id = str(payload.get("block_id", "") or "").strip()
        block = self._find_block(blocks, block_id)
        if block is None:
            raise ValueError(f"Block not found: {block_id}")
        if not block.is_editable():
            raise ValueError("This block is read-only.")

        allowed_keys = [key for key in EDITABLE_BLOCK_FIELDS if key in payload]
        if not allowed_keys:
            raise ValueError("No editable block property provided.")

        if "name" in payload:
            name = str(payload.get("name", "") or "").strip()
            if not name:
                raise ValueError("Block name is required.")
            block.name = name
        if "description" in payload:
            block.description = str(payload.get("description", "") or "").strip()
        if "functional_name" in payload:
            block.functional_name = str(payload.get("functional_name", "") or "").strip()
        if "comment" in payload:
            block.comment = str(payload.get("comment", "") or "").strip()
        if "prompt_ref" in payload:
            block.prompt_ref = str(payload.get("prompt_ref", "") or "").strip()
        if "prompt_generated" in payload:
            block.prompt_generated = str(payload.get("prompt_generated", "") or "").strip()
        if "tags" in payload:
            block.tags = self._normalize_tags(payload.get("tags", []))
        return block

    @staticmethod
    def _find_block(blocks: list[Block], block_id: str) -> Block | None:
        target = block_id.strip()
        if not target:
            return None
        for block in blocks:
            if block.id == target:
                return block
        return None

    @staticmethod
    def _normalize_tags(raw_tags: object) -> list[str]:
        if isinstance(raw_tags, str):
            raw_values = [part.strip() for part in raw_tags.split(",")]
        elif isinstance(raw_tags, list):
            raw_values = [str(item or "").strip() for item in raw_tags]
        else:
            raw_values = []

        cleaned: list[str] = []
        seen: set[str] = set()
        for value in raw_values:
            if not value:
                continue
            normalized = value.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(value)
        return cleaned
