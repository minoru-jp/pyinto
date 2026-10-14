"""Late rendering of a tree of target layout templates and named Slots.

The tree holds *placement*, not a target-language AST. No child is converted
into text while recipes are selected or while parent/child layouts are joined.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pyinto.constructs import ConstructError
from pyinto.constructs.types import PortType, ValueType

if TYPE_CHECKING:
    from pyinto.realizations.registry import EmitContext

PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z_0-9]*)\}")


def holes_in(template: str) -> set[str]:
    return set(PLACEHOLDER.findall(template))


def holes_in_order(template: str) -> tuple[str, ...]:
    """Unique Slots in first-use order, for deterministic recursive composition."""
    return tuple(dict.fromkeys(PLACEHOLDER.findall(template)))


@dataclass(frozen=True)
class TemplatePlan:
    """A Realization's placement and extra named Slot sources.

    Slot sources are Model or Layout parts, not rendered text. The original
    Construct remains unchanged; the Composer attaches and validates them.
    """

    source: str
    slots: Mapping[str, object]


@dataclass(frozen=True)
class Text:
    value: str


@dataclass(frozen=True)
class Joined:
    children: tuple[object, ...]
    separator: str = "\n"


@dataclass(frozen=True)
class Template:
    """A target layout and attached, still-unrendered Slot values."""

    source: str
    slots: Mapping[str, Layout]

    def __post_init__(self) -> None:
        missing = holes_in(self.source) - self.slots.keys()
        if missing:
            raise ConstructError(f"Unfilled template holes: {sorted(missing)}")


@dataclass(frozen=True)
class Name:
    value: str


@dataclass(frozen=True)
class TypeName:
    """Unmodified Model value/Port type, serialized only at final rendering."""

    value_type: ValueType | PortType


@dataclass(frozen=True)
class Requirements:
    """Render requirements after the entire Construct tree was composed."""


Layout = Text | Joined | Template | Name | TypeName | Requirements


def render(node: Layout, context: EmitContext) -> str:
    """Only final rendering serializes the layout tree to source text."""
    if isinstance(node, Text):
        return node.value
    if isinstance(node, Name):
        return context.registry.name(node.value)
    if isinstance(node, TypeName):
        return context.registry.type_name(node.value_type)
    if isinstance(node, Requirements):
        return context.registry.requirements(context)
    if isinstance(node, Joined):
        return node.separator.join(
            render(cast(Layout, child), context) for child in node.children
        )
    if not isinstance(node, Template):
        raise ConstructError(f"Invalid layout fragment: {type(node).__name__}")
    lines: list[str] = []
    for line in node.source.split("\n"):
        stripped = line.lstrip(" \t")
        match = PLACEHOLDER.fullmatch(stripped)
        if match:
            value = render(node.slots[match.group(1)], context)
            if value:
                indent = line[: len(line) - len(stripped)]
                lines.extend(
                    indent + item if item else item for item in value.split("\n")
                )
        else:

            def substitute(found: re.Match[str]) -> str:
                value = render(node.slots[found.group(1)], context)
                if "\n" in value:
                    raise ConstructError("Multiline Slot must occupy its own line")
                return value

            lines.append(PLACEHOLDER.sub(substitute, line))
    return "\n".join(lines)
