"""Target-independent control definitions for the pyinto Construct Model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from .base import Construct, Value
from .type_rules import _binds, _compatible, assignable
from .types import (
    ConstructError,
    Identifier,
    ParameterRole,
    Symbol,
    ValueKind,
    ValueType,
)
from .values import Literal, Reference


@dataclass(frozen=True)
class Initialize(Construct):
    symbol: Symbol
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"type", "name", "value"})

    def __post_init__(self) -> None:
        if self.symbol.kind is None or not _binds(self.symbol, self.value):
            raise ConstructError("Initialization type mismatch")

    def parts(self) -> Mapping[str, object]:
        return {
            "type": self.symbol,
            "name": Identifier(self.symbol.name),
            "value": self.value,
        }


@dataclass(frozen=True)
class Assign(Construct):
    target: Reference
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"target", "value"})

    def __post_init__(self) -> None:
        if not _compatible(self.target.symbol, self.value):
            raise ConstructError("Assignment type mismatch")

    def parts(self) -> Mapping[str, object]:
        return {"target": self.target, "value": self.value}


@dataclass(frozen=True)
class UnpackAssign(Construct):
    """Atomic fixed-arity tuple unpacking into existing typed bindings.

    Evaluate the complete RHS once, retaining all positional values before
    writing *any* target. Then bind targets left to right, including repeated
    names. A Realization selects temporary storage, never this Model.
    """

    targets: tuple[Reference, ...]
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"targets", "value"})

    def __post_init__(self) -> None:
        if not isinstance(self.targets, tuple):
            raise ConstructError("Unpack assignment requires a tuple of targets")
        if not isinstance(self.value, Value) or self.value.kind is not ValueKind.TUPLE:
            raise ConstructError("Unpack assignment requires a typed tuple value")
        shape = self.value.tuple_type
        if shape is None or len(self.targets) != len(shape.element_types):
            raise ConstructError("Unpack assignment tuple arity mismatch")
        for target, item_type in zip(self.targets, shape.element_types, strict=True):
            if (
                not isinstance(target, Reference)
                or target.kind is ValueKind.MAPPED_OBJECT
            ):
                raise ConstructError("Unpack assignment requires ordinary References")
            if target.symbol.role in {
                # Parameters that act as method receivers cannot be rebound.
                ParameterRole.RECEIVER,
                ParameterRole.CLASS_RECEIVER,
            }:
                raise ConstructError("Method receiver cannot be rebound")
            if not assignable(target.value_type, item_type):
                raise ConstructError("Unpack assignment element type mismatch")

    def parts(self) -> Mapping[str, object]:
        return {"targets": self.targets, "value": self.value}


@dataclass(frozen=True)
class Call(Construct):
    callee: Symbol
    arguments: tuple[Value, ...]
    # Dynamically numbered argument slots are validated by the call regulation.

    def parts(self) -> Mapping[str, object]:
        return {f"arg{i}": arg for i, arg in enumerate(self.arguments)}


@dataclass(frozen=True)
class ExpressionStatement(Construct):
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"expression"})

    def parts(self) -> Mapping[str, object]:
        return {"expression": self.value}


@dataclass(frozen=True)
class Block(Construct):
    children: tuple[Construct, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"children"})

    def parts(self) -> Mapping[str, object]:
        return {"children": self.children}


@dataclass(frozen=True)
class Branch(Construct):
    condition: Value
    then_body: Block
    else_body: Block | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"condition", "then", "otherwise"})

    def __post_init__(self) -> None:
        if self.condition.kind is not ValueKind.BOOLEAN:
            raise ConstructError("Branch condition must be Boolean")

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"default", "with_else"})

    def variant(self) -> str:
        return "with_else" if self.else_body is not None else "default"

    def parts(self) -> Mapping[str, object]:
        result: dict[str, object] = {
            "condition": self.condition,
            "then": self.then_body,
        }
        if self.else_body is not None:
            result["otherwise"] = self.else_body
        return result


@dataclass(frozen=True)
class While(Construct):
    """A block entered repeatedly while its condition evaluates to true.

    The condition is a child Value, not a precomputed Boolean. The target
    binding decides how to position and re-evaluate it. ``else_body`` denotes
    the block entered on normal loop completion, without a ``break``.
    """

    condition: Value
    body: Block
    else_body: Block | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"condition", "body", "otherwise"})

    def __post_init__(self) -> None:
        if self.condition.kind is not ValueKind.BOOLEAN:
            raise ConstructError("While condition must be Boolean")

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"default", "with_else"})

    def variant(self) -> str:
        return "with_else" if self.else_body is not None else "default"

    def parts(self) -> Mapping[str, object]:
        result: dict[str, object] = {
            "condition": self.condition,
            "body": self.body,
        }
        if self.else_body is not None:
            result["otherwise"] = self.else_body
        return result


@dataclass(frozen=True)
class Pass(Construct):
    """An explicit statement with no runtime effect.

    This is structural, rather than an empty Block, so the original statement
    position remains available to a future Realization.
    """


@dataclass(frozen=True)
class Break(Construct):
    """Exit the innermost enclosing loop (not a target-language statement)."""


@dataclass(frozen=True)
class Continue(Construct):
    """Begin the next iteration of the innermost enclosing loop."""


@dataclass(frozen=True)
class Range(Value):
    """The structural form of Python's range(start, stop, step)."""

    arguments: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"arg0", "arg1", "arg2"})

    def __post_init__(self) -> None:
        if not 1 <= len(self.arguments) <= 3:
            raise ValueError("range requires one to three arguments")
        if any(arg.kind is not ValueKind.INTEGER for arg in self.arguments):
            raise ValueError("range arguments must be declared integers")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.ITERABLE

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"1", "2", "3"})

    def variant(self) -> str:
        return str(len(self.arguments))

    def parts(self) -> Mapping[str, object]:
        return {f"arg{i}": arg for i, arg in enumerate(self.arguments)}

    def bounds(self) -> tuple[Value, Value, Value]:
        if len(self.arguments) == 1:
            return Literal(0), self.arguments[0], Literal(1)
        if len(self.arguments) == 2:
            return self.arguments[0], self.arguments[1], Literal(1)
        return self.arguments[0], self.arguments[1], self.arguments[2]


def iteration_source_shape(source: Value) -> tuple[str, tuple[ValueType, ...] | None]:
    """Classify an iteration source without choosing a Target implementation.

    A tuple returns each positional element type (an empty tuple is valid).
    An unshaped Iterable has no statically known element type and stays a
    legal *Model* source, but cannot be admitted by the current Frontend.
    """
    if isinstance(source, Range):
        return "range", (ValueType(ValueKind.INTEGER),)
    if source.kind is ValueKind.STRING:
        return "string", (ValueType(ValueKind.STRING),)
    if source.kind is ValueKind.LIST and source.list_type is not None:
        return "list", (source.list_type.element_type,)
    if source.kind is ValueKind.TUPLE and source.tuple_type is not None:
        shape = source.tuple_type
        if shape.variadic_element_type is not None:
            return "tuple", (shape.variadic_element_type,)
        return "tuple", shape.element_types
    if source.kind is ValueKind.ITERABLE:
        return "iterable", None
    return "unsupported", None


@dataclass(frozen=True)
class IterationEntry(Construct):
    """Bind each element to one stable typed name, existing or introduced.

    ``introduces_binding`` records a declaration at the iteration entry, not
    an invented initialization value. The binding is updated on each iteration
    and may remain unbound when the source is empty. Target storage and the
    lifetime of a runtime cell are not specified here.
    """

    target: Reference
    iterable: Value
    introduces_binding: bool = False
    HOLES: ClassVar[frozenset[str]] = frozenset({"target", "iterable"})

    def __post_init__(self) -> None:
        if not isinstance(self.target, Reference) or not isinstance(
            self.iterable, Value
        ):
            raise ConstructError(
                "Iteration entry requires a Reference and iterable Value"
            )
        if type(self.introduces_binding) is not bool:
            raise ConstructError("Iteration binding introduction flag must be boolean")
        if self.introduces_binding:
            if self.target.symbol.role is not ParameterRole.ORDINARY:
                raise ConstructError("Introduced iteration binding must be ordinary")
            _, element_types = iteration_source_shape(self.iterable)
            if (
                not element_types
                or any(item != element_types[0] for item in element_types)
                or self.target.value_type != element_types[0]
            ):
                raise ConstructError(
                    "Introduced iteration binding requires one matching element type"
                )

    def parts(self) -> Mapping[str, object]:
        return {"target": self.target, "iterable": self.iterable}


@dataclass(frozen=True)
class For(Construct):
    """The iteration entry and the body/normal-completion Blocks.

    Target packs are free to expand the entry into many target statements.
    """

    entry: IterationEntry
    body: Block
    else_body: Block | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"entry", "body", "otherwise"})

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"default", "with_else"})

    def variant(self) -> str:
        return "with_else" if self.else_body is not None else "default"

    def parts(self) -> Mapping[str, object]:
        parts: dict[str, object] = {"entry": self.entry, "body": self.body}
        if self.else_body is not None:
            parts["otherwise"] = self.else_body
        return parts


@dataclass(frozen=True)
class ContextEntry(Construct):
    """Context expression and optional explicitly declared binding name."""

    context: Value
    target: Reference | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"context", "target"})

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"default", "with_target"})

    def variant(self) -> str:
        return "with_target" if self.target is not None else "default"

    def parts(self) -> Mapping[str, object]:
        parts: dict[str, object] = {"context": self.context}
        if self.target is not None:
            parts["target"] = self.target
        return parts


@dataclass(frozen=True)
class With(Construct):
    """Context entries and a Block; entering/exiting is a Binding responsibility."""

    entries: tuple[ContextEntry, ...]
    body: Block
    # Entries are Model parts even though their names depend on the instance.
    # Naming/separators in the emitted code remain Realization decisions.
    HOLES: ClassVar[frozenset[str]] = frozenset({"body"})

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return super().accepts_part_name(name) or (
            name.startswith("entry")
            and name[5:].isascii()
            and name[5:].isdecimal()
            and (name[5:] == "0" or not name[5:].startswith("0"))
        )

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("with requires at least one context entry")

    def parts(self) -> Mapping[str, object]:
        return {
            **{f"entry{i}": entry for i, entry in enumerate(self.entries)},
            "body": self.body,
        }


SUPPORTED_EXCEPTION_NAMES = frozenset({"ValueError", "TypeError", "RuntimeError"})


@dataclass(frozen=True)
class Raise(Construct):
    """Raise a supported built-in exception with an optional string message.

    Exception construction is a constrained source form, not an arbitrary
    function call or a Python exception object in the Model's Value domain.
    """

    exception_name: str
    message: Value | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"exception", "message"})

    def __post_init__(self) -> None:
        if self.exception_name not in SUPPORTED_EXCEPTION_NAMES:
            raise ConstructError("Unsupported exception class")
        if self.message is not None and (
            not isinstance(self.message, Value)
            or self.message.kind is not ValueKind.STRING
        ):
            raise ConstructError("Exception message requires a string Value")

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"default", "with_message"})

    def variant(self) -> str:
        return "with_message" if self.message is not None else "default"

    def parts(self) -> Mapping[str, object]:
        result: dict[str, object] = {"exception": Identifier(self.exception_name)}
        if self.message is not None:
            result["message"] = self.message
        return result


@dataclass(frozen=True)
class ExceptHandler(Construct):
    """Ordered set of explicitly named exception classes and a handler body."""

    exception_names: tuple[str, ...]
    body: Block
    HOLES: ClassVar[frozenset[str]] = frozenset({"types", "body"})

    def __post_init__(self) -> None:
        if (
            not self.exception_names
            or any(
                name not in SUPPORTED_EXCEPTION_NAMES for name in self.exception_names
            )
            or len(set(self.exception_names)) != len(self.exception_names)
        ):
            raise ConstructError("Handler needs distinct supported exception classes")
        if not isinstance(self.body, Block):
            raise ConstructError("Handler requires a Block")

    def parts(self) -> Mapping[str, object]:
        return {
            "types": tuple(Identifier(name) for name in self.exception_names),
            "body": self.body,
        }


@dataclass(frozen=True)
class Try(Construct):
    """Preserve try/except/else/finally control flow and source order.

    Handlers apply only to exceptions from the try body. Else runs only on
    ordinary fall-through; finally runs on all exits. A Realization unable to
    implement propagation and finally control-flow precedence must reject it.
    """

    body: Block
    handlers: tuple[ExceptHandler, ...] = ()
    else_body: Block | None = None
    finally_body: Block | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset(
        {"body", "handlers", "otherwise", "final"}
    )

    def __post_init__(self) -> None:
        if not isinstance(self.body, Block):
            raise ConstructError("Try requires a Block")
        if not self.handlers and self.finally_body is None:
            raise ConstructError("Try requires handlers or a finally body")
        if any(not isinstance(handler, ExceptHandler) for handler in self.handlers):
            raise ConstructError("Try requires ExceptHandler entries")
        if self.else_body is not None and (
            not self.handlers or not isinstance(self.else_body, Block)
        ):
            raise ConstructError("Try else requires handlers and a Block")
        if self.finally_body is not None and not isinstance(self.finally_body, Block):
            raise ConstructError("Try finally requires a Block")

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset(
        {"handlers", "finally", "handlers_finally"}
    )

    def variant(self) -> str:
        if self.handlers and self.finally_body is not None:
            return "handlers_finally"
        return "handlers" if self.handlers else "finally"

    def parts(self) -> Mapping[str, object]:
        result: dict[str, object] = {"body": self.body}
        if self.handlers:
            result["handlers"] = self.handlers
        if self.else_body is not None:
            result["otherwise"] = self.else_body
        if self.finally_body is not None:
            result["final"] = self.finally_body
        return result


@dataclass(frozen=True)
class Program(Construct):
    body: Block
    docstring: str | None = None
    # Target output requirements are not a Model child or a Model slot.
    HOLES: ClassVar[frozenset[str]] = frozenset({"body"})

    def __post_init__(self) -> None:
        if not isinstance(self.body, Block) or (
            self.docstring is not None and not isinstance(self.docstring, str)
        ):
            raise ConstructError("Program requires a Block and optional docstring")

    def parts(self) -> Mapping[str, object]:
        # The docstring is declaration metadata, not an emitted child Slot.
        return {"body": self.body}
