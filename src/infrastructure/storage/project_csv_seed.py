from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree, InputConnection, PortType

from .project_storage_service import ProjectStorageService


def seed_project_from_csv(
    *,
    project_path: Path,
    project_name: str,
    csv_path: Path,
    assets_source_project_path: Path | None = None,
) -> list[Block]:
    storage = ProjectStorageService()
    storage.create_project(project_path, project_name)
    blocks = load_blocks_from_csv(csv_path)
    storage.save_blocks(project_path, blocks)
    if assets_source_project_path is not None:
        copy_assets_from_project(assets_source_project_path, project_path)
    return blocks


def ensure_test_project_from_data_dir(
    data_project_dir: Path,
    *,
    project_name: str = "TESTPROJ",
    csv_filename: str = "example_project_blocks.csv",
) -> Path:
    project_path = data_project_dir / project_name
    csv_path = data_project_dir / csv_filename
    assets_source = find_assets_source_project(data_project_dir)
    seed_project_from_csv(
        project_path=project_path,
        project_name=project_name,
        csv_path=csv_path,
        assets_source_project_path=assets_source,
    )
    return project_path


def find_assets_source_project(data_project_dir: Path) -> Path | None:
    for folder_name in ("PROJET", "projet", "project", "PROJECT"):
        candidate = data_project_dir / folder_name
        if (candidate / "storage" / "files").exists():
            return candidate
    return None


def load_blocks_from_csv(csv_path: Path) -> list[Block]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_block_from_row(row) for row in reader if row.get("id", "").strip()]


def copy_assets_from_project(source_project_path: Path, target_project_path: Path) -> int:
    source_files = source_project_path / "storage" / "files"
    target_files = target_project_path / "storage" / "files"
    if not source_files.exists():
        return 0

    if source_files.resolve() == target_files.resolve():
        return 0

    copied = 0
    for source in source_files.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_files)
        destination = target_files / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1
    return copied


def _block_from_row(row: dict[str, str]) -> Block:
    block_type = _as_block_type(row.get("type", ""))
    content = _parse_content(row.get("content_json", ""))

    prompt_generated = ""
    if isinstance(content.get("prompt_generated"), str):
        prompt_generated = content["prompt_generated"].strip()
    elif isinstance(content.get("prompt"), str):
        prompt_generated = content["prompt"].strip()

    tree = FreeTree() if block_type == BlockType.CONTAINER else None
    graph = FreeGraph() if block_type == BlockType.CONTAINER else None

    return Block(
        id=row["id"].strip(),
        type=block_type,
        profile=(row.get("profile", "").strip() or "generic"),
        name=(row.get("name", "").strip() or row["id"].strip()),
        description=row.get("description", "").strip(),
        prompt_generated=prompt_generated,
        shared=_parse_bool(row.get("shared", "")),
        domain=_as_block_domain(row.get("domain", "")),
        tags=_parse_tags(row.get("tags", "")),
        content=content,
        contains=_parse_contains(row.get("contains_ids", "")),
        inputs=_parse_input_links(row.get("input_links", "")),
        tree=tree,
        graph=graph,
    )


def _as_block_type(value: str) -> BlockType:
    try:
        return BlockType(value.strip().lower())
    except ValueError:
        return BlockType.TEXT


def _as_block_domain(value: str) -> BlockDomain:
    try:
        return BlockDomain(value.strip().lower())
    except ValueError:
        return BlockDomain.LIB


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_tags(raw_tags: str) -> list[str]:
    if not raw_tags.strip():
        return []
    return [item.strip() for item in raw_tags.split("|") if item.strip()]


def _parse_contains(raw_contains: str) -> list[str]:
    if not raw_contains.strip():
        return []
    return [item.strip() for item in raw_contains.split(";") if item.strip()]


def _parse_content(raw_content: str) -> dict:
    text = raw_content.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_input_links(raw_links: str) -> list[InputConnection]:
    if not raw_links.strip():
        return []

    inputs: list[InputConnection] = []
    for index, raw_link in enumerate(part.strip() for part in raw_links.split(";")):
        if not raw_link:
            continue
        parts = [part.strip() for part in raw_link.split("|")]
        if len(parts) < 2:
            continue

        source_block_id = parts[0]
        port = _as_port(parts[1])
        name = parts[2] if len(parts) >= 3 else ""

        inputs.append(
            InputConnection(
                source_block_id=source_block_id,
                port=port,
                name=name,
                order=index,
            )
        )
    return inputs


def _as_port(value: str) -> PortType:
    try:
        return PortType(value.strip().lower())
    except ValueError:
        return PortType.IN
