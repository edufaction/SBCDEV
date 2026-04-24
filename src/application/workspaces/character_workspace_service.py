from __future__ import annotations

from application.block_template_service import BlockTemplateService
from application.services import RootLocatorService
from domain import Block, BlockType


CHARACTERS_ROOT_BLOCK_ID = "blk_characters_root"


class CharacterWorkspaceService:
    """Workspace-level orchestration for Character domain actions."""

    def __init__(
        self,
        template_service: BlockTemplateService | None = None,
        root_locator: RootLocatorService | None = None,
    ) -> None:
        self._template_service = template_service or BlockTemplateService()
        self._root_locator = root_locator or RootLocatorService()

    def list_characters(self, blocks: list[Block]) -> list[Block]:
        characters_root = self._find_characters_root(blocks)
        by_id = {block.id: block for block in blocks}
        if characters_root is None:
            return [block for block in blocks if block.type == BlockType.CONTAINER and block.profile == "character"]

        ordered: list[Block] = []
        seen: set[str] = set()
        for child_id in characters_root.contains:
            child = by_id.get(child_id)
            if child is None or child.type != BlockType.CONTAINER or child.profile != "character":
                continue
            ordered.append(child)
            seen.add(child.id)

        for block in blocks:
            if block.id in seen:
                continue
            if block.type == BlockType.CONTAINER and block.profile == "character":
                ordered.append(block)
        return ordered

    def create_character(
        self,
        blocks: list[Block],
        *,
        name: str,
        template_key: str = "character_standard",
    ) -> Block:
        characters_root = self._find_characters_root(blocks)
        if characters_root is None:
            raise ValueError("Characters root container not found")

        created_blocks = self._template_service.instantiate_character_template(
            character_name=name,
            template_key=template_key,
        )
        if not created_blocks:
            raise ValueError("Character template did not produce any blocks")

        root_character = next(
            (
                block
                for block in created_blocks
                if block.type == BlockType.CONTAINER and block.profile == "character"
            ),
            None,
        )
        if root_character is None:
            raise ValueError("Character template root container not found")

        created_by_id = {block.id: block for block in created_blocks}
        root_character.container_paths[characters_root.id] = ""
        self._assign_child_container_paths(parent=root_character, created_by_id=created_by_id)

        blocks.extend(created_blocks)
        if root_character.id not in characters_root.contains:
            characters_root.contains.append(root_character.id)
        return root_character

    def update_character_from_payload(self, blocks: list[Block], payload: dict) -> Block:
        character_id = str(payload.get("character_id", "") or "").strip()
        character = self._find_character(blocks, character_id)
        if character is None:
            raise ValueError(f"Character not found: {character_id}")

        name = str(payload.get("name", "") or "").strip()
        if not name:
            raise ValueError("Character name is required")

        character.name = name
        character.description = str(payload.get("description", "") or "").strip()
        character.functional_name = str(payload.get("functional_name", "") or "").strip()
        character.comment = str(payload.get("comment", "") or "").strip()
        raw_tags = payload.get("tags", [])
        tags = raw_tags if isinstance(raw_tags, list) else []
        character.tags = self._normalize_character_tags(tags)
        return character

    @staticmethod
    def _assign_child_container_paths(*, parent: Block, created_by_id: dict[str, Block]) -> None:
        for child_id in parent.contains:
            child = created_by_id.get(child_id)
            if child is None:
                continue
            child.container_paths[parent.id] = ""
            if child.type == BlockType.CONTAINER:
                CharacterWorkspaceService._assign_child_container_paths(parent=child, created_by_id=created_by_id)

    def _find_characters_root(self, blocks: list[Block]) -> Block | None:
        return self._root_locator.find_workspace_root(
            blocks,
            role="characters_root",
        )

    @staticmethod
    def _find_character(blocks: list[Block], character_id: str) -> Block | None:
        target = character_id.strip()
        if not target:
            return None
        for block in blocks:
            if block.id != target:
                continue
            if block.type == BlockType.CONTAINER and block.profile == "character":
                return block
            return None
        return None

    @staticmethod
    def _normalize_character_tags(raw_tags: list[object]) -> list[str]:
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
        if "character" not in seen:
            cleaned.insert(0, "character")
        return cleaned
