"""Shikumi contracts for composition and structural Target Pack entries."""

from __future__ import annotations

from collections.abc import Iterator

from shikumi import (
    Cardinality,
    Diagnostic,
    InformationType,
    SemanticView,
    Shikumi,
    StructuralKind,
    validator,
)
from shikumi.standard import assignment, decorator, information_type_rule

from pyinto.constructs import Construct, Program
from pyinto.constructs.types import PortType, ValueKind
from pyinto.interfaces.builtins import PrintCall
from pyinto.realizations.layout import holes_in
from pyinto.realizations.runtime import is_runtime_schema

# Realization target is a publicly exported Model element, not a string key.
REALIZES = InformationType("target.realizes", object)
NAMING = InformationType("target.naming", bool)
VARIANT = InformationType("target.variant", str)
TEMPLATE = InformationType("target.template", str)
RENDER = InformationType("target.render", object)
VISIT = InformationType("target.visit", object)
TYPE_NAME = InformationType("target.type_name", object)
ACCEPTS = InformationType("target.accepts", tuple)
SUPPORTS = InformationType("target.supports", tuple)
REQUIRES = InformationType("target.requires", str, Cardinality.MANY)
SEPARATORS = InformationType("target.separators", dict)
RESERVED = InformationType("target.reserved", frozenset)
FORBIDDEN_PREFIXES = InformationType("target.forbidden_prefixes", tuple)
REQUIREMENT_LINE = InformationType("target.requirement_line", str)
PACK_TARGET = InformationType("pack.target", str)
PACK_ENTRIES = InformationType("pack.entries", tuple)
PACK_DISPATCH = InformationType("pack.dispatch", str)
PACK_SESSION = InformationType("pack.session", object)
PACK_SEMANTICS = InformationType("pack.semantics", str)
PACK_UNHANDLED = InformationType("pack.unhandled", str)
PACK_RUNTIME = InformationType("pack.runtime", str)
PACK_RUNTIME_SCHEMA = InformationType("pack.runtime_schema", object)

realizes = decorator(REALIZES)
naming = decorator(NAMING)(True)
variant = assignment(VARIANT)
template = assignment(TEMPLATE)
render = assignment(RENDER)
visit = assignment(VISIT)
type_name = assignment(TYPE_NAME)
accepts = assignment(ACCEPTS)
supports = assignment(SUPPORTS)
requires = assignment(REQUIRES)
separators = assignment(SEPARATORS)
reserved = assignment(RESERVED)
forbidden_prefixes = assignment(FORBIDDEN_PREFIXES)
requirement_line = assignment(REQUIREMENT_LINE)
pack_target = assignment(PACK_TARGET)
pack_entries = assignment(PACK_ENTRIES)
pack_dispatch = assignment(PACK_DISPATCH)
pack_session = assignment(PACK_SESSION)
pack_semantics = assignment(PACK_SEMANTICS)
pack_unhandled = assignment(PACK_UNHANDLED)
pack_runtime = assignment(PACK_RUNTIME)
pack_runtime_schema = assignment(PACK_RUNTIME_SCHEMA)

ROLE_TYPES = (REALIZES, NAMING)
ENTRY_TYPES = (
    *ROLE_TYPES,
    VARIANT,
    TEMPLATE,
    RENDER,
    VISIT,
    TYPE_NAME,
    ACCEPTS,
    SUPPORTS,
    REQUIRES,
    SEPARATORS,
    RESERVED,
    FORBIDDEN_PREFIXES,
    REQUIREMENT_LINE,
)


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
    if isinstance(element, ValueKind) and element is not ValueKind.PORT_OBJECT:
        return ("type", element.value)
    if isinstance(element, PortType):
        return ("type", element.key)
    return None


@validator(focus=StructuralKind.ENTITY, name="target.entry_validity")
def _entry_validity(view: SemanticView) -> Iterator[Diagnostic]:
    item = view.focused
    roles = int(item.has(REALIZES)) + int(item.has(NAMING))
    if roles != 1:
        yield Diagnostic("Entry must declare exactly one role", code="target.role")
        return
    target = (
        realization_target(item.values(REALIZES)[0]) if item.has(REALIZES) else None
    )
    if item.has(REALIZES) and target is None:
        yield Diagnostic(
            "realizes requires a published Construct, builtin Call, or Model type element",
            code="target.realizes",
        )
        return
    is_construct = target is not None and target[0] == "construct"
    is_call = target is not None and target[0] == "call"
    is_type = target is not None and target[0] == "type"
    if item.has(VARIANT):
        if not is_construct:
            yield Diagnostic(
                "variant belongs to a Construct realization", code="target.variant"
            )
        else:
            assert target is not None
            kind = target[1]
            assert isinstance(kind, type) and issubclass(kind, Construct)
            declared = item.values(VARIANT)[0]
            domain = kind.variant_domain()
            if declared != "*" and domain is not None and declared not in domain:
                yield Diagnostic(
                    f"{kind.__name__}: invalid variant {declared!r}; "
                    f"expected one of {', '.join(sorted(domain))} or '*'",
                    code="target.variant",
                )
    chosen = item.values(TEMPLATE)
    callback = item.values(RENDER)
    visitor = item.values(VISIT)
    if item.has(SEPARATORS):
        settings = item.values(SEPARATORS)[0]
        if not isinstance(settings, dict) or any(
            not isinstance(name, str) or not isinstance(separator, str)
            for name, separator in settings.items()
        ):
            yield Diagnostic(
                "separators needs a mapping of Slot names to strings",
                code="target.separators",
            )
        elif not is_construct or (chosen and set(settings) - holes_in(chosen[0])):
            yield Diagnostic(
                "separators needs used Construct Slots",
                code="target.separators",
            )
        elif is_construct:
            assert target is not None
            kind = target[1]
            assert isinstance(kind, type) and issubclass(kind, Construct)
            if any(not kind.accepts_part_name(name) for name in settings):
                yield Diagnostic(
                    "separators names must be Model part Slots",
                    code="target.separators",
                )
    if callback and not callable(callback[0]):
        yield Diagnostic("Renderer must be callable", code="target.render")
    if visitor and not callable(visitor[0]):
        yield Diagnostic("Visitor must be callable", code="target.visit")
    if visitor and not (is_construct or is_call):
        yield Diagnostic("visit belongs to a realization entry", code="target.visit")
    if item.has(SUPPORTS):
        import re

        obligations = item.values(SUPPORTS)[0]
        if (
            not isinstance(obligations, tuple)
            or not all(
                isinstance(key, str)
                and re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", key)
                for key in obligations
            )
            or len(obligations) != len(set(obligations))
        ):
            yield Diagnostic(
                "supports must be unique namespaced contract identifiers",
                code="target.supports",
            )
        if not (is_construct or is_call):
            yield Diagnostic(
                "supports belongs to a realization entry",
                code="target.supports",
            )
    if is_construct or is_call:
        if len(chosen) + len(callback) + len(visitor) != 1:
            yield Diagnostic(
                "Realization needs exactly one template or renderer (or visitor)",
                code="target.layout",
            )
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
                    yield Diagnostic(
                        f"{kind.__name__}: unknown template hole ${{{hole}}}",
                        code="target.hole",
                    )
            else:
                if item.has(ACCEPTS):
                    maximum = len(item.values(ACCEPTS)[0])
                    permitted = {f"arg{i}" for i in range(maximum)}
                    invalid = holes - permitted
                else:
                    import re

                    invalid = {h for h in holes if not re.fullmatch(r"arg[0-9]+", h)}
                for hole in invalid:
                    yield Diagnostic(
                        f"Invalid call hole ${{{hole}}}", code="target.hole"
                    )
    elif is_type:
        value = item.values(TYPE_NAME)
        if not value or not (isinstance(value[0], str) or callable(value[0])):
            yield Diagnostic(
                "Type spelling requires string or callable", code="target.type"
            )
    elif item.has(NAMING) and item.has(REQUIREMENT_LINE):
        if holes_in(item.values(REQUIREMENT_LINE)[0]) - {"name"}:
            yield Diagnostic(
                "Requirement line only accepts ${name}", code="target.hole"
            )


entry_regulation = Shikumi(
    information_types=ENTRY_TYPES,
    validators=(*tuple(information_type_rule(t) for t in ENTRY_TYPES), _entry_validity),
)


@validator(focus=StructuralKind.ENTITY, name="target.pack_validity")
def _pack_validity(view: SemanticView) -> Iterator[Diagnostic]:
    item = view.focused
    if not item.has(PACK_TARGET) or not item.values(PACK_TARGET)[0]:
        yield Diagnostic("Target Pack missing target", code="pack.target")
    if item.has(PACK_DISPATCH) and item.values(PACK_DISPATCH)[0] not in (
        "composition",
        "structural",
    ):
        yield Diagnostic("Invalid Target dispatch mode", code="pack.dispatch")
    semantics = (
        item.values(PACK_SEMANTICS)[0] if item.has(PACK_SEMANTICS) else "preservation"
    )
    unhandled = item.values(PACK_UNHANDLED)[0] if item.has(PACK_UNHANDLED) else "error"
    dispatch = (
        item.values(PACK_DISPATCH)[0] if item.has(PACK_DISPATCH) else "composition"
    )
    if semantics not in ("preservation", "projection"):
        yield Diagnostic("Invalid Target semantics mode", code="pack.semantics")
    if unhandled not in ("error", "traverse"):
        yield Diagnostic("Invalid unhandled Construct policy", code="pack.unhandled")
    if unhandled == "traverse" and (
        dispatch != "structural" or semantics != "projection"
    ):
        yield Diagnostic(
            "Unhandled traverse needs structural dispatch and projection semantics",
            code="pack.unhandled",
        )
    if item.has(PACK_RUNTIME) and item.values(PACK_RUNTIME)[0] not in (
        "required",
        "forbidden",
        "optional",
        "ignored",
    ):
        yield Diagnostic("Invalid Target runtime policy", code="pack.runtime")
    if (
        item.has(PACK_RUNTIME)
        and item.values(PACK_RUNTIME)[0] in ("required", "optional")
        and not item.has(PACK_SESSION)
    ):
        yield Diagnostic(
            "Runtime-enabled Target needs an artifact session", code="pack.session"
        )
    if item.has(PACK_RUNTIME_SCHEMA):
        schema = item.values(PACK_RUNTIME_SCHEMA)[0]
        if not is_runtime_schema(schema):
            yield Diagnostic(
                "Runtime schema must be a type or a callable validator",
                code="pack.runtime_schema",
            )
        if (
            item.values(PACK_RUNTIME)[0] if item.has(PACK_RUNTIME) else "ignored"
        ) not in ("required", "optional"):
            yield Diagnostic(
                "Runtime schema needs required or optional runtime policy",
                code="pack.runtime_schema",
            )
    if item.has(PACK_SESSION) and not callable(item.values(PACK_SESSION)[0]):
        yield Diagnostic(
            "Artifact session factory must be callable", code="pack.session"
        )
    if (
        item.has(PACK_DISPATCH)
        and item.values(PACK_DISPATCH)[0] == "structural"
        and not item.has(PACK_SESSION)
    ):
        yield Diagnostic(
            "Structural Target needs an artifact session", code="pack.session"
        )
    if not item.has(PACK_ENTRIES):
        yield Diagnostic("Target Pack missing entries", code="pack.entries")
    elif not all(isinstance(entry, type) for entry in item.values(PACK_ENTRIES)[0]):
        yield Diagnostic("Pack entries must be classes", code="pack.entries")


pack_regulation = Shikumi(
    information_types=(
        PACK_TARGET,
        PACK_ENTRIES,
        PACK_DISPATCH,
        PACK_SESSION,
        PACK_SEMANTICS,
        PACK_UNHANDLED,
        PACK_RUNTIME,
        PACK_RUNTIME_SCHEMA,
    ),
    validators=(
        information_type_rule(PACK_TARGET),
        information_type_rule(PACK_ENTRIES),
        information_type_rule(PACK_DISPATCH),
        information_type_rule(PACK_SESSION),
        information_type_rule(PACK_SEMANTICS),
        information_type_rule(PACK_UNHANDLED),
        information_type_rule(PACK_RUNTIME),
        information_type_rule(PACK_RUNTIME_SCHEMA),
        _pack_validity,
    ),
)
