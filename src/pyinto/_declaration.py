"""Plain class-attribute declarations shared by Target Packs and Interface Mappings.

A declaration class is ordinary Python: values are written with ``=`` in the
class body and role markers are applied by decorators. Only the class's own
namespace (``vars(cls)``) is read. Unknown public names, wrong value types and
inherited declarations are rejected so that a misspelled or misplaced
declaration fails at registration instead of being silently ignored.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar

_MARKERS = "__pyinto_markers__"

C = TypeVar("C", bound=type)


@dataclass(frozen=True)
class Field:
    """One declarable class attribute and its accepted Python value type."""

    value_type: type | tuple[type, ...] = object
    item_type: type | None = None
    """When set, the value must be a tuple whose items are all this type."""

    def problem(self, name: str, value: object) -> str | None:
        if self.item_type is not None:
            if not isinstance(value, tuple) or not all(
                isinstance(item, self.item_type) for item in value
            ):
                return (
                    f"{name} must be a tuple of {self.item_type.__name__}, "
                    f"got {type(value).__name__}"
                )
            return None
        if not isinstance(value, self.value_type):
            return f"{name} must be {_type_label(self.value_type)}, got {type(value).__name__}"
        return None


def _type_label(value_type: type | tuple[type, ...]) -> str:
    if isinstance(value_type, tuple):
        return " or ".join(t.__name__ for t in value_type)
    return value_type.__name__


def marker(name: str, value: object) -> Callable[[C], C]:
    """Return a class decorator recording one role marker on that class only."""

    def apply(subject: C) -> C:
        if not isinstance(subject, type):
            raise TypeError(f"@{name} can only decorate a class")
        own = vars(subject).get(_MARKERS, ())
        setattr(subject, _MARKERS, (*own, (name, value)))
        return subject

    return apply


@dataclass(frozen=True)
class Declaration:
    """Read-only view of the markers and values declared directly on a class."""

    subject: type
    markers: Mapping[str, tuple[object, ...]]
    values: Mapping[str, object]
    nested: tuple[type, ...]

    def has(self, name: str) -> bool:
        return name in self.values

    def value(self, name: str) -> object:
        return self.values[name]

    def values_of(self, name: str) -> tuple[object, ...]:
        """Zero or one declared value, convenient for optional checks."""
        return (self.values[name],) if name in self.values else ()

    def has_marker(self, name: str) -> bool:
        return name in self.markers

    def marker(self, name: str) -> object:
        return self.markers[name][0]


def _is_declaration_namespace(namespace: Mapping[str, object]) -> bool:
    return _MARKERS in namespace


def read(
    subject: object,
    *,
    fields: Mapping[str, Field],
    markers: Iterable[str] = (),
    allow_nested: bool = False,
) -> tuple[Declaration | None, tuple[str, ...]]:
    """Collect a class's own declarations and the problems found while reading.

    Dunder and ``_private`` names are ordinary Python details and are ignored.
    Nested classes are collected only when ``allow_nested`` is true.
    """
    if not isinstance(subject, type):
        return None, ("declaration must be a class",)
    known_markers = frozenset(markers)
    problems: list[str] = []
    for base in subject.__mro__[1:]:
        if base is object:
            continue
        namespace = vars(base)
        if _is_declaration_namespace(namespace) or any(
            name in fields for name in namespace
        ):
            problems.append(
                f"declarations are not inherited; {subject.__name__} must not "
                f"derive from declaration class {base.__name__}"
            )
    recorded: dict[str, list[object]] = {}
    for name, value in vars(subject).get(_MARKERS, ()):
        recorded.setdefault(name, []).append(value)
    for name, found in recorded.items():
        if name not in known_markers:
            problems.append(f"@{name} is not valid here")
        elif len(found) > 1:
            problems.append(f"@{name} may be applied only once")
    values: dict[str, object] = {}
    nested: list[type] = []
    for name, value in vars(subject).items():
        if name.startswith("_"):
            continue
        if name in fields:
            problem = fields[name].problem(name, value)
            if problem is not None:
                problems.append(problem)
            values[name] = value
        elif allow_nested and isinstance(value, type):
            nested.append(value)
        else:
            expected = ", ".join(sorted(fields)) or "none"
            problems.append(
                f"unknown declaration {name!r} (expected one of: {expected}; "
                "use a leading underscore for helpers)"
            )
    declaration = Declaration(
        subject,
        MappingProxyType({k: tuple(v) for k, v in recorded.items()}),
        MappingProxyType(values),
        tuple(nested),
    )
    return declaration, tuple(problems)


def require(
    subject: object,
    validate: Callable[[Declaration], Iterator[str]],
    *,
    fields: Mapping[str, Field],
    markers: Iterable[str] = (),
    allow_nested: bool = False,
    label: str,
) -> Declaration:
    """Read and validate a declaration class, raising one ``ValueError``."""
    declaration, problems = read(
        subject, fields=fields, markers=markers, allow_nested=allow_nested
    )
    messages = list(problems)
    if declaration is not None and not problems:
        messages.extend(validate(declaration))
    if messages or declaration is None:
        name = getattr(subject, "__name__", repr(subject))
        raise ValueError(f"{label} {name}: " + "; ".join(messages))
    return declaration
