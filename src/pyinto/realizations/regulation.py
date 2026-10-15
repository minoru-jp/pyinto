"""Plain class-attribute declarations for Target Pack entries and Packs.

A realization entry is a class decorated with ``@realizes(element)`` (or the
naming policy marker ``@naming``) whose body assigns declaration values with
ordinary ``=``::

    @realizes(lang.While)
    class CWhile:
        template = "while (${condition}) {\n    ${body}\n}"

A Target Pack is an undecorated class passed explicitly to
``RealizationRegistry.from_pack()``::

    class CTargetPack:
        target = "c"
        entries = (CWhile,)

Only names declared directly in the class body are read. Unknown public names,
values of the wrong type, and inherited declarations are rejected when the
class is registered. Use a leading underscore for helper attributes.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from typing import TypeVar, cast

from pyinto._declaration import Declaration, Field, marker, require
from pyinto.constructs import Construct, Program
from pyinto.constructs.types import MappedType, ValueKind
from pyinto.interfaces.builtins import PrintCall
from pyinto.model.kinds import ELEMENTS, KindElement
from pyinto.realizations.layout import holes_in
from pyinto.realizations.runtime import is_runtime_schema

C = TypeVar("C", bound=type)

ENTRY_FIELDS: dict[str, Field] = {
    "variant": Field(str),
    "template": Field(str),
    "render": Field(),
    "visit": Field(),
    "type_name": Field(),
    "accepts": Field(tuple),
    "supports": Field(tuple),
    "requires": Field(item_type=str),
    "separators": Field(dict),
    "reserved": Field(frozenset),
    "forbidden_prefixes": Field(tuple),
    "requirement_line": Field(str),
}
"""Names an entry class body may assign, with their accepted value types."""

PACK_FIELDS: dict[str, Field] = {
    "target": Field(str),
    "entries": Field(tuple),
    "dispatch": Field(str),
    "session": Field(),
    "semantics": Field(str),
    "unhandled": Field(str),
    "runtime": Field(str),
    "runtime_schema": Field(),
}
"""Names a Target Pack class body may assign, with their accepted value types."""

ROLE_MARKERS = ("realizes", "naming")


def realizes(element: object) -> Callable[[C], C]:
    """Declare the class as the realization of one public Model element."""
    return marker("realizes", element)


def naming(subject: C) -> C:
    """Declare the class as the Target's naming policy."""
    return marker("naming", True)(subject)


def realization_target(element: object) -> tuple[str, type[Construct] | str] | None:
    """Resolve a public Model element to its existing lookup route.

    The current direct-Call Model knows only the builtin print name.  Its
    public element must be the exact published token, not a forged string.
    Other builtin operations use their already-defined Construct identities.
    """
    if isinstance(element, type) and issubclass(element, Construct):
        return ("construct", element)
    if element is PrintCall:
        return ("call", "print")
    if isinstance(element, ValueKind) and element is not ValueKind.MAPPED_OBJECT:
        return ("type", element.value)
    if isinstance(element, MappedType):
        return ("type", element.key)
    if isinstance(element, KindElement) and element in ELEMENTS:
        return ("type", element.key)
    return None


def _entry_validity(item: Declaration) -> Iterator[str]:
    roles = int(item.has_marker("realizes")) + int(item.has_marker("naming"))
    if roles != 1:
        yield "Entry must declare exactly one role"
        return
    target = (
        realization_target(item.marker("realizes"))
        if item.has_marker("realizes")
        else None
    )
    if item.has_marker("realizes") and target is None:
        yield "realizes requires a published Construct, builtin Call, or Model type element"
        return
    is_construct = target is not None and target[0] == "construct"
    is_call = target is not None and target[0] == "call"
    is_type = target is not None and target[0] == "type"
    if item.has("variant"):
        if not is_construct:
            yield "variant belongs to a Construct realization"
        else:
            assert target is not None
            kind = target[1]
            assert isinstance(kind, type) and issubclass(kind, Construct)
            declared = item.value("variant")
            domain = kind.variant_domain()
            if declared != "*" and domain is not None and declared not in domain:
                yield (
                    f"{kind.__name__}: invalid variant {declared!r}; "
                    f"expected one of {', '.join(sorted(domain))} or '*'"
                )
    chosen = cast(tuple[str, ...], item.values_of("template"))
    callback = item.values_of("render")
    visitor = item.values_of("visit")
    if item.has("separators"):
        settings = item.value("separators")
        if not isinstance(settings, dict) or any(
            not isinstance(name, str) or not isinstance(separator, str)
            for name, separator in settings.items()
        ):
            yield "separators needs a mapping of Slot names to strings"
        elif not is_construct or (chosen and set(settings) - holes_in(chosen[0])):
            yield "separators needs used Construct Slots"
        elif is_construct:
            assert target is not None
            kind = target[1]
            assert isinstance(kind, type) and issubclass(kind, Construct)
            if any(not kind.accepts_part_name(name) for name in settings):
                yield "separators names must be Model part Slots"
    if callback and not callable(callback[0]):
        yield "Renderer must be callable"
    if visitor and not callable(visitor[0]):
        yield "Visitor must be callable"
    if visitor and not (is_construct or is_call):
        yield "visit belongs to a realization entry"
    if item.has("supports"):
        obligations = item.value("supports")
        if (
            not isinstance(obligations, tuple)
            or not all(
                isinstance(key, str)
                and re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", key)
                for key in obligations
            )
            or len(obligations) != len(set(obligations))
        ):
            yield "supports must be unique namespaced contract identifiers"
        if not (is_construct or is_call):
            yield "supports belongs to a realization entry"
    if is_construct or is_call:
        if len(chosen) + len(callback) + len(visitor) != 1:
            yield "Realization needs exactly one template or renderer (or visitor)"
        if chosen:
            holes = holes_in(chosen[0])
            if is_construct:
                assert target is not None
                kind = target[1]
                assert isinstance(kind, type) and issubclass(kind, Construct)
                # Model part names describe possible instance structure. The
                # composer validates actual part presence when realizing a node.
                for hole in holes:
                    if kind.accepts_part_name(hole) or (
                        kind is Program and hole == "requirements"
                    ):
                        continue
                    yield f"{kind.__name__}: unknown template hole ${{{hole}}}"
            else:
                if item.has("accepts"):
                    maximum = len(cast(tuple[object, ...], item.value("accepts")))
                    permitted = {f"arg{i}" for i in range(maximum)}
                    invalid = holes - permitted
                else:
                    invalid = {h for h in holes if not re.fullmatch(r"arg[0-9]+", h)}
                for hole in invalid:
                    yield f"Invalid call hole ${{{hole}}}"
    elif is_type:
        value = item.values_of("type_name")
        if not value or not (isinstance(value[0], str) or callable(value[0])):
            yield "Type spelling requires string or callable"
    elif item.has_marker("naming") and item.has("requirement_line"):
        if holes_in(cast(str, item.value("requirement_line"))) - {"name"}:
            yield "Requirement line only accepts ${name}"


def _pack_validity(item: Declaration) -> Iterator[str]:
    if not item.has("target") or not item.value("target"):
        yield "Target Pack missing target"
    if item.has("dispatch") and item.value("dispatch") not in (
        "composition",
        "structural",
    ):
        yield "Invalid Target dispatch mode"
    semantics = item.value("semantics") if item.has("semantics") else "preservation"
    unhandled = item.value("unhandled") if item.has("unhandled") else "error"
    dispatch = item.value("dispatch") if item.has("dispatch") else "composition"
    if semantics not in ("preservation", "projection"):
        yield "Invalid Target semantics mode"
    if unhandled not in ("error", "traverse"):
        yield "Invalid unhandled Construct policy"
    if unhandled == "traverse" and (
        dispatch != "structural" or semantics != "projection"
    ):
        yield "Unhandled traverse needs structural dispatch and projection semantics"
    if item.has("runtime") and item.value("runtime") not in (
        "required",
        "forbidden",
        "optional",
        "ignored",
    ):
        yield "Invalid Target runtime policy"
    if (
        item.has("runtime")
        and item.value("runtime") in ("required", "optional")
        and not item.has("session")
    ):
        yield "Runtime-enabled Target needs an artifact session"
    if item.has("runtime_schema"):
        schema = item.value("runtime_schema")
        if not is_runtime_schema(schema):
            yield "Runtime schema must be a type or a callable validator"
        if (item.value("runtime") if item.has("runtime") else "ignored") not in (
            "required",
            "optional",
        ):
            yield "Runtime schema needs required or optional runtime policy"
    if item.has("session") and not callable(item.value("session")):
        yield "Artifact session factory must be callable"
    if (
        item.has("dispatch")
        and item.value("dispatch") == "structural"
        and not item.has("session")
    ):
        yield "Structural Target needs an artifact session"
    if not item.has("entries"):
        yield "Target Pack missing entries"
    elif not all(
        isinstance(entry, type)
        for entry in cast(tuple[object, ...], item.value("entries"))
    ):
        yield "Pack entries must be classes"


def read_entry(declaration: object) -> Declaration:
    """Read and validate one realization or naming entry class."""
    return require(
        declaration,
        _entry_validity,
        fields=ENTRY_FIELDS,
        markers=ROLE_MARKERS,
        label="Invalid target entry",
    )


def read_pack(pack: object) -> Declaration:
    """Read and validate one Target Pack class."""
    return require(
        pack, _pack_validity, fields=PACK_FIELDS, label="Invalid Target Pack"
    )
