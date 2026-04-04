from __future__ import annotations

from domain import Block, NotFoundError, ValidationError


class BlockRepository:
    """In-memory repository for blocks (infrastructure adapter)."""

    def __init__(self) -> None:
        self._items: dict[str, Block] = {}

    def add(self, block: Block) -> Block:
        if block.id in self._items:
            raise ValidationError(f"Block already exists: {block.id}")
        self._items[block.id] = block
        return self._items[block.id]

    def get(self, block_id: str) -> Block:
        block = self._items.get(block_id)
        if block is None:
            raise NotFoundError(f"Block not found: {block_id}")
        return block

    def update(self, block: Block) -> Block:
        if block.id not in self._items:
            raise NotFoundError(f"Block not found: {block.id}")
        self._items[block.id] = block
        return self._items[block.id]

    def delete(self, block_id: str) -> None:
        if block_id not in self._items:
            raise NotFoundError(f"Block not found: {block_id}")
        del self._items[block_id]

    def exists(self, block_id: str) -> bool:
        return block_id in self._items

    def list(self) -> list[Block]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()

