from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from domain import Block, BlockType
from infrastructure.storage import ProjectStorageService


class ProjectWorkspaceService:
    """Project workspace orchestration helpers."""

    @staticmethod
    def _format_fs_datetime(timestamp: float) -> str:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _resolve_block_asset_path(block: Block, project_root: Path | None) -> Path | None:
        for key in ("thumbnail_path", "preview_path", "storage_path", "file_path", "path", "url"):
            raw_value = block.content.get(key)
            if not isinstance(raw_value, str) or not raw_value.strip():
                continue
            candidate = Path(raw_value)
            if candidate.is_absolute() and candidate.exists():
                return candidate
            if project_root is not None:
                resolved = (project_root / candidate).resolve()
                if resolved.exists():
                    return resolved
        return None

    def project_preview_from_blocks(self, blocks: list[Block], project_root: Path | None) -> str:
        if project_root is None:
            return ""
        for block in blocks:
            if block.type != BlockType.IMAGE:
                continue
            resolved = self._resolve_block_asset_path(block, project_root)
            if resolved is not None and resolved.exists():
                return str(resolved)
        return ""

    def project_metadata_view(self, *, project_root: Path | None, blocks: list[Block]) -> dict[str, str]:
        if project_root is None or not project_root.exists():
            return {
                "name": "-",
                "description": "",
                "preview_image_path": "",
                "created_at": "-",
                "updated_at": "-",
                "author_name": "-",
                "author_email": "-",
            }

        storage = ProjectStorageService()
        metadata: dict = {}
        try:
            metadata = storage.load_project_metadata(project_root)
        except Exception:
            metadata = {}

        stats = project_root.stat()
        name = str(metadata.get("name", "") or project_root.name)
        description = str(metadata.get("description", "") or "")
        preview_image_path = str(metadata.get("preview_image_path", "") or "")
        if not preview_image_path:
            preview_image_path = self.project_preview_from_blocks(blocks, project_root)
        created_at = str(metadata.get("created_at", "") or self._format_fs_datetime(stats.st_ctime))
        updated_at = str(metadata.get("updated_at", "") or self._format_fs_datetime(stats.st_mtime))
        author_name = str(metadata.get("author_name", "") or "-")
        author_email = str(metadata.get("author_email", "") or "-")
        return {
            "name": name,
            "description": description,
            "preview_image_path": preview_image_path,
            "created_at": created_at,
            "updated_at": updated_at,
            "author_name": author_name,
            "author_email": author_email,
        }

    def project_stats_view(self, blocks: list[Block]) -> dict[str, int]:
        counts = {
            "images": 0,
            "videos": 0,
            "characters": 0,
            "shots": 0,
            "forms": 0,
            "prompts": 0,
            "audio": 0,
            "total": 0,
        }
        for block in blocks:
            if block.profile == "workspace_root":
                continue
            counts["total"] += 1
            if block.type == BlockType.IMAGE:
                counts["images"] += 1
            if block.type == BlockType.VIDEO:
                counts["videos"] += 1
            if block.type == BlockType.AUDIO:
                counts["audio"] += 1
            if block.type == BlockType.PROMPT:
                counts["prompts"] += 1
            if block.profile == "character":
                counts["characters"] += 1
            if block.profile == "character_form":
                counts["forms"] += 1
            if block.profile == "shot":
                counts["shots"] += 1
        return counts

    def image_blocks(self, blocks: list[Block], project_root: Path | None) -> list[Block]:
        if project_root is None:
            return []
        image_blocks: list[Block] = []
        for block in blocks:
            if block.type != BlockType.IMAGE:
                continue
            resolved = self._resolve_block_asset_path(block, project_root)
            if resolved is None or not resolved.exists():
                continue
            image_blocks.append(block)
        return image_blocks

    def resolve_block_asset_path(self, block: Block, project_root: Path | None) -> Path | None:
        return self._resolve_block_asset_path(block, project_root)

    def find_block_id_for_preview_path(
        self,
        *,
        project_root: Path | None,
        preview_path: str,
        image_blocks: list[Block],
    ) -> str | None:
        if project_root is None:
            return None
        text = str(preview_path or "").strip()
        if not text:
            return None
        target = Path(text).expanduser()
        if not target.is_absolute():
            target = (project_root / target).resolve()
        else:
            target = target.resolve()

        for block in image_blocks:
            resolved = self._resolve_block_asset_path(block, project_root)
            if resolved is None:
                continue
            if resolved.resolve() == target:
                return block.id
        return None

    @staticmethod
    def serialize_preview_path(*, project_root: Path | None, resolved_path: Path) -> str:
        if project_root is None:
            return str(resolved_path)
        try:
            return resolved_path.resolve().relative_to(project_root.resolve()).as_posix()
        except Exception:
            return str(resolved_path.resolve())

    @staticmethod
    def merge_metadata_payload(current: Mapping[str, object], payload: Mapping[str, object]) -> dict[str, object]:
        merged = dict(current)
        merged.update(
            {
                "author_name": str(payload.get("author_name", "") or ""),
                "author_email": str(payload.get("author_email", "") or ""),
                "description": str(payload.get("description", "") or ""),
            }
        )
        return merged
