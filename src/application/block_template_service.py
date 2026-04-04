from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from uuid import uuid4

from domain import Block, BlockDomain, BlockType, FreeGraph, FreeTree


@dataclass(frozen=True, slots=True)
class TemplateSlotSpec:
    key: str
    name: str
    expected_types: tuple[BlockType, ...] = (BlockType.IMAGE,)


@dataclass(frozen=True, slots=True)
class TemplateFormSpec:
    key: str
    name: str
    slots: tuple[TemplateSlotSpec, ...]


@dataclass(frozen=True, slots=True)
class CharacterTemplateSpec:
    key: str
    label: str
    forms: tuple[TemplateFormSpec, ...]


CHARACTER_STANDARD_TEMPLATE = CharacterTemplateSpec(
    key="character_standard",
    label="Character Standard",
    forms=(
        TemplateFormSpec(
            key="references",
            name="References",
            slots=(
                TemplateSlotSpec(key="front_view", name="Front View", expected_types=(BlockType.IMAGE,)),
                TemplateSlotSpec(key="side_view", name="Side View", expected_types=(BlockType.IMAGE,)),
                TemplateSlotSpec(key="back_view", name="Back View", expected_types=(BlockType.IMAGE,)),
                TemplateSlotSpec(key="face_reference", name="Face Reference", expected_types=(BlockType.IMAGE,)),
                TemplateSlotSpec(key="voice_reference", name="Voice Reference", expected_types=(BlockType.AUDIO,)),
            ),
        ),
        TemplateFormSpec(
            key="character_sheet",
            name="Character Sheet",
            slots=(
                TemplateSlotSpec(key="sheet_main", name="Character Sheet", expected_types=(BlockType.IMAGE,)),
                TemplateSlotSpec(key="pose_turnaround", name="Pose Turnaround", expected_types=(BlockType.VIDEO,)),
                TemplateSlotSpec(key="notes", name="Notes", expected_types=(BlockType.TEXT,)),
                TemplateSlotSpec(key="prompt_base", name="Prompt Base", expected_types=(BlockType.PROMPT,)),
            ),
        ),
    ),
)


class BlockTemplateService:
    """Factory for template-based block hierarchies."""

    def __init__(self, templates: dict[str, CharacterTemplateSpec] | None = None) -> None:
        self._templates = templates or {CHARACTER_STANDARD_TEMPLATE.key: CHARACTER_STANDARD_TEMPLATE}

    def available_character_templates(self) -> list[CharacterTemplateSpec]:
        return list(self._templates.values())

    def instantiate_character_template(
        self,
        *,
        character_name: str,
        template_key: str = "character_standard",
        domain: BlockDomain = BlockDomain.CHARACTERS,
    ) -> list[Block]:
        template = self._templates.get(template_key)
        if template is None:
            raise ValueError(f"unknown character template: {template_key}")

        resolved_name = character_name.strip() or "Character"
        name_token = self._slug_token(resolved_name)
        blocks: list[Block] = []

        character_block = Block(
            id=f"blk_character_{name_token}_{uuid4().hex[:6]}",
            type=BlockType.CONTAINER,
            profile="character",
            name=resolved_name,
            description=f"Template root for character: {resolved_name}",
            domain=domain,
            tags=["template", "character", template.key],
            content={"template_key": template.key, "template_label": template.label},
            tree=FreeTree(),
            graph=FreeGraph(),
        )
        blocks.append(character_block)

        for form in template.forms:
            form_block = Block(
                id=f"blk_character_form_{form.key}_{uuid4().hex[:6]}",
                type=BlockType.CONTAINER,
                profile="character_form",
                name=f"{resolved_name} - {form.name}",
                description=f"Template form '{form.name}' for {resolved_name}",
                domain=domain,
                tags=["template", "character_form", form.key],
                content={
                    "template_key": template.key,
                    "template_label": template.label,
                    "template_form_key": form.key,
                    "template_form_name": form.name,
                },
                tree=FreeTree(),
                graph=FreeGraph(),
            )
            character_block.contains.append(form_block.id)
            blocks.append(form_block)

            for slot in form.slots:
                slot_block = Block(
                    id=f"blk_slot_{slot.key}_{uuid4().hex[:6]}",
                    type=BlockType.EMPTY,
                    profile="template_slot",
                    name=slot.name,
                    description=f"Template slot '{slot.name}'",
                    domain=domain,
                    tags=["template", "slot", slot.key],
                    content={
                        "template_slot": True,
                        "drop_target": True,
                        "template_key": template.key,
                        "template_form_key": form.key,
                        "template_slot_key": slot.key,
                        "expected_types": [item.value for item in slot.expected_types],
                    },
                )
                form_block.contains.append(slot_block.id)
                blocks.append(slot_block)

        return blocks

    @staticmethod
    def _slug_token(value: str) -> str:
        normalized = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
            .strip()
        )
        token = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
        return token or "character"
