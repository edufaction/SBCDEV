from __future__ import annotations

from domain import Block, BlockType

_PROFILE_ICON_NAMES: dict[str, str] = {
    "storage_root": "project_folder_root.svg",
    "workspace_root": "project_folder_root.svg",
    "character": "story_world_user_star.svg",
    "character_form": "project_file_description.svg",
    "shot": "project_file_stack.svg",
    "story_block": "project_file_stack.svg",
    "note": "project_notes.svg",
    "description": "project_notes.svg",
    "dialogue": "project_notes.svg",
    "prompt": "edit_filter_2_spark.svg",
    "preset": "edit_filter_2_spark.svg",
    "placeholder": "actions_plus_minus.svg",
    "template_slot": "actions_plus_minus.svg",
    "asset": "media_photo_search.svg",
    "reference_image": "media_photo_search.svg",
    "image": "media_photo_search.svg",
    "frame": "media_photo_search.svg",
    "video": "media_photo_video.svg",
    "footage": "media_photo_video.svg",
    "voice": "story_world_message_circle_user.svg",
    "music": "story_world_message_circle_user.svg",
    "sfx": "story_world_message_circle_user.svg",
}

_TYPE_ICON_NAMES: dict[BlockType, str] = {
    BlockType.EMPTY: "actions_plus_minus.svg",
    BlockType.CONTAINER: "project_folder_open.svg",
    BlockType.IMAGE: "media_photo_search.svg",
    BlockType.VIDEO: "media_photo_video.svg",
    BlockType.AUDIO: "story_world_message_circle_user.svg",
    BlockType.TEXT: "project_file_description.svg",
    BlockType.PROMPT: "edit_filter_2_spark.svg",
}


def block_icon_name(block: Block) -> str:
    return block_icon_name_for(profile=block.profile, block_type=block.type)


def block_icon_name_for(*, profile: str, block_type: BlockType) -> str:
    normalized = str(profile or "").strip().lower()
    if normalized in _PROFILE_ICON_NAMES:
        return _PROFILE_ICON_NAMES[normalized]
    if normalized.endswith("_root"):
        return "project_folder_root.svg"
    if normalized.endswith("_form"):
        return "project_file_description.svg"
    if normalized.endswith("_empty") or normalized.endswith("_slot"):
        return "actions_plus_minus.svg"
    if normalized.startswith("character"):
        return "story_world_user_star.svg"
    return _TYPE_ICON_NAMES.get(block_type, "actions_adjustments_search.svg")
