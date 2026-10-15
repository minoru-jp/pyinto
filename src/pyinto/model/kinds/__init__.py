"""Kind elements and helpers for Target authors.

The tree mirrors ``pyinto.kinds``: each type word has a ``KindElement`` that a
Target uses as an ``@realizes`` subject to register its type spelling::

    from pyinto.model.kinds.datatypes import general as dg

    @realizes(dg.Wide)
    class CWide:
        type_name = lambda shape, spell: ...

The spelling receives the complete ``ValueType``; ``shape.label`` holds the
word and its arguments as a ``KindLabel``. Source-side words cannot serve as
subjects because ``Void`` / ``Nil`` / ``Null`` are ``None``. ``Memory``,
``Pointer`` operations and declaration words are realized through their
Constructs (``lang.MemoryNew``, ``lang.AddressOf``, ``ClassDefinition.labels``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyinto.constructs.types import KindLabel, ValueKind, ValueType
from pyinto.model.kinds._elements import KindElement
from pyinto.model.kinds.datatypes import detailed as _datatypes_detailed
from pyinto.model.kinds.datatypes import general as _datatypes_general
from pyinto.model.kinds.memory import detailed as _memory_detailed
from pyinto.model.kinds.memory import general as _memory_general

if TYPE_CHECKING:
    from pyinto.realizations.registry import RealizationRegistry

__all__ = [
    "ELEMENTS",
    "GENERAL_ELEMENTS",
    "KindElement",
    "KindLabel",
    "NumericProfile",
    "missing_general",
    "profile",
]


def _elements(*modules: object) -> frozenset[KindElement]:
    return frozenset(
        value
        for module in modules
        for value in vars(module).values()
        if isinstance(value, KindElement)
    )


GENERAL_ELEMENTS: frozenset[KindElement] = _elements(
    _datatypes_general, _memory_general
)
ELEMENTS: frozenset[KindElement] = GENERAL_ELEMENTS | _elements(
    _datatypes_detailed, _memory_detailed
)


@dataclass(frozen=True)
class NumericProfile:
    """``int`` / ``float`` refined by the general Wide/Narrow/Unsigned words.

    ``rank`` counts Wide steps as positive and Narrow steps as negative.
    """

    base: ValueKind
    rank: int
    unsigned: bool


def profile(value_type: ValueType) -> NumericProfile | None:
    """Read ``Unsigned[Wide[Wide[int]]]`` as ``(INTEGER, +2, unsigned)``.

    Plain ``int`` / ``float`` give rank 0. Any other label returns None.
    """
    unsigned = False
    rank = 0
    current = value_type
    label = current.label
    if label is not None and label.name == "Unsigned":
        unsigned = True
        current = _argument(label)
        label = current.label
    while label is not None and label.name in {"Wide", "Narrow"}:
        rank += 1 if label.name == "Wide" else -1
        current = _argument(label)
        label = current.label
    if label is not None or current.kind not in {ValueKind.INTEGER, ValueKind.FLOAT}:
        return None
    return NumericProfile(current.kind, rank, unsigned)


def _argument(label: KindLabel) -> ValueType:
    target = label.arguments[0]
    assert isinstance(target, ValueType)
    return target


# Python's built-in types are the base general vocabulary, spelled through
# their Model value kinds.
_GENERAL_BASES: tuple[tuple[str, ValueKind], ...] = (
    ("int", ValueKind.INTEGER),
    ("float", ValueKind.FLOAT),
    ("str", ValueKind.STRING),
    ("bool", ValueKind.BOOLEAN),
    ("None", ValueKind.NONE),
    ("list", ValueKind.LIST),
    ("dict", ValueKind.DICT),
    ("tuple", ValueKind.TUPLE),
    ("Callable", ValueKind.FUNCTION),
    ("class", ValueKind.INSTANCE),
)
_GENERAL_CONSTRUCTS: tuple[str, ...] = (
    "MemoryNew",
    "MemoryNewBuffer",
    "MemoryRelease",
    "MemoryResize",
    "MemoryLength",
    "MemoryBorrow",
    "MemoryCopy",
    "MemoryFill",
)


def missing_general(registry: RealizationRegistry) -> tuple[str, ...]:
    """General vocabulary a Target's registry does not realize, in a fixed order.

    A Target that claims the general vocabulary checks this is empty in its
    tests. Registration does not require it: projection Targets need not
    spell types at all.
    """
    import pyinto.constructs as model

    missing = [
        name for name, kind in _GENERAL_BASES if not registry.covers_type(kind.value)
    ]
    missing += sorted(
        element.name
        for element in GENERAL_ELEMENTS
        if not registry.covers_type(element.key)
    )
    missing += [
        name
        for name in _GENERAL_CONSTRUCTS
        if not registry.covers_construct(getattr(model, name))
    ]
    return tuple(missing)
