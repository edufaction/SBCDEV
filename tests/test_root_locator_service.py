from application import RootLocatorService
from domain import Block, BlockDomain, BlockType


def test_root_locator_service_finds_workspace_root_by_role_and_scope() -> None:
    locator = RootLocatorService()
    storage_root = Block(
        id="blk_storage_project_root",
        type=BlockType.CONTAINER,
        profile="storage_root",
        name="Project Storage",
        domain=BlockDomain.LIB,
        content={"storage_kind": "project_space", "source_kind": "project"},
    )
    characters_root = Block(
        id="blk_characters_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="Characters Root",
        domain=BlockDomain.CHARACTERS,
        content={
            "workspace_role": "characters_root",
            "workspace_scope": "project",
            "storage_root_id": storage_root.id,
        },
    )
    internal_root = Block(
        id="blk_internal_lib_root",
        type=BlockType.CONTAINER,
        profile="workspace_root",
        name="INTERNALLIB",
        domain=BlockDomain.LIB,
        content={
            "workspace_role": "internal_lib",
            "workspace_scope": "internal",
            "storage_root_id": "blk_storage_internal_root",
        },
    )

    resolved = locator.find_workspace_root(
        [storage_root, characters_root, internal_root],
        role="characters_root",
        scope="project",
        storage_root_id=storage_root.id,
    )

    assert resolved is characters_root
