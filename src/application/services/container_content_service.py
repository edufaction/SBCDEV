from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

from application.block_import_utils import block_spec_from_imported_file
from application.session import ProjectSession
from domain import Block, BlockType, ValidationError
from infrastructure.storage import ProjectStorageService
from services import ContainerRulesService


@dataclass(slots=True)
class ImportRequest:
    container_id: str
    file_paths: list[str]
    target_block_id: str = ""
    graph_drop: tuple[float, float] | None = None
    source_tag: str = "workspace_toolbar"


@dataclass(slots=True)
class ContainerMutationResult:
    container_id: str
    affected_block_ids: list[str]
    message: str
    created_count: int = 0
    replaced_count: int = 0


class ContainerContentService:
    """Orchestrates note, placeholder and media insertion inside containers."""

    def __init__(
        self,
        *,
        storage: ProjectStorageService | None = None,
        container_rules: ContainerRulesService | None = None,
    ) -> None:
        self._storage = storage or ProjectStorageService()
        self._container_rules = container_rules or ContainerRulesService()

    def create_note(self, session: ProjectSession, *, container_id: str) -> ContainerMutationResult:
        project_root = session.project_root
        if project_root is None:
            raise ValueError("Open a project first.")
        container = self._require_container(session, container_id)

        use_case = session.rebuild_use_case()
        note = use_case.create_block(
            type=BlockType.TEXT,
            domain=container.domain,
            profile="note",
            name=self._next_note_name(session.blocks, container),
            tags=["note", "postit"],
            content={"text": "", "note_style": "postit"},
        )
        note.container_paths[container.id] = ""
        use_case.add_to_container(container.id, note.id)
        session.replace_blocks(use_case.list_blocks())
        return ContainerMutationResult(
            container_id=container.id,
            affected_block_ids=[note.id],
            created_count=1,
            message=f"Note created: {note.name or note.id}",
        )

    def create_placeholder(self, session: ProjectSession, *, container_id: str) -> ContainerMutationResult:
        project_root = session.project_root
        if project_root is None:
            raise ValueError("Open a project first.")
        container = self._require_container(session, container_id)
        if container.profile != "character_form":
            raise ValidationError("Only character forms can receive placeholder blocks.")

        use_case = session.rebuild_use_case()
        placeholder = use_case.create_block(
            type=BlockType.EMPTY,
            domain=container.domain,
            profile="placeholder",
            name=self._next_placeholder_name(session.blocks, container),
            description="Manual placeholder block.",
            tags=["placeholder", "workspace_toolbar"],
            content={"placeholder": True},
        )
        placeholder.container_paths[container.id] = ""
        use_case.add_to_container(container.id, placeholder.id)
        session.replace_blocks(use_case.list_blocks())
        return ContainerMutationResult(
            container_id=container.id,
            affected_block_ids=[placeholder.id],
            created_count=1,
            message=f"Placeholder created: {placeholder.name or placeholder.id}",
        )

    def import_files(self, session: ProjectSession, request: ImportRequest) -> ContainerMutationResult:
        project_root = session.project_root
        if project_root is None:
            raise ValueError("Open a project first.")
        container = self._require_container(session, request.container_id)
        if container.profile != "character_form":
            raise ValidationError("Only character forms can receive imported blocks.")

        valid_sources = self._existing_source_files(request.file_paths)
        if not valid_sources:
            raise ValueError("No file imported.")

        placeholder = self._resolve_placeholder_target(
            blocks=session.blocks,
            container=container,
            target_block_id=request.target_block_id,
        )
        use_case = session.rebuild_use_case()
        affected_ids: list[str] = []
        created_count = 0
        replaced_count = 0
        for index, source_path in enumerate(valid_sources):
            if placeholder is not None:
                self._replace_placeholder_with_imported_asset(
                    project_root=project_root,
                    container=container,
                    placeholder=placeholder,
                    source_path=source_path,
                    source_tag=request.source_tag,
                )
                affected_ids.append(placeholder.id)
                replaced_count += 1
                placeholder = None
                continue

            created = self._create_imported_block(
                project_root=project_root,
                use_case=use_case,
                container=container,
                source_path=source_path,
                source_tag=request.source_tag,
            )
            if request.graph_drop is not None:
                x, y = request.graph_drop
                offset = float(index * 28)
                use_case.move_block_in_graph(container.id, created.id, x=x + offset, y=y + offset)
            affected_ids.append(created.id)
            created_count += 1

        session.replace_blocks(use_case.list_blocks())
        return ContainerMutationResult(
            container_id=container.id,
            affected_block_ids=affected_ids,
            created_count=created_count,
            replaced_count=replaced_count,
            message=self._format_import_feedback(
                container=container,
                created_count=created_count,
                replaced_count=replaced_count,
            ),
        )

    @staticmethod
    def _existing_source_files(file_paths: list[str]) -> list[Path]:
        existing: list[Path] = []
        for raw_path in file_paths:
            source_path = Path(str(raw_path or "")).expanduser()
            if not source_path.exists() or not source_path.is_file():
                continue
            existing.append(source_path.resolve())
        return existing

    @staticmethod
    def _require_container(session: ProjectSession, container_id: str) -> Block:
        container = session.find_container(container_id)
        if container is None:
            raise ValueError("Target container not found.")
        return container

    @staticmethod
    def _resolve_placeholder_target(*, blocks: list[Block], container: Block, target_block_id: str) -> Block | None:
        normalized_target_id = str(target_block_id or "").strip()
        if not normalized_target_id or normalized_target_id not in container.contains:
            return None
        candidate = next((block for block in blocks if block.id == normalized_target_id), None)
        if candidate is None or candidate.type != BlockType.EMPTY:
            return None
        if candidate.profile.strip().lower() not in {"placeholder", "template_slot"}:
            return None
        return candidate

    @staticmethod
    def _preview_import_spec(source_path: Path) -> tuple[BlockType, str]:
        mime_type = mimetypes.guess_type(source_path.name)[0] or ""
        block_type, profile, _content = block_spec_from_imported_file(source_path, {"mime_type": mime_type})
        return block_type, profile

    def _validate_placeholder_import(self, *, container: Block, placeholder: Block, source_path: Path) -> None:
        block_type, profile = self._preview_import_spec(source_path)
        expected_types = [
            str(item).strip().lower()
            for item in placeholder.content.get("expected_types", [])
            if str(item).strip()
        ]
        if expected_types and block_type.value not in expected_types:
            allowed = ", ".join(sorted(expected_types))
            raise ValidationError(
                f"block type '{block_type.value}' is not allowed in placeholder '{placeholder.name or placeholder.id}'. "
                f"Allowed types: {allowed}"
            )
        candidate = Block(
            id=placeholder.id,
            type=block_type,
            domain=container.domain,
            profile=profile,
            name=source_path.stem or source_path.name,
        )
        self._container_rules.validate_child_link(parent=container, child=candidate)

    def _replace_placeholder_with_imported_asset(
        self,
        *,
        project_root: Path,
        container: Block,
        placeholder: Block,
        source_path: Path,
        source_tag: str,
    ) -> None:
        self._validate_placeholder_import(container=container, placeholder=placeholder, source_path=source_path)
        file_meta = self._storage.import_file(project_root, source_path)
        block_type, profile, content = block_spec_from_imported_file(source_path, file_meta)
        placeholder.type = block_type
        placeholder.profile = profile
        placeholder.name = source_path.stem or source_path.name
        placeholder.description = f"Imported from disk: {source_path.name}"
        placeholder.tags = ["imported", source_tag, block_type.value]
        placeholder.content = content
        placeholder.container_paths[container.id] = ""

    def _create_imported_block(
        self,
        *,
        project_root: Path,
        use_case,
        container: Block,
        source_path: Path,
        source_tag: str,
    ) -> Block:
        file_meta = self._storage.import_file(project_root, source_path)
        block_type, profile, content = block_spec_from_imported_file(source_path, file_meta)
        created = use_case.create_block(
            type=block_type,
            domain=container.domain,
            profile=profile,
            name=source_path.stem or source_path.name,
            description=f"Imported from disk: {source_path.name}",
            tags=["imported", source_tag, block_type.value],
            content=content,
        )
        created.container_paths[container.id] = ""
        use_case.add_to_container(container.id, created.id)
        return created

    @staticmethod
    def _format_import_feedback(*, container: Block, created_count: int, replaced_count: int) -> str:
        container_label = container.name or container.id
        if created_count and replaced_count:
            return (
                f"{created_count} block(s) imported into {container_label}; "
                f"{replaced_count} placeholder(s) filled."
            )
        if replaced_count:
            return f"{replaced_count} placeholder(s) filled in {container_label}."
        return f"{created_count} block(s) imported into {container_label}."

    @staticmethod
    def _next_note_name(blocks: list[Block], container: Block) -> str:
        by_id = {block.id: block for block in blocks}
        highest = 0
        for child_id in container.contains:
            child = by_id.get(child_id)
            if child is None or child.type != BlockType.TEXT or child.profile.strip().lower() != "note":
                continue
            label = (child.name or "").strip().lower()
            if label == "note":
                highest = max(highest, 1)
                continue
            if not label.startswith("note "):
                continue
            suffix = label.removeprefix("note ").strip()
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return f"Note {highest + 1}" if highest else "Note"

    @staticmethod
    def _next_placeholder_name(blocks: list[Block], container: Block) -> str:
        by_id = {block.id: block for block in blocks}
        highest = 0
        for child_id in container.contains:
            child = by_id.get(child_id)
            if child is None or child.type != BlockType.EMPTY or child.profile.strip().lower() != "placeholder":
                continue
            label = (child.name or "").strip().lower()
            if label == "placeholder":
                highest = max(highest, 1)
                continue
            if not label.startswith("placeholder "):
                continue
            suffix = label.removeprefix("placeholder ").strip()
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return f"Placeholder {highest + 1}" if highest else "Placeholder"
