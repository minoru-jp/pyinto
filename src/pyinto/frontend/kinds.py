"""Static recognition of the ``pyinto.kinds`` vocabulary.

Words are recognized by their import spelling only. Each type word is given a
Python-side shape (what the value is when the source runs as Python) and a
kind label that the Host carries to Targets without interpreting it.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import replace

from pyinto.constructs import (
    CallableType,
    KindLabel,
    ListType,
    ValueKind,
    ValueType,
)
from pyinto.constructs.types import CLASS_LABELS, NONE_ALIASES

from .errors import UnsupportedPython, reject

PACKAGE = "pyinto.kinds"

# Each importable module and the words it provides.
MODULES: dict[str, frozenset[str]] = {
    "pyinto.kinds.datatypes.general": frozenset(
        {"Wide", "Narrow", "Unsigned", "Size", "Index", "Byte"}
    ),
    "pyinto.kinds.datatypes.detailed": frozenset(
        {
            "Int",
            "UInt",
            "Float",
            "Decimal",
            "CodeUnit",
            "Array",
            "Enum",
            "Function",
            "Char",
            "Void",
            "Nil",
            "Null",
        }
    ),
    "pyinto.kinds.memory.general": frozenset({"Owned", "Shared", "Buffer", "Memory"}),
    "pyinto.kinds.memory.detailed": frozenset({"Pointer", "Ref"}),
    "pyinto.kinds.declarations.detailed": frozenset(
        {"Interface", "MixIn", "Implements"}
    ),
}


def module_of(word: str) -> str | None:
    return next((module for module, words in MODULES.items() if word in words), None)


# Words written with one positive size argument, and their Python-side kind.
SIZED: dict[str, ValueKind] = {
    "Int": ValueKind.INTEGER,
    "UInt": ValueKind.INTEGER,
    "Float": ValueKind.FLOAT,
    "Decimal": ValueKind.FLOAT,
    "CodeUnit": ValueKind.INTEGER,
}
# Words written without arguments.
PLAIN: dict[str, ValueKind] = {
    "Byte": ValueKind.INTEGER,
    "Size": ValueKind.INTEGER,
    "Index": ValueKind.INTEGER,
    "Char": ValueKind.STRING,
}
# General refinements of int / float (Unsigned: integers only).
REFINING: frozenset[str] = frozenset({"Wide", "Narrow", "Unsigned"})
# Words written with one type argument.
TYPED: dict[str, ValueKind] = {
    "Pointer": ValueKind.INTEGER,
    "Enum": ValueKind.INTEGER,
}
# Words that keep the shape of their one type argument and add a label.
WRAPPING: frozenset[str] = frozenset({"Ref", "Owned", "Shared"})
TYPE_WORDS: frozenset[str] = frozenset(
    {
        *SIZED,
        *PLAIN,
        *TYPED,
        *WRAPPING,
        *REFINING,
        "Array",
        "Buffer",
        "Function",
        *NONE_ALIASES,
    }
)
VOCABULARY: frozenset[str] = frozenset().union(*MODULES.values())
assert TYPE_WORDS | CLASS_LABELS | {"Memory"} == VOCABULARY

# Memory.<operation>: positional argument count, and whether it is a statement.
MEMORY_OPERATIONS: dict[str, tuple[int, bool]] = {
    "new": (2, False),
    "new_buffer": (3, False),
    "length": (1, False),
    "borrow": (1, False),
    "release": (1, True),
    "resize": (2, True),
    "copy": (2, True),
    "fill": (2, True),
}


def pointer_operation(node: ast.expr, aliases: dict[str, str]) -> str | None:
    """``address`` / ``load`` / ``store`` for a ``Pointer.<op>(...)`` call."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and aliases.get(node.func.value.id) == "Pointer"
    ):
        operation = node.func.attr
        if operation not in {"address", "load", "store"}:
            raise reject(node, f"Unknown Pointer operation: {operation!r}")
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            raise reject(node, f"Pointer.{operation} takes positional arguments only")
        expected = 2 if operation == "store" else 1
        if len(node.args) != expected:
            raise reject(node, f"Pointer.{operation} requires {expected} argument(s)")
        return operation
    return None


def memory_operation(node: ast.expr, aliases: dict[str, str]) -> str | None:
    """The operation name for a ``Memory.<op>(...)`` call, after shape checks."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and aliases.get(node.func.value.id) == "Memory"
    ):
        operation = node.func.attr
        if operation not in MEMORY_OPERATIONS:
            raise reject(node, f"Unknown Memory operation: {operation!r}")
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            raise reject(node, f"Memory.{operation} takes positional arguments only")
        expected, _ = MEMORY_OPERATIONS[operation]
        if len(node.args) != expected:
            raise reject(node, f"Memory.{operation} requires {expected} argument(s)")
        return operation
    return None


def _size(node: ast.expr) -> int:
    if (
        not isinstance(node, ast.Constant)
        or type(node.value) is not int
        or node.value <= 0
    ):
        raise reject(node, "Kind size must be a positive integer literal")
    return node.value


def _refine(word: str, node: ast.expr, target: ValueType) -> ValueType:
    """``Wide`` / ``Narrow`` / ``Unsigned`` over ``int`` / ``float``.

    One spelling per meaning: ``Unsigned`` is outermost and Wide/Narrow are
    not mixed. The Host never interprets the resulting steps.
    """
    inner = target.label
    if word == "Unsigned":
        if target.kind is not ValueKind.INTEGER:
            raise reject(node, "Unsigned applies only to integers")
        if inner is not None and inner.name not in {"Wide", "Narrow"}:
            raise reject(node, "Unsigned applies only to int, Wide[...] or Narrow[...]")
    else:
        if target.kind not in {ValueKind.INTEGER, ValueKind.FLOAT}:
            raise reject(node, f"{word} applies only to int or float")
        if inner is not None and inner.name == "Unsigned":
            raise reject(node, "Unsigned must be the outermost word")
        if inner is not None and inner.name != word:
            raise reject(
                node,
                f"{word} applies only to int, float or {word}[...]"
                if inner.name not in {"Wide", "Narrow"}
                else "Wide and Narrow cannot be mixed",
            )
    return replace(target, label=KindLabel(word, (target,)))


def plain_annotation(word: str, node: ast.expr) -> ValueType:
    """A word written without arguments (``Byte``, ``Char``, ``Void`` ...)."""
    if word in PLAIN:
        return ValueType(PLAIN[word], label=KindLabel(word))
    if word in NONE_ALIASES:
        return ValueType(ValueKind.NONE, label=KindLabel(word))
    if word in CLASS_LABELS:
        raise reject(node, f"{word} is a class decorator, not a type")
    if word == "Memory":
        raise reject(node, "Memory is an operation vocabulary, not a type")
    raise reject(node, f"Kind {word} requires arguments")


def generic_annotation(
    word: str, node: ast.Subscript, typed: Callable[[ast.expr], ValueType]
) -> ValueType:
    """A word written with arguments (``Int[32]``, ``Pointer[T]`` ...)."""
    arguments = (
        list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
    )
    try:
        if word in REFINING:
            if len(arguments) != 1:
                raise reject(node, f"{word} requires exactly one type")
            return _refine(word, node, typed(arguments[0]))
        if word in SIZED:
            if len(arguments) != 1:
                raise reject(node, f"{word} requires exactly one size")
            size = _size(arguments[0])
            return ValueType(SIZED[word], label=KindLabel(word, (size,)))
        if word in TYPED or word in WRAPPING:
            if len(arguments) != 1:
                raise reject(node, f"{word} requires exactly one type")
            target = typed(arguments[0])
            label = KindLabel(word, (target,))
            if word in WRAPPING:
                # Ref / Owned / Shared keep their target's Python-side shape.
                return replace(target, label=label)
            return ValueType(TYPED[word], label=label)
        if word == "Buffer":
            if len(arguments) != 1:
                raise reject(node, "Buffer requires exactly one element type")
            element = typed(arguments[0])
            if element.kind is ValueKind.NONE:
                raise reject(node, "Unsupported Buffer element type")
            return ValueType(
                ValueKind.LIST,
                list_type=ListType(element),
                label=KindLabel("Buffer", (element,)),
            )
        if word == "Array":
            if len(arguments) != 2:
                raise reject(node, "Array requires an element type and a length")
            element = typed(arguments[0])
            if element.kind is ValueKind.NONE:
                raise reject(node, "Unsupported Array element type")
            length = _size(arguments[1])
            return ValueType(
                ValueKind.LIST,
                list_type=ListType(element),
                label=KindLabel("Array", (element, length)),
            )
        if word == "Function":
            if not (len(arguments) == 2 and isinstance(arguments[0], ast.List)):
                raise reject(
                    node, "Function requires an explicit parameter list and result"
                )
            parameters = tuple(typed(item) for item in arguments[0].elts)
            if any(item.kind is ValueKind.NONE for item in parameters):
                raise reject(node, "Unsupported Function parameter type")
            shape = CallableType(parameters, typed(arguments[1]))
            return ValueType(
                ValueKind.FUNCTION,
                callable_type=shape,
                label=KindLabel("Function"),
            )
    except UnsupportedPython:
        raise
    except ValueError as exc:
        raise reject(node, str(exc)) from exc
    raise reject(node, f"Kind {word} takes no arguments")
