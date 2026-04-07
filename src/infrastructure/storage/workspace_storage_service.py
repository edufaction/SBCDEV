from __future__ import annotations

"""Workspace persistence layer used by project and library storage.

This module owns on-disk workspace conventions: metadata file, UI state file,
partitioned block files under workspaces, and imported media files.

It also encapsulates mounted library metadata normalization so UI and
application services can rely on a stable format.
"""

import json
import mimetypes
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from domain import Block, BlockType
from infrastructure.storage.serialization import block_from_dict, block_to_dict


class WorkspaceStorageService:
    """Persistence service for workspace data (projects and libraries).

    The class encapsulates file-system structure, metadata normalization,
    and block partitioning by workspace root. It is intentionally shared by
    project and library storage to keep one storage grammar across the app.
    """

    _WORKSPACES_DIRNAME = "workspaces"
    _BLOCKS_FILENAME = "blocks.json"
    _STORAGE_LAYOUT_VERSION = 2

    def __init__(self, *, workspace_kind: str = "project") -> None:
        """Initialize a storage service for one logical workspace kind.

        Args:
            workspace_kind: Default kind assigned to newly created workspaces
                when no explicit kind is provided.
        """

        self._workspace_kind = workspace_kind

    def create_workspace(self, workspace_path: Path, name: str, *, workspace_kind: str | None = None) -> None:
        """Create a workspace directory with the canonical SBC2 layout.

        The method initializes storage folders, baseline metadata, workspace
        partition folder, and an empty UI state payload.

        Args:
            workspace_path: Target workspace root directory.
            name: Human-readable workspace name persisted in metadata.
            workspace_kind: Optional kind override (for example project or library).
        """

        kind = (workspace_kind or self._workspace_kind).strip() or "workspace"
        timestamp = self._utc_now_iso()
        workspace_path.mkdir(parents=True, exist_ok=True)
        (workspace_path / "storage" / "files").mkdir(parents=True, exist_ok=True)
        (workspace_path / "storage" / "thumbs").mkdir(parents=True, exist_ok=True)
        (workspace_path / "cache" / "previews").mkdir(parents=True, exist_ok=True)

        metadata = {
            "id": f"{kind}_{uuid4().hex[:8]}",
            "kind": kind,
            "name": name,
            "version": 1,
            "storage_layout_version": self._STORAGE_LAYOUT_VERSION,
            "description": "",
            "preview_image_path": "",
            "author_name": "",
            "author_email": "",
            "mounted_libraries": [],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        self.save_workspace_metadata(workspace_path, metadata)
        (workspace_path / self._WORKSPACES_DIRNAME).mkdir(parents=True, exist_ok=True)
        self._write_json(workspace_path / "ui_state.json", {})

    def create_project(self, project_path: Path, name: str) -> None:
        """Convenience wrapper creating a workspace with project kind."""

        self.create_workspace(project_path, name, workspace_kind="project")

    def create_library(self, library_path: Path, name: str) -> None:
        """Convenience wrapper creating a workspace with library kind."""

        self.create_workspace(library_path, name, workspace_kind="library")

    def load_workspace_metadata(self, workspace_path: Path) -> dict:
        """Load workspace metadata and normalize mounted library entries.

        Args:
            workspace_path: Workspace directory containing project.json.

        Returns:
            Metadata dictionary with guaranteed list-form mounted_libraries.
        """

        metadata = self._read_json(workspace_path / "project.json")
        if not isinstance(metadata, dict):
            return {}
        raw_mounts = metadata.get("mounted_libraries", [])
        metadata["mounted_libraries"] = self._normalize_mounted_libraries(raw_mounts)
        return metadata

    def save_workspace_metadata(self, workspace_path: Path, metadata: dict) -> None:
        """Persist workspace metadata with schema defaults and timestamps.

        The method keeps created_at stable when possible, updates updated_at on
        every save, and normalizes mounted_libraries into canonical shape.
        """

        payload = dict(metadata)
        existing_created = ""
        target_file = workspace_path / "project.json"
        if target_file.exists():
            try:
                existing = self._read_json(target_file)
                existing_created = str(existing.get("created_at", "") or "")
            except Exception:
                existing_created = ""
        if "kind" not in payload:
            payload["kind"] = self._workspace_kind
        if "storage_layout_version" not in payload:
            payload["storage_layout_version"] = self._STORAGE_LAYOUT_VERSION
        payload["mounted_libraries"] = self._normalize_mounted_libraries(payload.get("mounted_libraries", []))
        if "created_at" not in payload:
            payload["created_at"] = existing_created or self._utc_now_iso()
        payload["updated_at"] = self._utc_now_iso()
        self._write_json(target_file, payload)

    def load_project_metadata(self, project_path: Path) -> dict:
        """Backward-compatible alias for load_workspace_metadata."""

        return self.load_workspace_metadata(project_path)

    def save_project_metadata(self, project_path: Path, metadata: dict) -> None:
        """Backward-compatible alias for save_workspace_metadata."""

        self.save_workspace_metadata(project_path, metadata)

    def list_mounted_libraries(self, workspace_path: Path) -> list[dict[str, Any]]:
        """Return normalized mounted library descriptors for a workspace."""

        metadata = self.load_workspace_metadata(workspace_path)
        return [dict(item) for item in self._normalize_mounted_libraries(metadata.get("mounted_libraries", []))]

    def save_mounted_libraries(self, workspace_path: Path, mounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace mounted library list after canonical normalization."""

        metadata = self.load_workspace_metadata(workspace_path)
        normalized = self._normalize_mounted_libraries(mounts)
        metadata["mounted_libraries"] = normalized
        self.save_workspace_metadata(workspace_path, metadata)
        return [dict(item) for item in normalized]

    def add_mounted_library(
        self,
        workspace_path: Path,
        *,
        library_path: str | Path,
        label: str = "",
        enabled: bool = True,
        read_only: bool = True,
        mount_id: str | None = None,
    ) -> dict[str, Any]:
        """Add or update one mounted library entry.

        If the path already exists in metadata, the existing item is updated
        in place. Otherwise, a new canonical mount descriptor is appended.
        """

        mounts = self.list_mounted_libraries(workspace_path)
        resolved_path = Path(str(library_path)).expanduser().resolve().as_posix()

        for item in mounts:
            if item.get("path") == resolved_path:
                item["label"] = label.strip() or item.get("label") or Path(resolved_path).name
                item["enabled"] = bool(enabled)
                item["read_only"] = bool(read_only)
                updated = self.save_mounted_libraries(workspace_path, mounts)
                for saved in updated:
                    if saved.get("path") == resolved_path:
                        return dict(saved)
                return dict(item)

        mount = {
            "id": (mount_id or "").strip() or f"lib_mount_{uuid4().hex[:8]}",
            "kind": "LIB",
            "path": resolved_path,
            "label": label.strip() or Path(resolved_path).name,
            "enabled": bool(enabled),
            "read_only": bool(read_only),
            "mounted_at": self._utc_now_iso(),
        }
        mounts.append(mount)
        updated = self.save_mounted_libraries(workspace_path, mounts)
        for saved in updated:
            if saved.get("path") == resolved_path:
                return dict(saved)
        return mount

    def remove_mounted_library(
        self,
        workspace_path: Path,
        *,
        mount_id: str | None = None,
        library_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Remove mounted library entries by id and or path."""

        mounts = self.list_mounted_libraries(workspace_path)
        target_id = (mount_id or "").strip()
        target_path = ""
        if library_path is not None:
            target_path = Path(str(library_path)).expanduser().resolve().as_posix()

        filtered = [
            item
            for item in mounts
            if not (
                (target_id and str(item.get("id", "")).strip() == target_id)
                or (target_path and str(item.get("path", "")).strip() == target_path)
            )
        ]
        return self.save_mounted_libraries(workspace_path, filtered)

    def load_blocks(self, workspace_path: Path) -> list[Block]:
        """Load all blocks from partitioned workspace files.

        The current storage layout marker is also enforced on metadata.
        """

        self._mark_storage_layout(workspace_path)
        return self._load_blocks_from_workspace_dirs(workspace_path)

    def save_blocks(self, workspace_path: Path, blocks: list[Block]) -> None:
        """Persist blocks partitioned by workspace-root ownership.

        Partitioning keeps each logical root in its own blocks file while
        preserving deterministic ordering.
        """

        partitions = self._partition_blocks_by_workspace(blocks)
        self._write_workspace_partitions(workspace_path, partitions)
        self._mark_storage_layout(workspace_path)

    def load_ui_state(self, workspace_path: Path) -> dict:
        """Load UI state payload for a workspace, or an empty mapping."""

        path = workspace_path / "ui_state.json"
        if not path.exists():
            return {}
        payload = self._read_json(path)
        if isinstance(payload, dict):
            return payload
        return {}

    def save_ui_state(self, workspace_path: Path, ui_state: dict) -> None:
        """Persist UI state payload for a workspace."""

        self._write_json(workspace_path / "ui_state.json", dict(ui_state))

    def import_file(self, workspace_path: Path, source_file: Path) -> dict[str, str]:
        """Import one external file into workspace-managed storage.

        Video files are normalized to a UI-safe MP4 variant when ffmpeg is
        available; otherwise the source file is copied as-is.

        Returns a descriptor with storage path, mime type and original name.
        """

        files_dir = workspace_path / "storage" / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        source_mime_type = mimetypes.guess_type(source_file.name)[0] or "application/octet-stream"
        if self._is_video_file(source_file, source_mime_type):
            normalized_name = f"{source_file.stem}.mp4"
            normalized_target = self._unique_target_path(files_dir, normalized_name)
            if self._normalize_video_for_ui(source_file, normalized_target):
                relative_storage_path = normalized_target.relative_to(workspace_path).as_posix()
                return {
                    "storage_path": relative_storage_path,
                    "mime_type": "video/mp4",
                    "original_name": source_file.name,
                }

        target_file = self._unique_target_path(files_dir, source_file.name)
        shutil.copy2(source_file, target_file)

        mime_type = mimetypes.guess_type(source_file.name)[0] or "application/octet-stream"
        relative_storage_path = target_file.relative_to(workspace_path).as_posix()
        return {
            "storage_path": relative_storage_path,
            "mime_type": mime_type,
            "original_name": source_file.name,
        }

    def resolve_path(self, workspace_path: Path, relative_path: str) -> Path:
        """Resolve a stored path against workspace root when needed."""

        path = Path(relative_path)
        if path.is_absolute():
            return path
        return (workspace_path / path).resolve()

    def _load_blocks_from_workspace_dirs(self, workspace_path: Path) -> list[Block]:
        workspaces_dir = workspace_path / self._WORKSPACES_DIRNAME
        if not workspaces_dir.exists():
            return []

        loaded: list[Block] = []
        seen_ids: set[str] = set()
        for blocks_file in sorted(workspaces_dir.glob(f"*/{self._BLOCKS_FILENAME}")):
            data = self._read_json(blocks_file)
            if not isinstance(data, list):
                continue
            for item in data:
                block = block_from_dict(item)
                if block.id in seen_ids:
                    continue
                seen_ids.add(block.id)
                loaded.append(block)
        return loaded

    def _partition_blocks_by_workspace(self, blocks: list[Block]) -> dict[str, list[Block]]:
        if not blocks:
            return {}

        by_id = {block.id: block for block in blocks}
        workspace_roots = [
            block
            for block in blocks
            if block.type == BlockType.CONTAINER and block.profile == "workspace_root"
        ]
        if not workspace_roots:
            return {"default": list(blocks)}

        root_ids = {block.id for block in workspace_roots}
        root_key_by_id = self._workspace_keys_for_roots(workspace_roots)
        project_root_id = self._project_root_id(workspace_roots)
        partitions: dict[str, list[Block]] = {key: [] for key in root_key_by_id.values()}
        assigned: dict[str, str] = {}

        for root in workspace_roots:
            key = root_key_by_id[root.id]
            partitions[key].append(root)
            assigned[root.id] = key

        for root in workspace_roots:
            if root.id == project_root_id:
                continue
            key = root_key_by_id[root.id]
            for block_id in self._collect_descendants(root.id, by_id, root_ids):
                if block_id in assigned:
                    continue
                block = by_id.get(block_id)
                if block is None:
                    continue
                partitions[key].append(block)
                assigned[block_id] = key

        fallback_key = root_key_by_id.get(project_root_id or "", "")
        if not fallback_key and partitions:
            fallback_key = next(iter(partitions.keys()))
        if not fallback_key:
            fallback_key = "default"
            partitions.setdefault(fallback_key, [])

        for block in blocks:
            if block.id in assigned:
                continue
            partitions[fallback_key].append(block)
            assigned[block.id] = fallback_key

        ordered_ids = {block.id: index for index, block in enumerate(blocks)}
        normalized: dict[str, list[Block]] = {}
        for key, grouped in partitions.items():
            deduped: list[Block] = []
            seen: set[str] = set()
            for block in sorted(grouped, key=lambda item: ordered_ids.get(item.id, 0)):
                if block.id in seen:
                    continue
                seen.add(block.id)
                deduped.append(block)
            normalized[key] = deduped
        return normalized

    @staticmethod
    def _collect_descendants(root_id: str, by_id: dict[str, Block], workspace_root_ids: set[str]) -> set[str]:
        root = by_id.get(root_id)
        if root is None:
            return set()

        collected: set[str] = set()
        pending = [child_id for child_id in root.contains if child_id]
        while pending:
            current_id = pending.pop()
            if current_id in collected or current_id in workspace_root_ids:
                continue
            collected.add(current_id)
            current = by_id.get(current_id)
            if current is None:
                continue
            pending.extend(child_id for child_id in current.contains if child_id and child_id not in collected)
        return collected

    def _workspace_keys_for_roots(self, roots: list[Block]) -> dict[str, str]:
        keys: dict[str, str] = {}
        used: set[str] = set()
        for root in roots:
            base = self._workspace_key_for_root(root)
            if not base:
                base = self._sanitize_workspace_key(root.id)
            if not base:
                base = "workspace"
            candidate = base
            index = 2
            while candidate in used:
                candidate = f"{base}_{index}"
                index += 1
            used.add(candidate)
            keys[root.id] = candidate
        return keys

    @staticmethod
    def _project_root_id(roots: list[Block]) -> str | None:
        for root in roots:
            role = str(root.content.get("workspace_role", "") or "").strip().lower()
            if role == "project_root":
                return root.id
        for root in roots:
            if root.id == "blk_project_root":
                return root.id
        return None

    def _workspace_key_for_root(self, block: Block) -> str:
        role = str(block.content.get("workspace_role", "") or "").strip().lower()
        if role:
            return self._sanitize_workspace_key(role)
        name = (block.name or "").strip()
        if name:
            return self._sanitize_workspace_key(name)
        return self._sanitize_workspace_key(block.id)

    @staticmethod
    def _sanitize_workspace_key(value: str) -> str:
        lowered = value.strip().lower().replace("-", "_").replace(" ", "_")
        cleaned = "".join(char for char in lowered if char.isalnum() or char == "_")
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip("_")

    def _write_workspace_partitions(self, workspace_path: Path, partitions: dict[str, list[Block]]) -> None:
        workspaces_dir = workspace_path / self._WORKSPACES_DIRNAME
        workspaces_dir.mkdir(parents=True, exist_ok=True)

        desired_keys = {key for key, grouped in partitions.items() if grouped}
        for existing in workspaces_dir.iterdir():
            if not existing.is_dir():
                continue
            if existing.name not in desired_keys:
                shutil.rmtree(existing, ignore_errors=True)

        for workspace_key, grouped_blocks in partitions.items():
            if not grouped_blocks:
                continue
            target_dir = workspaces_dir / workspace_key
            target_dir.mkdir(parents=True, exist_ok=True)
            payload = [block_to_dict(block) for block in grouped_blocks]
            self._write_json(target_dir / self._BLOCKS_FILENAME, payload)

    def _mark_storage_layout(self, workspace_path: Path) -> None:
        try:
            metadata = self.load_workspace_metadata(workspace_path)
        except Exception:
            return
        if metadata.get("storage_layout_version") == self._STORAGE_LAYOUT_VERSION:
            return
        metadata["storage_layout_version"] = self._STORAGE_LAYOUT_VERSION
        self.save_workspace_metadata(workspace_path, metadata)

    @staticmethod
    def _read_json(path: Path):
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(path: Path, payload) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    @staticmethod
    def _unique_target_path(directory: Path, filename: str) -> Path:
        candidate = directory / filename
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        index = 1
        while True:
            unique = directory / f"{stem}_{index}{suffix}"
            if not unique.exists():
                return unique
            index += 1

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _normalize_mounted_libraries(raw_mounts: Any) -> list[dict[str, Any]]:
        """Normalize mounted library payload into canonical persisted schema."""

        if not isinstance(raw_mounts, list):
            return []

        normalized: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for item in raw_mounts:
            if not isinstance(item, dict):
                continue
            raw_path = str(item.get("path", "") or "").strip()
            if not raw_path:
                continue
            resolved_path = Path(raw_path).expanduser().resolve().as_posix()
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)

            mount_id = str(item.get("id", "") or "").strip()
            if not mount_id:
                mount_id = f"lib_mount_{uuid5(NAMESPACE_URL, resolved_path).hex[:8]}"
            label = str(item.get("label", "") or "").strip() or Path(resolved_path).name
            normalized_item = {
                "id": mount_id,
                "kind": "LIB",
                "path": resolved_path,
                "label": label,
                "enabled": WorkspaceStorageService._as_bool(item.get("enabled", True), default=True),
                "read_only": WorkspaceStorageService._as_bool(item.get("read_only", True), default=True),
            }
            mounted_at = str(item.get("mounted_at", "") or "").strip()
            if mounted_at:
                normalized_item["mounted_at"] = mounted_at
            normalized.append(normalized_item)
        return normalized

    @staticmethod
    def _as_bool(value: Any, *, default: bool) -> bool:
        """Convert arbitrary value to bool using tolerant string rules."""

        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "y", "on"}:
                return True
            if lowered in {"0", "false", "no", "n", "off"}:
                return False
            return default
        if value is None:
            return default
        return bool(value)

    @staticmethod
    def _is_video_file(source_file: Path, mime_type: str) -> bool:
        """Return True when the source should follow video import pipeline."""

        if mime_type.startswith("video/"):
            return True
        return source_file.suffix.lower() in {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}

    @staticmethod
    def _normalize_video_for_ui(source_file: Path, target_file: Path) -> bool:
        """Transcode source video into a broadly compatible MP4 variant."""

        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin is None:
            return False

        temp_target = target_file.with_name(f"{target_file.stem}.tmp{target_file.suffix}")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            str(source_file),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "24",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-b:a",
            "128k",
            str(temp_target),
        ]

        try:
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode != 0 or not temp_target.exists():
                temp_target.unlink(missing_ok=True)
                return False

            temp_target.replace(target_file)
            return True
        except OSError:
            temp_target.unlink(missing_ok=True)
            return False


class ProjectStorageService(WorkspaceStorageService):
    """Storage service specialization for project workspaces."""

    def __init__(self) -> None:
        super().__init__(workspace_kind="project")


class LibraryStorageService(WorkspaceStorageService):
    """Storage service specialization for standalone library workspaces."""

    def __init__(self) -> None:
        super().__init__(workspace_kind="library")
