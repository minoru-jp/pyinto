"""Shikumi declarations for Python Source API -> Model function mappings.

A parent ``@maps(function)`` owns one or more nested ``@signature(...)``
classes; each signature declares its Model factory with ``factory @= ...``.
Declarations are reduced to the existing immutable InterfaceFunctionMapping data,
so call binding, overload resolution and fail-closed behavior stay centralized.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import cast

from shikumi import (
    Diagnostic,
    InformationType,
    SemanticView,
    Shikumi,
    StructuralKind,
    validator,
)
from shikumi.standard import assignment, decorator, information_type_rule

from pyinto.constructs import Value, ValueKind
from pyinto.interface_mapping.registry import (
    InterfaceFunctionMapping,
    InterfaceParameter,
    InterfaceVariadicParameter,
)


@dataclass(frozen=True)
class _Signature:
    parameters: tuple[InterfaceParameter, ...] | None
    positional_kinds: tuple[ValueKind, ...]
    variadic: InterfaceVariadicParameter | None


MAP_SOURCE = InformationType("interface.mapping.source", object)
SIGNATURE = InformationType("interface.mapping.signature", _Signature)
FACTORY = InformationType("interface.mapping.factory", object)

maps = decorator(MAP_SOURCE)
factory = assignment(FACTORY)


def signature(
    *parameters: InterfaceParameter | ValueKind,
    variadic: InterfaceVariadicParameter | None = None,
) -> Callable[[type[object]], type[object]]:
    """Declare a named or positional-only signature, with optional ``*args``.

    ``@signature(InterfaceParameter(...), ...)`` declares named parameters and
    defaults. ``@signature(ValueKind.INTEGER, ...)`` preserves explicit
    positional-only signatures without inventing parameter names. The two
    styles cannot be mixed within a signature.
    """
    if not parameters:
        entry = _Signature(None, (), variadic)
    elif all(isinstance(p, InterfaceParameter) for p in parameters):
        entry = _Signature(
            cast(tuple[InterfaceParameter, ...], parameters), (), variadic
        )
    elif all(isinstance(p, ValueKind) for p in parameters):
        entry = _Signature(None, cast(tuple[ValueKind, ...], parameters), variadic)
    else:
        raise TypeError("signature requires only InterfaceParameter or only ValueKind")
    return decorator(SIGNATURE)(entry)


def _source_name(source: object) -> str:
    """Identify the *defining* module-level function, never guess an export alias.

    Importing the Python library is the declaration author's explicit choice;
    the Frontend does not import or execute the mapped library while parsing.
    """
    if not (inspect.isfunction(source) or inspect.isbuiltin(source)):
        raise TypeError("maps requires a Python module-level function")
    module = getattr(source, "__module__", None)
    name = getattr(source, "__qualname__", None)
    if (
        not isinstance(module, str)
        or not isinstance(name, str)
        or not name.isidentifier()
        or "<locals>" in name
    ):
        raise ValueError(
            "maps requires a module-level function with an unambiguous name"
        )
    # Exact fully-qualified identity is checked again by the Registry.
    return f"{module}.{name}"


@validator(focus=StructuralKind.ENTITY, name="interface.mapping.declaration")
def _validate_declaration(view: SemanticView) -> Iterator[Diagnostic]:
    item = view.focused
    parent = item.has(MAP_SOURCE)
    child = item.has(SIGNATURE)
    if parent == child:
        yield Diagnostic(
            "Mapping entry must declare exactly one of maps or signature",
            code="interface.mapping.role",
        )
        return
    if parent:
        if item.has(FACTORY):
            yield Diagnostic(
                "maps parent cannot declare factory", code="interface.mapping.factory"
            )
        try:
            _source_name(item.values(MAP_SOURCE)[0])
        except (TypeError, ValueError) as exc:
            yield Diagnostic(str(exc), code="interface.mapping.source")
    else:
        if not item.has(FACTORY) or not callable(item.values(FACTORY)[0]):
            yield Diagnostic(
                "signature requires a callable factory",
                code="interface.mapping.factory",
            )


mapping_regulation = Shikumi(
    information_types=(MAP_SOURCE, SIGNATURE, FACTORY),
    validators=(
        information_type_rule(MAP_SOURCE),
        information_type_rule(SIGNATURE),
        information_type_rule(FACTORY),
        _validate_declaration,
    ),
)


def _validated_item(declaration: type[object]) -> SemanticView:
    result = mapping_regulation.validate(declaration)
    if not result.is_valid:
        raise ValueError(
            f"Invalid interface mapping declaration {declaration.__qualname__}: "
            + "; ".join(d.message for d in result.diagnostics)
        )
    return result.view


def function_declarations(parent: type[object]) -> tuple[InterfaceFunctionMapping, ...]:
    """Collect only *lexically nested* signatures from an explicit maps parent.

    We deliberately do not search globally, follow class aliases, or register
    decorators by side effect. A parent class alone is the unit of selection.
    """
    if not isinstance(parent, type):
        raise TypeError("Interface mapping declaration must be a class")
    outer = _validated_item(parent).focused
    if not outer.has(MAP_SOURCE):
        raise ValueError("Interface mapping parent requires @maps")
    source = _source_name(outer.values(MAP_SOURCE)[0])
    children: list[type[object]] = []
    prefix = parent.__qualname__ + "."
    for name, item in vars(parent).items():
        if not isinstance(item, type):
            continue
        # Don't silently accept unrelated imported class objects or aliases.
        if item.__module__ != parent.__module__ or item.__qualname__ != prefix + name:
            raise ValueError("Mapping signatures must be directly nested classes")
        children.append(item)
    if not children:
        raise ValueError("@maps requires at least one nested @signature class")
    definitions: list[InterfaceFunctionMapping] = []
    for child in children:
        inner = _validated_item(child).focused
        if not inner.has(SIGNATURE):
            raise ValueError("Nested mapping class requires @signature")
        sig = inner.values(SIGNATURE)[0]
        definitions.append(
            InterfaceFunctionMapping(
                source,
                sig.positional_kinds,
                cast(Callable[[tuple[Value, ...]], Value], inner.values(FACTORY)[0]),
                parameters=sig.parameters,
                variadic=sig.variadic,
            )
        )
    return tuple(definitions)


def collect_function_declarations(
    parents: Iterable[type[object]],
) -> tuple[InterfaceFunctionMapping, ...]:
    return tuple(entry for parent in parents for entry in function_declarations(parent))
