from __future__ import annotations

from application.story_shot_service import StoryShotService
from domain import Block


class StoryWorkspaceService:
    """Workspace-level orchestration for Story domain actions."""

    def __init__(self, shot_service: StoryShotService | None = None) -> None:
        self._shot_service = shot_service or StoryShotService()

    def create_shot(self, blocks: list[Block], *, name: str):
        return self._shot_service.create_shot(blocks, name=name)

    def update_shot_from_payload(self, blocks: list[Block], payload: dict):
        shot_id = str(payload.get("shot_id", "") or "").strip()
        name = str(payload.get("name", "") or "")
        functional_name = str(payload.get("functional_name", "") or "")
        description = str(payload.get("description", "") or "")
        comment = str(payload.get("comment", "") or "")
        raw_tags = payload.get("tags", [])
        tags = [str(item) for item in raw_tags] if isinstance(raw_tags, list) else []

        return self._shot_service.update_shot(
            blocks,
            shot_id=shot_id,
            name=name,
            description=description,
            tags=tags,
            functional_name=functional_name,
            comment=comment,
        )
