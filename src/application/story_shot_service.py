from __future__ import annotations

from uuid import uuid4

from application.services import RootLocatorService
from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree


STORY_ROOT_BLOCK_ID = "blk_story_root"


class StoryShotService:
    """Application workflow service for Story shot creation and listing."""

    def __init__(self, root_locator: RootLocatorService | None = None) -> None:
        self._root_locator = root_locator or RootLocatorService()

    def list_shots(self, blocks: list[Block]) -> list[Block]:
        story_root = self._find_story_root(blocks)
        by_id = {block.id: block for block in blocks}
        if story_root is not None:
            ordered: list[Block] = []
            seen: set[str] = set()
            for child_id in story_root.contains:
                child = by_id.get(child_id)
                if child is None or child.profile != "shot":
                    continue
                ordered.append(child)
                seen.add(child.id)
            for block in blocks:
                if block.id in seen or block.profile != "shot":
                    continue
                ordered.append(block)
            return ordered
        return [block for block in blocks if block.profile == "shot"]

    def create_shot(self, blocks: list[Block], *, name: str) -> Block:
        story_root = self._find_story_root(blocks)
        if story_root is None:
            raise ValueError("Story root container not found")

        shot_name = name.strip() or "New Shot"
        block_id = self._new_shot_id(blocks)
        shot = Block(
            id=block_id,
            type=BlockType.CONTAINER,
            profile="shot",
            name=shot_name,
            description=f"Story shot container: {shot_name}",
            domain=BlockDomain.STORY,
            exposed=False,
            tags=["story", "shot"],
            content={"kind": "story_shot"},
            tree=FreeTree(),
            graph=FreeGraph(),
        )
        shot.container_paths[story_root.id] = ""
        blocks.append(shot)
        if shot.id not in story_root.contains:
            story_root.contains.append(shot.id)
        return shot

    def update_shot(
        self,
        blocks: list[Block],
        *,
        shot_id: str,
        name: str,
        description: str,
        tags: list[str],
        functional_name: str,
        comment: str,
    ) -> Block:
        shot = self._find_shot(blocks, shot_id)
        if shot is None:
            raise ValueError(f"Shot not found: {shot_id}")

        resolved_name = name.strip()
        if not resolved_name:
            raise ValueError("Shot name is required")

        shot.name = resolved_name
        shot.description = description.strip()
        shot.tags = self._normalize_tags(tags)
        shot.functional_name = functional_name.strip()
        shot.comment = comment.strip()
        return shot

    @staticmethod
    def _new_shot_id(blocks: list[Block]) -> str:
        used_ids = {block.id for block in blocks}
        while True:
            candidate = f"blk_shot_{uuid4().hex[:10]}"
            if candidate not in used_ids:
                return candidate

    def _find_story_root(self, blocks: list[Block]) -> Block | None:
        return self._root_locator.find_workspace_root(
            blocks,
            role="story_root",
        )

    @staticmethod
    def _find_shot(blocks: list[Block], shot_id: str) -> Block | None:
        target = shot_id.strip()
        if not target:
            return None
        for block in blocks:
            if block.id != target:
                continue
            if block.profile == "shot" and block.type == BlockType.CONTAINER:
                return block
            return None
        return None

    @staticmethod
    def _normalize_tags(raw_tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in raw_tags:
            value = str(raw or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        if "story" not in seen:
            cleaned.insert(0, "story")
            seen.add("story")
        if "shot" not in seen:
            cleaned.append("shot")
        return cleaned
