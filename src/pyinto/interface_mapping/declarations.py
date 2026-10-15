"""Class declarations for Python Source API -> Model function mappings.

A parent ``@maps(function)`` owns one or more nested ``@signature(...)``
classes; each signature declares its Model factory with ``factory = ...``.
Declarations are reduced to the existing immutable InterfaceFunctionMapping data,
so call binding, overload resolution and fail-closed behavior stay centralized.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import TypeVar, cast

from pyinto._declaration import Declaration, Field, marker, require
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


C = TypeVar("C", bound=type)

_PARENT_FIELDS: dict[str, Field] = {}
_SIGNATURE_FIELDS: dict[str, Field] = {"factory": Field()}
_MARKERS = ("maps", "signature")


def maps(function: object) -> Callable[[C], C]:
    """Declare the class as the mapping parent for one Python function."""
    return marker("maps", function)


def signature(
    *parameters: InterfaceParameter | ValueKind,
    variadic: InterfaceVariadicParameter | None = None,
) -> Callable[[C], C]:
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
    return marker("signature", entry)


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


def _validate_declaration(item: Declaration) -> Iterator[str]:
    parent = item.has_marker("maps")
    child = item.has_marker("signature")
    if parent == child:
        yield "Mapping entry must declare exactly one of maps or signature"
        return
    if parent:
        try:
            _source_name(item.marker("maps"))
        except (TypeError, ValueError) as exc:
            yield str(exc)
    elif not item.has("factory") or not callable(item.value("factory")):
        yield "signature requires a callable factory"


def _validated_item(declaration: type[object], *, parent: bool) -> Declaration:
    return require(
        declaration,
        _validate_declaration,
        fields=_PARENT_FIELDS if parent else _SIGNATURE_FIELDS,
        markers=_MARKERS,
        allow_nested=parent,
        label="Invalid interface mapping declaration",
    )


def function_declarations(parent: type[object]) -> tuple[InterfaceFunctionMapping, ...]:
    """Collect only *lexically nested* signatures from an explicit maps parent.

    We deliberately do not search globally, follow class aliases, or register
    decorators by side effect. A parent class alone is the unit of selection.
    """
    if not isinstance(parent, type):
        raise TypeError("Interface mapping declaration must be a class")
    outer = _validated_item(parent, parent=True)
    if not outer.has_marker("maps"):
        raise ValueError("Interface mapping parent requires @maps")
    source = _source_name(outer.marker("maps"))
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
        inner = _validated_item(child, parent=False)
        if not inner.has_marker("signature"):
            raise ValueError("Nested mapping class requires @signature")
        sig = cast(_Signature, inner.marker("signature"))
        definitions.append(
            InterfaceFunctionMapping(
                source,
                sig.positional_kinds,
                cast(Callable[[tuple[Value, ...]], Value], inner.value("factory")),
                parameters=sig.parameters,
                variadic=sig.variadic,
            )
        )
    return tuple(definitions)


def collect_function_declarations(
    parents: Iterable[type[object]],
) -> tuple[InterfaceFunctionMapping, ...]:
    return tuple(entry for parent in parents for entry in function_declarations(parent))
