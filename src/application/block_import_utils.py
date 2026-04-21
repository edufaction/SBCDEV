from __future__ import annotations

import mimetypes
from pathlib import Path

from domain import BlockType


def block_spec_from_imported_file(source_path: Path, file_meta: dict[str, str]) -> tuple[BlockType, str, dict]:
    """Map one imported file descriptor to the canonical SBC block spec."""

    mime_type = str(file_meta.get("mime_type", "") or "")
    relative_path = str(file_meta.get("storage_path", "") or "")
    content = {
        "storage_path": relative_path,
        "mime_type": mime_type,
        "original_name": str(file_meta.get("original_name", "") or source_path.name),
    }

    suffix = source_path.suffix.lower()
    if mime_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        return BlockType.IMAGE, "asset", content
    if mime_type.startswith("video/") or suffix in {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}:
        return BlockType.VIDEO, "asset", content
    if mime_type.startswith("audio/") or suffix in {".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg"}:
        return BlockType.AUDIO, "asset", content
    if suffix in {".prompt"}:
        content["prompt_ref"] = relative_path
        return BlockType.PROMPT, "preset", content
    if mime_type.startswith("text/") or suffix in {".txt", ".md", ".markdown", ".json", ".yaml", ".yml"}:
        return BlockType.TEXT, "note", content
    guessed_mime = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    content["mime_type"] = guessed_mime
    return BlockType.TEXT, "note", content
