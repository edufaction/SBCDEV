from __future__ import annotations

from pathlib import Path

from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree
from infrastructure.storage import ProjectStorageService

CHARACTERS_ROOT_BLOCK_ID = "blk_characters_root"
STORY_ROOT_BLOCK_ID = "blk_story_root"
INTERNAL_LIB_ROOT_BLOCK_ID = "blk_internal_lib_root"
PROJECT_STORAGE_ROOT_BLOCK_ID = "blk_storage_project_root"
INTERNAL_STORAGE_ROOT_BLOCK_ID = "blk_storage_internal_root"


class ProjectStructureService:
    """Seeds and migrates the canonical workspace structure for a project."""

    def __init__(self, *, storage: ProjectStorageService | None = None) -> None:
        self._storage = storage or ProjectStorageService()

    @staticmethod
    def create_workspace_root_block(
        *,
        block_id: str,
        name: str,
        domain: BlockDomain,
        role: str,
        description: str,
        storage_root_id: str = "",
        workspace_scope: str = "",
    ) -> Block:
        return Block(
            id=block_id,
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name=name,
            description=description,
            domain=domain,
            exposed=False,
            tags=["workspace_root", role],
            content={
                "workspace_role": role,
                "workspace_scope": workspace_scope,
                "storage_root_id": storage_root_id,
            },
            tree=FreeTree(),
            graph=FreeGraph(),
        )

    @staticmethod
    def create_storage_root_block(
        *,
        block_id: str,
        name: str,
        domain: BlockDomain,
        storage_kind: str,
        source_kind: str,
        description: str,
        read_only: bool = False,
        library_enabled: bool = True,
    ) -> Block:
        return Block(
            id=block_id,
            type=BlockType.CONTAINER,
            profile="storage_root",
            name=name,
            description=description,
            domain=domain,
            exposed=False,
            tags=["storage_root", storage_kind, source_kind],
            content={
                "storage_kind": storage_kind,
                "source_kind": source_kind,
                "read_only": read_only,
                "library_enabled": library_enabled,
            },
            tree=FreeTree(),
            graph=FreeGraph(),
        )

    @classmethod
    def default_workspace_structure_blocks(cls) -> list[Block]:
        project_storage_root = cls.create_storage_root_block(
            block_id=PROJECT_STORAGE_ROOT_BLOCK_ID,
            name="Project Storage",
            domain=BlockDomain.LIB,
            storage_kind="project_space",
            source_kind="project",
            description="Technical storage root for project-owned workspaces.",
        )
        internal_storage_root = cls.create_storage_root_block(
            block_id=INTERNAL_STORAGE_ROOT_BLOCK_ID,
            name="Internal Library Storage",
            domain=BlockDomain.LIB,
            storage_kind="internal_lib",
            source_kind="internal",
            description="Technical storage root for the project internal library.",
        )
        characters_root = cls.create_workspace_root_block(
            block_id=CHARACTERS_ROOT_BLOCK_ID,
            name="Characters Root",
            domain=BlockDomain.CHARACTERS,
            role="characters_root",
            description="Characters workspace root.",
            storage_root_id=PROJECT_STORAGE_ROOT_BLOCK_ID,
            workspace_scope="project",
        )
        story_root = cls.create_workspace_root_block(
            block_id=STORY_ROOT_BLOCK_ID,
            name="Story Root",
            domain=BlockDomain.STORY,
            role="story_root",
            description="Story workspace root.",
            storage_root_id=PROJECT_STORAGE_ROOT_BLOCK_ID,
            workspace_scope="project",
        )
        internal_lib_root = cls.create_workspace_root_block(
            block_id=INTERNAL_LIB_ROOT_BLOCK_ID,
            name="INTERNALLIB",
            domain=BlockDomain.LIB,
            role="internal_lib",
            description="Internal import workspace root.",
            storage_root_id=INTERNAL_STORAGE_ROOT_BLOCK_ID,
            workspace_scope="internal",
        )
        project_storage_root.contains = [characters_root.id, story_root.id]
        internal_storage_root.contains = [internal_lib_root.id]
        return [
            project_storage_root,
            internal_storage_root,
            characters_root,
            story_root,
            internal_lib_root,
        ]

    @staticmethod
    def workspace_root_role(block: Block) -> str:
        if block.type != BlockType.CONTAINER or block.profile != "workspace_root":
            return ""
        role = block.as_container().workspace_role
        if role:
            return role
        normalized_name = (block.name or "").strip().upper().replace(" ", "_")
        if block.id == INTERNAL_LIB_ROOT_BLOCK_ID:
            return "internal_lib"
        if normalized_name in {"INTERNALLIB", "INTERNAL_LIB"}:
            return "internal_lib"
        if block.id == CHARACTERS_ROOT_BLOCK_ID or "CHAR" in normalized_name:
            return "characters_root"
        if block.id == STORY_ROOT_BLOCK_ID or "STORY" in normalized_name:
            return "story_root"
        return ""

    @staticmethod
    def replace_ids_in_text(value: str, mapping: dict[str, str]) -> str:
        updated = value
        for old, new in mapping.items():
            updated = updated.replace(old, new)
        return updated

    @staticmethod
    def dedupe_ids(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def seed_workspace_structure_defaults(
        self,
        project_path: Path,
        *,
        storage: ProjectStorageService | None = None,
    ) -> None:
        service = storage or self._storage
        try:
            existing = service.load_blocks(project_path)
        except Exception:
            existing = []
        if existing:
            return
        service.save_blocks(project_path, self.default_workspace_structure_blocks())

    def ensure_workspace_structure_on_open(self, project_path: Path, blocks: list[Block]) -> list[Block]:
        if not blocks:
            return blocks

        updated_blocks = list(blocks)
        by_id = {block.id: block for block in updated_blocks}
        changed = False

        def resolve_or_create_storage_root(
            *,
            block_id: str,
            name: str,
            domain: BlockDomain,
            storage_kind: str,
            source_kind: str,
            description: str,
            read_only: bool = False,
            library_enabled: bool = True,
        ) -> Block:
            nonlocal changed
            candidate = by_id.get(block_id)
            if candidate is None:
                candidate = self.create_storage_root_block(
                    block_id=block_id,
                    name=name,
                    domain=domain,
                    storage_kind=storage_kind,
                    source_kind=source_kind,
                    description=description,
                    read_only=read_only,
                    library_enabled=library_enabled,
                )
                updated_blocks.append(candidate)
                by_id[candidate.id] = candidate
                changed = True
            if candidate.type != BlockType.CONTAINER:
                candidate.type = BlockType.CONTAINER
                changed = True
            if candidate.profile != "storage_root":
                candidate.profile = "storage_root"
                changed = True
            if candidate.name != name:
                candidate.name = name
                changed = True
            if candidate.domain != domain:
                candidate.domain = domain
                changed = True
            if candidate.description != description:
                candidate.description = description
                changed = True
            if candidate.tree is None:
                candidate.tree = FreeTree()
                changed = True
            if candidate.graph is None:
                candidate.graph = FreeGraph()
                changed = True
            if candidate.as_container().storage_kind != storage_kind:
                candidate.content["storage_kind"] = storage_kind
                changed = True
            if candidate.as_container().source_kind != source_kind:
                candidate.content["source_kind"] = source_kind
                changed = True
            if candidate.as_container().read_only != read_only:
                candidate.content["read_only"] = read_only
                changed = True
            if candidate.as_container().library_enabled != library_enabled:
                candidate.content["library_enabled"] = library_enabled
                changed = True
            candidate.contains = self.dedupe_ids(list(candidate.contains))
            return candidate

        def ensure_role(block: Block, role: str) -> None:
            nonlocal changed
            if block.as_container().workspace_role != role:
                block.content["workspace_role"] = role
                changed = True

        def ensure_workspace_binding(block: Block, *, storage_root_id: str, workspace_scope: str) -> None:
            nonlocal changed
            if block.as_container().storage_root_id != storage_root_id:
                block.content["storage_root_id"] = storage_root_id
                changed = True
            if block.as_container().workspace_scope != workspace_scope:
                block.content["workspace_scope"] = workspace_scope
                changed = True

        project_storage_root = resolve_or_create_storage_root(
            block_id=PROJECT_STORAGE_ROOT_BLOCK_ID,
            name="Project Storage",
            domain=BlockDomain.LIB,
            storage_kind="project_space",
            source_kind="project",
            description="Technical storage root for project-owned workspaces.",
        )
        internal_storage_root = resolve_or_create_storage_root(
            block_id=INTERNAL_STORAGE_ROOT_BLOCK_ID,
            name="Internal Library Storage",
            domain=BlockDomain.LIB,
            storage_kind="internal_lib",
            source_kind="internal",
            description="Technical storage root for the project internal library.",
        )

        def resolve_or_create_root(
            *,
            role: str,
            block_id: str,
            name: str,
            domain: BlockDomain,
            description: str,
            aliases: set[str] | None = None,
        ) -> Block:
            nonlocal changed
            aliases = aliases or set()
            candidate: Block | None = None
            for block in updated_blocks:
                if block.type != BlockType.CONTAINER or block.profile != "workspace_root":
                    continue
                block_role = self.workspace_root_role(block)
                if block_role == role:
                    candidate = block
                    break
                normalized_name = (block.name or "").strip().upper().replace(" ", "_")
                if block.id == block_id or block.id in aliases or normalized_name in aliases:
                    candidate = block
                    break
            if candidate is None:
                candidate = self.create_workspace_root_block(
                    block_id=block_id,
                    name=name,
                    domain=domain,
                    role=role,
                    description=description,
                )
                updated_blocks.append(candidate)
                by_id[candidate.id] = candidate
                changed = True

            ensure_role(candidate, role)
            if candidate.name != name:
                candidate.name = name
                changed = True
            if candidate.domain != domain:
                candidate.domain = domain
                changed = True
            if candidate.profile != "workspace_root":
                candidate.profile = "workspace_root"
                changed = True
            if candidate.type != BlockType.CONTAINER:
                candidate.type = BlockType.CONTAINER
                changed = True
            if candidate.tree is None:
                candidate.tree = FreeTree()
                changed = True
            if candidate.graph is None:
                candidate.graph = FreeGraph()
                changed = True
            candidate.contains = self.dedupe_ids(list(candidate.contains))
            return candidate

        characters_root = resolve_or_create_root(
            role="characters_root",
            block_id=CHARACTERS_ROOT_BLOCK_ID,
            name="Characters Root",
            domain=BlockDomain.CHARACTERS,
            description="Characters workspace root.",
            aliases={"CHARACTERS_ROOT", "CHARACTERSROOT"},
        )
        ensure_workspace_binding(characters_root, storage_root_id=project_storage_root.id, workspace_scope="project")
        story_root = resolve_or_create_root(
            role="story_root",
            block_id=STORY_ROOT_BLOCK_ID,
            name="Story Root",
            domain=BlockDomain.STORY,
            description="Story workspace root.",
            aliases={"STORY_ROOT", "STORYROOT"},
        )
        ensure_workspace_binding(story_root, storage_root_id=project_storage_root.id, workspace_scope="project")
        internal_lib_root = resolve_or_create_root(
            role="internal_lib",
            block_id=INTERNAL_LIB_ROOT_BLOCK_ID,
            name="INTERNALLIB",
            domain=BlockDomain.LIB,
            description="Internal import workspace root.",
            aliases={"INTERNAL_LIB", "INTERNALLIB"},
        )
        ensure_workspace_binding(internal_lib_root, storage_root_id=internal_storage_root.id, workspace_scope="internal")

        internal_lib_root.contains = self.dedupe_ids(internal_lib_root.contains)

        for storage_root, child_ids in (
            (project_storage_root, [characters_root.id, story_root.id]),
            (internal_storage_root, [internal_lib_root.id]),
        ):
            for child_id in child_ids:
                if child_id not in storage_root.contains:
                    storage_root.contains.append(child_id)
                    changed = True
            storage_root.contains = self.dedupe_ids(storage_root.contains)

        workspace_root_ids = {
            block.id
            for block in updated_blocks
            if block.type == BlockType.CONTAINER and block.profile == "workspace_root"
        }

        for block in updated_blocks:
            if block.type != BlockType.CONTAINER:
                continue
            original = list(block.contains)
            filtered: list[str] = []
            for child_id in original:
                if child_id in workspace_root_ids and block.profile != "storage_root":
                    continue
                filtered.append(child_id)
            deduped = self.dedupe_ids(filtered)
            if deduped != original:
                block.contains = deduped
                changed = True

        filtered_blocks = [
            block
            for block in updated_blocks
            if not (
                (
                    block.type == BlockType.CONTAINER
                    and block.profile == "workspace_root"
                    and (
                        block.id == "blk_project_root"
                        or block.as_container().workspace_role == "project_root"
                        or (block.name or "").strip().upper() == "PROJET"
                    )
                )
                or (
                    block.type == BlockType.CONTAINER
                    and block.profile == "workspace_root"
                    and (
                        block.id == "blk_lib_root"
                        or (
                            block.as_container().workspace_role == "library_root"
                            and block.as_container().workspace_scope in {"", "project"}
                            and block.as_container().storage_root_id in {"", project_storage_root.id}
                        )
                    )
                )
                or block.id == "blk_internal_lib_empty"
                or block.profile == "internal_lib_empty"
                or (
                    block.type == BlockType.EMPTY
                    and bool(block.content.get("internal_lib"))
                    and bool(block.content.get("drop_target"))
                )
            )
        ]
        if len(filtered_blocks) != len(updated_blocks):
            updated_blocks = filtered_blocks
            by_id = {block.id: block for block in updated_blocks}
            for block in updated_blocks:
                if block.type != BlockType.CONTAINER:
                    continue
                cleaned_contains = [child_id for child_id in block.contains if child_id in by_id]
                deduped = self.dedupe_ids(cleaned_contains)
                if deduped != block.contains:
                    block.contains = deduped
                    changed = True
            changed = True

        if changed:
            try:
                self._storage.save_blocks(project_path, updated_blocks)
            except Exception:
                return updated_blocks
        return updated_blocks
