from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from domain import Block, BlockAccessMode, BlockDomain, BlockType, InputConnection
from infrastructure.storage import LibraryStorageService, ProjectStorageService


class MountedStorageProjectionService:
    """Projects mounted library workspaces into transient session blocks.

    Mounted libraries stay persisted in project metadata only. At load time they
    are projected into read-only blocks so the session can reason about
    ``storage_root`` and ``workspace_root`` objects uniformly.
    """

    _PROJECTED_FLAG = "projected_mount"

    def __init__(
        self,
        *,
        project_storage: ProjectStorageService | None = None,
        library_storage: LibraryStorageService | None = None,
    ) -> None:
        self._project_storage = project_storage or ProjectStorageService()
        self._library_storage = library_storage or LibraryStorageService()

    def load_project_blocks(self, project_path: Path) -> list[Block]:
        project_blocks = list(self._project_storage.load_blocks(project_path))
        return self.merge_mounted_libraries(project_path, project_blocks)

    def merge_mounted_libraries(self, project_path: Path, project_blocks: list[Block]) -> list[Block]:
        merged = list(project_blocks)
        seen_ids = {block.id for block in merged}
        for mount in self._project_storage.list_mounted_libraries(project_path):
            if not bool(mount.get("enabled", True)):
                continue
            for block in self._project_blocks_for_mount(mount):
                if block.id in seen_ids:
                    continue
                merged.append(block)
                seen_ids.add(block.id)
        return merged

    def persistable_blocks(self, blocks: list[Block]) -> list[Block]:
        return [block for block in blocks if not self.is_projected_mount_block(block)]

    @classmethod
    def is_projected_mount_block(cls, block: Block) -> bool:
        provenance = block.provenance if isinstance(block.provenance, dict) else {}
        return bool(provenance.get(cls._PROJECTED_FLAG))

    def _project_blocks_for_mount(self, mount: dict) -> list[Block]:
        mount_id = str(mount.get("id", "") or "").strip()
        mount_label = str(mount.get("label", "") or "").strip() or mount_id or "Mounted Library"
        mount_path_text = str(mount.get("path", "") or "").strip()
        if not mount_id or not mount_path_text:
            return []

        mount_path = Path(mount_path_text).expanduser().resolve()
        if not mount_path.exists():
            return []

        try:
            source_blocks = list(self._library_storage.load_blocks(mount_path))
        except Exception:
            source_blocks = []
        try:
            source_metadata = self._library_storage.load_workspace_metadata(mount_path)
        except Exception:
            source_metadata = {}

        id_map = {block.id: self._projected_block_id(mount_id, block.id) for block in source_blocks}
        projected: list[Block] = [
            self._clone_projected_block(
                block,
                mount=mount,
                mount_path=mount_path,
                mount_label=mount_label,
                source_metadata=source_metadata,
                id_map=id_map,
            )
            for block in source_blocks
        ]
        by_id = {block.id: block for block in projected}

        source_storage_roots = [block for block in source_blocks if block.type == BlockType.CONTAINER and block.profile == "storage_root"]
        source_workspace_roots = [block for block in source_blocks if block.type == BlockType.CONTAINER and block.profile == "workspace_root"]

        projected_storage_root_ids = [id_map[block.id] for block in source_storage_roots if block.id in id_map]
        projected_workspace_root_ids = [id_map[block.id] for block in source_workspace_roots if block.id in id_map]

        synthetic_storage_root_id = ""
        if not projected_storage_root_ids:
            synthetic_storage_root_id = self._synthetic_storage_root_id(mount_id)
            synthetic_storage_root = Block(
                id=synthetic_storage_root_id,
                type=BlockType.CONTAINER,
                profile="storage_root",
                name=mount_label,
                description=f"Mounted library projection for {mount_label}.",
                domain=BlockDomain.LIB,
                access_mode=BlockAccessMode.LINK,
                provenance=self._projection_provenance(
                    mount=mount,
                    mount_path=mount_path,
                    source_block_id="",
                    source_block_name=mount_label,
                    source_workspace_id=str(source_metadata.get("id", "") or ""),
                ),
                tags=["storage_root", "mounted_lib"],
                content={
                    "storage_kind": "mounted_lib",
                    "source_kind": "mounted",
                    "mount_id": mount_id,
                    "backing_path": mount_path.as_posix(),
                    "library_enabled": True,
                    "read_only": bool(mount.get("read_only", True)),
                },
                contains=[],
            )
            projected.append(synthetic_storage_root)
            by_id[synthetic_storage_root.id] = synthetic_storage_root
            projected_storage_root_ids = [synthetic_storage_root.id]

        for source_root in source_workspace_roots:
            projected_root = by_id.get(id_map[source_root.id])
            if projected_root is None:
                continue
            original_storage_root_id = str(source_root.content.get("storage_root_id", "") or "").strip()
            projected_root.content["workspace_scope"] = f"mount:{mount_id}"
            if original_storage_root_id and original_storage_root_id in id_map:
                projected_root.content["storage_root_id"] = id_map[original_storage_root_id]
            elif synthetic_storage_root_id:
                projected_root.content["storage_root_id"] = synthetic_storage_root_id

        if source_workspace_roots and synthetic_storage_root_id:
            synthetic_storage_root = by_id[synthetic_storage_root_id]
            synthetic_storage_root.contains = [root_id for root_id in projected_workspace_root_ids if root_id in by_id]

        synthetic_workspace_root_id = ""
        if not projected_workspace_root_ids:
            synthetic_workspace_root_id = self._synthetic_workspace_root_id(mount_id)
            synthetic_workspace_root = Block(
                id=synthetic_workspace_root_id,
                type=BlockType.CONTAINER,
                profile="workspace_root",
                name=f"{mount_label} Library",
                description=f"Workspace view for mounted library {mount_label}.",
                domain=BlockDomain.LIB,
                access_mode=BlockAccessMode.LINK,
                provenance=self._projection_provenance(
                    mount=mount,
                    mount_path=mount_path,
                    source_block_id="",
                    source_block_name=f"{mount_label} Library",
                    source_workspace_id=str(source_metadata.get("id", "") or ""),
                ),
                tags=["workspace_root", "library_root"],
                content={
                    "workspace_role": "library_root",
                    "workspace_scope": f"mount:{mount_id}",
                    "storage_root_id": projected_storage_root_ids[0],
                },
                contains=[],
            )
            projected.append(synthetic_workspace_root)
            by_id[synthetic_workspace_root.id] = synthetic_workspace_root
            projected_workspace_root_ids = [synthetic_workspace_root.id]
            by_id[projected_storage_root_ids[0]].contains = [synthetic_workspace_root.id]

            contained_source_ids = {
                child_id
                for block in source_blocks
                if block.type == BlockType.CONTAINER
                for child_id in block.contains
            }
            top_level_ids = [
                id_map[block.id]
                for block in source_blocks
                if block.id not in contained_source_ids and block.profile not in {"storage_root", "workspace_root"}
            ]
            synthetic_workspace_root.contains = list(top_level_ids)
            for block_id in top_level_ids:
                candidate = by_id.get(block_id)
                if candidate is None:
                    continue
                candidate.container_paths.setdefault(synthetic_workspace_root.id, "")

        return projected

    def _clone_projected_block(
        self,
        block: Block,
        *,
        mount: dict,
        mount_path: Path,
        mount_label: str,
        source_metadata: dict,
        id_map: dict[str, str],
    ) -> Block:
        projected = deepcopy(block)
        original_id = block.id
        projected.id = id_map[original_id]
        projected.contains = [id_map.get(child_id, child_id) for child_id in block.contains if child_id in id_map]
        projected.inputs = [
            InputConnection(
                source_block_id=id_map[source.source_block_id],
                port=source.port,
                name=source.name,
                enabled=source.enabled,
                order=source.order,
                metadata=dict(source.metadata),
            )
            for source in block.inputs
            if source.source_block_id in id_map
        ]
        projected.container_paths = {
            id_map[parent_id]: str(path_value or "")
            for parent_id, path_value in block.container_paths.items()
            if parent_id in id_map
        }
        if projected.tree is not None:
            for node in projected.tree.nodes.values():
                if node.block_id:
                    node.block_id = id_map.get(node.block_id)
        if projected.graph is not None:
            for node in projected.graph.nodes.values():
                mapped = id_map.get(node.block_id)
                if mapped:
                    node.block_id = mapped

        projected.access_mode = BlockAccessMode.LINK
        projected.provenance = self._projection_provenance(
            mount=mount,
            mount_path=mount_path,
            source_block_id=original_id,
            source_block_name=block.name or original_id,
            source_workspace_id=str(source_metadata.get("id", "") or ""),
        )

        if projected.profile == "storage_root":
            source_storage_kind = str(projected.content.get("storage_kind", "") or "").strip().lower()
            projected.content["storage_kind"] = "mounted_lib"
            projected.content["source_kind"] = "mounted"
            projected.content["source_storage_kind"] = source_storage_kind
            projected.content["mount_id"] = str(mount.get("id", "") or "").strip()
            projected.content["backing_path"] = mount_path.as_posix()
            projected.content["library_enabled"] = True
            projected.content["read_only"] = bool(mount.get("read_only", True))
            projected.name = f"{mount_label} / {block.name or original_id}"
        elif projected.profile == "workspace_root":
            projected.content["workspace_scope"] = f"mount:{str(mount.get('id', '') or '').strip()}"
            original_storage_root_id = str(block.content.get("storage_root_id", "") or "").strip()
            if original_storage_root_id in id_map:
                projected.content["storage_root_id"] = id_map[original_storage_root_id]
        return projected

    def _projection_provenance(
        self,
        *,
        mount: dict,
        mount_path: Path,
        source_block_id: str,
        source_block_name: str,
        source_workspace_id: str,
    ) -> dict:
        return {
            "kind": "lib_link",
            "mount_id": str(mount.get("id", "") or "").strip(),
            "source_workspace_id": source_workspace_id,
            "source_workspace_path": mount_path.as_posix(),
            "source_block_id": source_block_id,
            "source_block_name": source_block_name,
            self._PROJECTED_FLAG: True,
        }

    @staticmethod
    def _projected_block_id(mount_id: str, source_block_id: str) -> str:
        return f"blk_mount_{mount_id}_{source_block_id}"

    @staticmethod
    def _synthetic_storage_root_id(mount_id: str) -> str:
        return f"blk_mount_{mount_id}_storage_root"

    @staticmethod
    def _synthetic_workspace_root_id(mount_id: str) -> str:
        return f"blk_mount_{mount_id}_library_root"
