from domain import (
    Block,
    BlockAccessMode,
    BlockDomain,
    BlockProvenanceKind,
    BlockType,
    PortType,
    ValidationError,
)
from infrastructure.repositories import BlockRepository
from infrastructure.storage.serialization import block_from_dict, block_to_dict
from services import BlockService
from application import UseCaseService


def test_block_from_dict_defaults_to_owned_local_when_fields_are_missing() -> None:
    legacy_payload = {
        "id": "blk_legacy",
        "type": "image",
        "profile": "asset",
        "name": "Legacy Image",
        "domain": "lib",
        "content": {},
        "contains": [],
        "inputs": [],
        "tree": None,
        "graph": None,
    }

    block = block_from_dict(legacy_payload)

    assert block.access_mode is BlockAccessMode.OWNED
    assert block.provenance.get("kind") == BlockProvenanceKind.LOCAL.value


def test_block_from_dict_normalizes_link_provenance_kind() -> None:
    payload = {
        "id": "blk_link",
        "type": "image",
        "profile": "asset",
        "name": "Linked Image",
        "domain": "lib",
        "access_mode": "link",
        "provenance": {"kind": "local", "mount_id": "lib_mount_001"},
        "content": {},
        "contains": [],
        "inputs": [],
        "tree": None,
        "graph": None,
    }

    block = block_from_dict(payload)
    assert block.access_mode is BlockAccessMode.LINK
    assert block.provenance.get("kind") == BlockProvenanceKind.LIB_LINK.value
    assert block.provenance.get("mount_id") == "lib_mount_001"


def test_block_to_dict_persists_access_mode_and_provenance() -> None:
    block = Block(
        id="blk_1",
        type=BlockType.IMAGE,
        profile="asset",
        name="Image",
        domain=BlockDomain.LIB,
        access_mode=BlockAccessMode.LINK,
        provenance={
            "kind": BlockProvenanceKind.LIB_LINK.value,
            "mount_id": "lib_mount_abc",
            "source_block_id": "lib_img_1",
        },
    )

    payload = block_to_dict(block)
    assert payload["access_mode"] == "link"
    assert payload["provenance"]["kind"] == BlockProvenanceKind.LIB_LINK.value
    assert payload["provenance"]["mount_id"] == "lib_mount_abc"


def test_block_service_rejects_update_on_link_block() -> None:
    service = BlockService(BlockRepository())
    link_block = service.create_block(
        block_type=BlockType.IMAGE,
        profile="asset",
        name="Linked Ref",
        domain=BlockDomain.LIB,
        access_mode=BlockAccessMode.LINK,
        provenance={"kind": "lib_link", "mount_id": "m1", "source_block_id": "s1"},
    )

    link_block.comment = "attempted edit"
    try:
        service.update_block(link_block)
        assert False, "Expected ValidationError for LINK block update"
    except ValidationError:
        pass


def test_block_service_rejects_input_changes_on_link_target() -> None:
    service = BlockService(BlockRepository())
    target = service.create_block(
        block_type=BlockType.IMAGE,
        profile="asset",
        name="Linked Target",
        access_mode=BlockAccessMode.LINK,
        provenance={"kind": "lib_link", "mount_id": "m1", "source_block_id": "s1"},
    )
    source = service.create_block(block_type=BlockType.IMAGE, profile="asset", name="Source")

    try:
        service.add_input(target_id=target.id, source_block_id=source.id, port=PortType.IN)
        assert False, "Expected ValidationError for LINK block input update"
    except ValidationError:
        pass


def test_use_case_create_block_from_library_source_supports_clone_and_link() -> None:
    use_case = UseCaseService(BlockService(BlockRepository()))
    source = Block(
        id="lib_source_block",
        type=BlockType.IMAGE,
        profile="asset",
        name="Source from LIB",
        domain=BlockDomain.LIB,
    )

    clone = use_case.create_block_from_library_source(
        source_block=source,
        mount_id="lib_mount_01",
        source_workspace_id="library_01",
        source_workspace_path="/tmp/library_01",
        as_link=False,
    )
    link = use_case.create_block_from_library_source(
        source_block=source,
        mount_id="lib_mount_01",
        source_workspace_id="library_01",
        source_workspace_path="/tmp/library_01",
        as_link=True,
    )

    assert clone.access_mode is BlockAccessMode.OWNED
    assert clone.provenance.get("kind") == BlockProvenanceKind.LIB_CLONE.value
    assert clone.provenance.get("source_block_id") == source.id

    assert link.access_mode is BlockAccessMode.LINK
    assert link.provenance.get("kind") == BlockProvenanceKind.LIB_LINK.value
    assert link.provenance.get("source_block_id") == source.id
