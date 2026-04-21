from __future__ import annotations

from pathlib import Path

from application.free_tree_workspace_controller import FreeTreeWorkspaceController
from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree, FreeTreeNode
from infrastructure.storage import ProjectStorageService

PROJECT_ROOT_BLOCK_ID = "blk_project_root"
CHARACTERS_ROOT_BLOCK_ID = "blk_characters_root"
STORY_ROOT_BLOCK_ID = "blk_story_root"
LIB_ROOT_BLOCK_ID = "blk_lib_root"
INTERNAL_LIB_ROOT_BLOCK_ID = "blk_internal_lib_root"
INTERNAL_LIB_EMPTY_BLOCK_ID = "blk_internal_lib_empty"


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
    ) -> Block:
        return Block(
            id=block_id,
            type=BlockType.CONTAINER,
            profile="workspace_root",
            name=name,
            description=description,
            domain=domain,
            shared=False,
            tags=["workspace_root", role],
            content={"workspace_role": role},
            tree=FreeTree(),
            graph=FreeGraph(),
        )

    @classmethod
    def default_workspace_structure_blocks(cls) -> list[Block]:
        project_root = cls.create_workspace_root_block(
            block_id=PROJECT_ROOT_BLOCK_ID,
            name="PROJET",
            domain=BlockDomain.LIB,
            role="project_root",
            description="Project root container.",
        )
        characters_root = cls.create_workspace_root_block(
            block_id=CHARACTERS_ROOT_BLOCK_ID,
            name="Characters Root",
            domain=BlockDomain.CHARACTERS,
            role="characters_root",
            description="Characters workspace root.",
        )
        story_root = cls.create_workspace_root_block(
            block_id=STORY_ROOT_BLOCK_ID,
            name="Story Root",
            domain=BlockDomain.STORY,
            role="story_root",
            description="Story workspace root.",
        )
        lib_root = cls.create_workspace_root_block(
            block_id=LIB_ROOT_BLOCK_ID,
            name="Library Root",
            domain=BlockDomain.LIB,
            role="library_root",
            description="Library workspace root.",
        )
        internal_lib_root = cls.create_workspace_root_block(
            block_id=INTERNAL_LIB_ROOT_BLOCK_ID,
            name="INTERNALLIB",
            domain=BlockDomain.LIB,
            role="internal_lib",
            description="Internal import workspace root.",
        )
        internal_lib_empty = Block(
            id=INTERNAL_LIB_EMPTY_BLOCK_ID,
            type=BlockType.EMPTY,
            profile="internal_lib_empty",
            name="Drop Resources Here",
            description="Drop a resource thumbnail on INTERNALLIB to create a new block in this container.",
            domain=BlockDomain.LIB,
            shared=False,
            tags=["internal_lib", "empty", "dropzone"],
            content={"internal_lib": True, "drop_target": True},
        )
        internal_lib_root.contains = [internal_lib_empty.id]
        project_root.contains = [characters_root.id, story_root.id, lib_root.id, internal_lib_root.id]
        return [project_root, characters_root, story_root, lib_root, internal_lib_root, internal_lib_empty]

    @staticmethod
    def workspace_root_role(block: Block) -> str:
        if block.type != BlockType.CONTAINER or block.profile != "workspace_root":
            return ""
        role = block.as_container().workspace_role
        if role:
            return role
        normalized_name = (block.name or "").strip().upper().replace(" ", "_")
        if block.id == PROJECT_ROOT_BLOCK_ID or normalized_name == "PROJET":
            return "project_root"
        if block.id == INTERNAL_LIB_ROOT_BLOCK_ID:
            return "internal_lib"
        if normalized_name in {"INTERNALLIB", "INTERNAL_LIB"}:
            return "internal_lib"
        if block.id == CHARACTERS_ROOT_BLOCK_ID or "CHAR" in normalized_name:
            return "characters_root"
        if block.id == STORY_ROOT_BLOCK_ID or "STORY" in normalized_name:
            return "story_root"
        if block.id == LIB_ROOT_BLOCK_ID or ("LIB" in normalized_name and "INTERNAL" not in normalized_name):
            return "library_root"
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

        updated_blocks, migrated_legacy = self.migrate_legacy_workspace_aliases(project_path, list(blocks))
        path_migration_changed = self.migrate_legacy_project_tree_to_block_paths(project_path, updated_blocks)
        by_id = {block.id: block for block in updated_blocks}
        changed = migrated_legacy or path_migration_changed

        def ensure_role(block: Block, role: str) -> None:
            nonlocal changed
            if block.as_container().workspace_role != role:
                block.content["workspace_role"] = role
                changed = True

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

        project_root = resolve_or_create_root(
            role="project_root",
            block_id=PROJECT_ROOT_BLOCK_ID,
            name="PROJET",
            domain=BlockDomain.LIB,
            description="Project root container.",
            aliases={"PROJET"},
        )
        characters_root = resolve_or_create_root(
            role="characters_root",
            block_id=CHARACTERS_ROOT_BLOCK_ID,
            name="Characters Root",
            domain=BlockDomain.CHARACTERS,
            description="Characters workspace root.",
            aliases={"CHARACTERS_ROOT", "CHARACTERSROOT"},
        )
        story_root = resolve_or_create_root(
            role="story_root",
            block_id=STORY_ROOT_BLOCK_ID,
            name="Story Root",
            domain=BlockDomain.STORY,
            description="Story workspace root.",
            aliases={"STORY_ROOT", "STORYROOT"},
        )
        lib_root = resolve_or_create_root(
            role="library_root",
            block_id=LIB_ROOT_BLOCK_ID,
            name="Library Root",
            domain=BlockDomain.LIB,
            description="Library workspace root.",
            aliases={"LIB_ROOT", "LIBRARY_ROOT", "LIBRARYROOT"},
        )
        internal_lib_root = resolve_or_create_root(
            role="internal_lib",
            block_id=INTERNAL_LIB_ROOT_BLOCK_ID,
            name="INTERNALLIB",
            domain=BlockDomain.LIB,
            description="Internal import workspace root.",
            aliases={"INTERNAL_LIB", "INTERNALLIB"},
        )

        internal_empty = by_id.get(INTERNAL_LIB_EMPTY_BLOCK_ID)
        if internal_empty is None:
            for child_id in internal_lib_root.contains:
                child = by_id.get(child_id)
                if child is not None and child.type == BlockType.EMPTY:
                    internal_empty = child
                    break
        if internal_empty is None:
            internal_empty = Block(
                id=INTERNAL_LIB_EMPTY_BLOCK_ID,
                type=BlockType.EMPTY,
                profile="internal_lib_empty",
                name="Drop Resources Here",
                description="Drop a resource thumbnail on INTERNALLIB to create a new block in this container.",
                domain=BlockDomain.LIB,
                shared=False,
                tags=["internal_lib", "empty", "dropzone"],
                content={"internal_lib": True, "drop_target": True},
            )
            updated_blocks.append(internal_empty)
            by_id[internal_empty.id] = internal_empty
            changed = True
        else:
            if not internal_empty.as_container().drop_target:
                internal_empty.content["drop_target"] = True
                changed = True
            if not internal_empty.as_container().internal_lib:
                internal_empty.content["internal_lib"] = True
                changed = True
            if not internal_empty.name.strip():
                internal_empty.name = "Drop Resources Here"
                changed = True
            expected_description = "Drop a resource thumbnail on INTERNALLIB to create a new block in this container."
            if internal_empty.description != expected_description:
                internal_empty.description = expected_description
                changed = True

        if internal_empty.id not in internal_lib_root.contains:
            internal_lib_root.contains.append(internal_empty.id)
            changed = True
        internal_lib_root.contains = self.dedupe_ids(internal_lib_root.contains)

        workspace_root_ids = {
            block.id
            for block in updated_blocks
            if block.type == BlockType.CONTAINER and block.profile == "workspace_root"
        }
        expected_children = [characters_root.id, story_root.id, lib_root.id, internal_lib_root.id]
        for child_id in expected_children:
            if child_id not in project_root.contains:
                project_root.contains.append(child_id)
                changed = True
        for child_id in sorted(workspace_root_ids):
            if child_id == project_root.id:
                continue
            if child_id not in project_root.contains:
                project_root.contains.append(child_id)
                changed = True
        project_root.contains = self.dedupe_ids(project_root.contains)

        for block in updated_blocks:
            if block.type != BlockType.CONTAINER:
                continue
            original = list(block.contains)
            filtered: list[str] = []
            for child_id in original:
                if child_id == project_root.id:
                    continue
                if block.id != project_root.id and child_id in workspace_root_ids:
                    continue
                filtered.append(child_id)
            deduped = self.dedupe_ids(filtered)
            if deduped != original:
                block.contains = deduped
                changed = True

        if changed:
            try:
                self._storage.save_blocks(project_path, updated_blocks)
            except Exception:
                return updated_blocks
        return updated_blocks

    def migrate_legacy_workspace_aliases(
        self,
        project_path: Path,
        blocks: list[Block],
    ) -> tuple[list[Block], bool]:
        id_mapping = {
            "blk_virtual_root": INTERNAL_LIB_ROOT_BLOCK_ID,
            "blk_virtual_empty": INTERNAL_LIB_EMPTY_BLOCK_ID,
        }
        if not any(block.id in id_mapping for block in blocks):
            return blocks, False

        changed = False
        working = list(blocks)
        by_id = {block.id: block for block in working}
        remove_ids: set[str] = set()

        for legacy_id, new_id in id_mapping.items():
            legacy = by_id.get(legacy_id)
            if legacy is None:
                continue
            existing = by_id.get(new_id)
            if existing is not None and existing is not legacy:
                for child_id in legacy.contains:
                    if child_id not in existing.contains:
                        existing.contains.append(child_id)
                remove_ids.add(legacy_id)
                changed = True
                continue
            legacy.id = new_id
            changed = True

        if remove_ids:
            working = [block for block in working if block.id not in remove_ids]

        for block in working:
            original_contains = list(block.contains)
            block.contains = [id_mapping.get(child_id, child_id) for child_id in block.contains if child_id not in remove_ids]
            block.contains = self.dedupe_ids(block.contains)
            if block.contains != original_contains:
                changed = True

            for input_connection in block.inputs:
                mapped_source = id_mapping.get(input_connection.source_block_id, input_connection.source_block_id)
                if mapped_source != input_connection.source_block_id:
                    input_connection.source_block_id = mapped_source
                    changed = True

            if block.tree is not None:
                for node in block.tree.nodes.values():
                    if node.block_id in remove_ids:
                        node.block_id = None
                        changed = True
                    elif node.block_id in id_mapping:
                        node.block_id = id_mapping[node.block_id]
                        changed = True

            if block.graph is not None:
                for node in block.graph.nodes.values():
                    mapped = id_mapping.get(node.block_id, node.block_id)
                    if mapped != node.block_id:
                        node.block_id = mapped
                        changed = True

        for block in working:
            if block.id == INTERNAL_LIB_ROOT_BLOCK_ID:
                if block.name != "INTERNALLIB":
                    block.name = "INTERNALLIB"
                    changed = True
                if block.profile != "workspace_root":
                    block.profile = "workspace_root"
                    changed = True
                if block.domain != BlockDomain.LIB:
                    block.domain = BlockDomain.LIB
                    changed = True
                if block.as_container().workspace_role != "internal_lib":
                    block.content["workspace_role"] = "internal_lib"
                    changed = True
            if block.id == INTERNAL_LIB_EMPTY_BLOCK_ID:
                if block.profile != "internal_lib_empty":
                    block.profile = "internal_lib_empty"
                    changed = True
                if not block.as_container().internal_lib:
                    block.content["internal_lib"] = True
                    changed = True
                if not block.as_container().drop_target:
                    block.content["drop_target"] = True
                    changed = True

        if not changed:
            return working, False

        try:
            ui_state = self._storage.load_ui_state(project_path)
            tree_key = "project_free_tree"
            payload = ui_state.get(tree_key)
            if isinstance(payload, dict):
                nodes = payload.get("nodes")
                if isinstance(nodes, dict):
                    for node_data in nodes.values():
                        if not isinstance(node_data, dict):
                            continue
                        block_id = node_data.get("block_id")
                        if isinstance(block_id, str) and block_id in id_mapping:
                            node_data["block_id"] = id_mapping[block_id]
                        node_name = node_data.get("name")
                        if (
                            isinstance(node_name, str)
                            and node_data.get("block_id") == INTERNAL_LIB_ROOT_BLOCK_ID
                            and node_name.strip().upper() == "VIRTUAL"
                        ):
                            node_data["name"] = "INTERNALLIB"
                    renamed_nodes: dict[str, dict] = {}
                    for node_id, node_data in nodes.items():
                        if not isinstance(node_id, str):
                            continue
                        new_node_id = self.replace_ids_in_text(node_id, id_mapping)
                        if isinstance(node_data, dict):
                            node_data["id"] = self.replace_ids_in_text(str(node_data.get("id", new_node_id)), id_mapping)
                            children = node_data.get("children")
                            if isinstance(children, list):
                                node_data["children"] = [
                                    self.replace_ids_in_text(str(child_id), id_mapping) for child_id in children
                                ]
                        renamed_nodes[new_node_id] = node_data
                    payload["nodes"] = renamed_nodes
                root_ids = payload.get("root_ids")
                if isinstance(root_ids, list):
                    payload["root_ids"] = [self.replace_ids_in_text(str(node_id), id_mapping) for node_id in root_ids]
                ui_state[tree_key] = payload
                self._storage.save_ui_state(project_path, ui_state)
        except Exception:
            pass

        return working, True

    def migrate_legacy_project_tree_to_block_paths(self, project_path: Path, blocks: list[Block]) -> bool:
        persisted_tree = self.load_legacy_project_free_tree(project_path)
        if persisted_tree is None:
            return False

        controller = FreeTreeWorkspaceController()
        controller.set_blocks(blocks)
        before = {block.id: dict(block.container_paths) for block in blocks}
        controller.apply_persisted_tree(persisted_tree)
        after = {block.id: dict(block.container_paths) for block in blocks}
        changed = before != after
        if not changed:
            return False

        try:
            ui_state = self._storage.load_ui_state(project_path)
            if "project_free_tree" in ui_state:
                ui_state.pop("project_free_tree", None)
                self._storage.save_ui_state(project_path, ui_state)
        except Exception:
            pass
        return True

    def load_legacy_project_free_tree(self, project_path: Path) -> FreeTree | None:
        try:
            ui_state = self._storage.load_ui_state(project_path)
        except Exception:
            return None
        payload = ui_state.get("project_free_tree")
        if not isinstance(payload, dict):
            return None
        return self.legacy_tree_from_payload(payload)

    @staticmethod
    def legacy_tree_from_payload(data: dict) -> FreeTree | None:
        nodes = {
            node_id: FreeTreeNode(
                id=str(node_data.get("id", node_id)),
                kind=str(node_data.get("kind", "folder")),
                name=str(node_data.get("name", "")),
                block_id=(str(node_data.get("block_id")) if node_data.get("block_id") is not None else None),
                children=[str(child_id) for child_id in node_data.get("children", [])],
            )
            for node_id, node_data in data.get("nodes", {}).items()
            if isinstance(node_data, dict)
        }
        if not nodes:
            return None
        referenced_ids = {
            child_id
            for node in nodes.values()
            for child_id in node.children
            if child_id in nodes
        }
        root_ids = [
            str(node_id)
            for node_id in data.get("root_ids", [])
            if str(node_id) in nodes and str(node_id) not in referenced_ids
        ]
        for node_id in nodes:
            if node_id in root_ids:
                continue
            if node_id not in referenced_ids:
                root_ids.append(node_id)
        return FreeTree(root_ids=root_ids, nodes=nodes)
