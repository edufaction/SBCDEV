from __future__ import annotations

"""Rules engine controlling which child blocks can be attached to containers."""

from dataclasses import dataclass
import unicodedata

from domain import Block, BlockType, ValidationError


@dataclass(frozen=True, slots=True)
class ContainerChildRule:
    """Allowed child constraints for one parent container profile."""

    allowed_child_types: set[BlockType] | None = None
    allowed_child_profiles: set[str] | None = None


_ALIAS_BY_PROFILE: dict[str, str] = {
    "caractere": "character",
    "caractere_form": "character_form",
}


def _normalize_profile(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    return _ALIAS_BY_PROFILE.get(normalized, normalized)


_DEFAULT_RULES: dict[str, ContainerChildRule] = {
    "character": ContainerChildRule(
        allowed_child_types={BlockType.CONTAINER},
        allowed_child_profiles={"character_form"},
    ),
    "character_form": ContainerChildRule(
        allowed_child_types={
            BlockType.EMPTY,
            BlockType.IMAGE,
            BlockType.VIDEO,
            BlockType.PROMPT,
            BlockType.TEXT,
            BlockType.AUDIO,
        }
    ),
}


class ContainerRulesService:
    """Validates parent/child compatibility for container links."""

    def __init__(self, rules: dict[str, ContainerChildRule] | None = None) -> None:
        self._rules = rules or _DEFAULT_RULES

    def validate_child_link(self, *, parent: Block, child: Block) -> None:
        if parent.type != BlockType.CONTAINER:
            raise ValidationError(f"target block is not a container: {parent.id}")

        parent_profile = _normalize_profile(parent.profile)
        child_profile = _normalize_profile(child.profile)

        rule = self._rules.get(parent_profile)
        if rule is None:
            return

        if rule.allowed_child_types is not None and child.type not in rule.allowed_child_types:
            allowed_types = ", ".join(sorted(item.value for item in rule.allowed_child_types))
            raise ValidationError(
                f"block type '{child.type.value}' is not allowed in container profile '{parent.profile}'. "
                f"Allowed types: {allowed_types}"
            )

        if rule.allowed_child_profiles is not None and child_profile not in rule.allowed_child_profiles:
            allowed_profiles = ", ".join(sorted(rule.allowed_child_profiles))
            raise ValidationError(
                f"block profile '{child.profile}' is not allowed in container profile '{parent.profile}'. "
                f"Allowed profiles: {allowed_profiles}"
            )
