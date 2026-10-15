"""Provider-declared typed primitives, independent of Target implementations.

Operation keys identify *families*. Definitions identify static signatures. A
small signature-local variable vocabulary permits structural matching without
runtime dispatch, a general type inference engine, or Target-specific rules.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, TypeAlias

from .base import Value
from .types import ConstructError, ListType, ValueKind, ValueType

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RECEIVER_KINDS = {
    ValueKind.INTEGER: "int",
    ValueKind.FLOAT: "float",
    ValueKind.STRING: "str",
    ValueKind.BOOLEAN: "bool",
    ValueKind.LIST: "list",
    ValueKind.DICT: "dict",
    ValueKind.TUPLE: "tuple",
    ValueKind.INSTANCE: "instance",
}
_CONTRACT = re.compile(r"intrinsic(?:\.[a-z][a-z0-9_]*){2,}")


@dataclass(frozen=True)
class IntrinsicTypeVar:
    """A named static placeholder scoped to one IntrinsicDefinition."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _IDENTIFIER.fullmatch(self.name):
            raise ConstructError("Intrinsic type variable requires an identifier")


@dataclass(frozen=True)
class IntrinsicListType:
    """A list-shaped signature pattern, e.g. ``list[T]``.

    This is *not* a new Model ValueType or a runtime generic type.
    """

    element_type: ValueType | IntrinsicTypeVar

    def __post_init__(self) -> None:
        if not isinstance(self.element_type, (ValueType, IntrinsicTypeVar)):
            raise ConstructError("Intrinsic list pattern requires a typed element")


IntrinsicSignatureType: TypeAlias = ValueType | IntrinsicTypeVar | IntrinsicListType


def _valid_shape(shape: object, *, argument: bool) -> bool:
    if not isinstance(shape, (ValueType, IntrinsicTypeVar, IntrinsicListType)):
        return False
    if isinstance(shape, ValueType) and argument:
        return shape.kind not in {ValueKind.NONE, ValueKind.MAPPED_OBJECT}
    if isinstance(shape, IntrinsicListType) and isinstance(
        shape.element_type, ValueType
    ):
        return shape.element_type.kind not in {ValueKind.NONE, ValueKind.MAPPED_OBJECT}
    return True


def _match(
    pattern: IntrinsicSignatureType,
    actual: ValueType,
    bindings: dict[str, ValueType],
) -> bool:
    """Unify only explicitly declared shapes and already-known value types."""
    if isinstance(pattern, ValueType):
        return pattern == actual
    if isinstance(pattern, IntrinsicTypeVar):
        bound = bindings.get(pattern.name)
        if bound is None:
            bindings[pattern.name] = actual
            return True
        return bound == actual
    return (
        actual.kind is ValueKind.LIST
        and actual.list_type is not None
        and _match(pattern.element_type, actual.list_type.element_type, bindings)
    )


def _substitute(
    pattern: IntrinsicSignatureType, bindings: Mapping[str, ValueType]
) -> ValueType | None:
    if isinstance(pattern, ValueType):
        return pattern
    if isinstance(pattern, IntrinsicTypeVar):
        return bindings.get(pattern.name)
    element = _substitute(pattern.element_type, bindings)
    return ValueType(ValueKind.LIST, list_type=ListType(element)) if element else None


def _variables(pattern: IntrinsicSignatureType) -> frozenset[str]:
    if isinstance(pattern, IntrinsicTypeVar):
        return frozenset({pattern.name})
    if isinstance(pattern, IntrinsicListType):
        return _variables(pattern.element_type)
    return frozenset()


@dataclass(frozen=True)
class IntrinsicDefinition:
    """One provider-owned signature with optional signature-local type variables.

    Multiple definitions may share a family key. Obligations remain specific
    to the selected signature, not merely to the operation's family.
    """

    name: str
    receiver_type: IntrinsicSignatureType | None
    argument_types: tuple[IntrinsicSignatureType, ...]
    return_type: IntrinsicSignatureType
    obligations: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _IDENTIFIER.fullmatch(self.name):
            raise ConstructError("Intrinsic name must be an identifier")
        if self.receiver_type is not None and (
            not _valid_shape(self.receiver_type, argument=True)
            or (
                isinstance(self.receiver_type, ValueType)
                and self.receiver_type.kind not in _RECEIVER_KINDS
            )
            or isinstance(self.receiver_type, IntrinsicTypeVar)
        ):
            raise ConstructError("Intrinsic receiver requires a supported typed shape")
        if not isinstance(self.argument_types, tuple) or any(
            not _valid_shape(t, argument=True) for t in self.argument_types
        ):
            raise ConstructError("Intrinsic arguments require explicit value types")
        if not _valid_shape(self.return_type, argument=False):
            raise ConstructError("Intrinsic return requires an explicit value type")
        if not isinstance(self.obligations, frozenset) or any(
            not isinstance(key, str) or _CONTRACT.fullmatch(key) is None
            for key in self.obligations
        ):
            raise ConstructError(
                "Intrinsic obligations require concrete intrinsic.* keys"
            )
        input_variables = frozenset().union(
            *(
                _variables(shape)
                for shape in (self.receiver_type, *self.argument_types)
                if shape is not None
            )
        )
        if not _variables(self.return_type) <= input_variables:
            raise ConstructError("Intrinsic return has unbound type variables")

    @property
    def key(self) -> str:
        if self.receiver_type is None:
            owner = "global"
        elif isinstance(self.receiver_type, IntrinsicListType):
            owner = "list"
        else:
            assert isinstance(self.receiver_type, ValueType)
            owner = _RECEIVER_KINDS[self.receiver_type.kind]
        return f"intrinsic.{owner}.{self.name}"

    def receiver_matches(self, actual: ValueType | None) -> bool:
        if (self.receiver_type is None) != (actual is None):
            return False
        if self.receiver_type is None or actual is None:
            return True
        return _match(self.receiver_type, actual, {})

    def expected_arguments(
        self, receiver: ValueType | None
    ) -> tuple[ValueType | None, ...]:
        """Known expectations for a single candidate, before reading arguments."""
        bindings: dict[str, ValueType] = {}
        if (
            self.receiver_type is not None
            and receiver is not None
            and not _match(self.receiver_type, receiver, bindings)
        ):
            return ()
        return tuple(_substitute(t, bindings) for t in self.argument_types)

    def resolve(
        self, receiver: ValueType | None, arguments: tuple[ValueType, ...]
    ) -> IntrinsicDefinition | None:
        """Resolve to a concrete signature; failure does not alter the catalog."""
        if len(arguments) != len(self.argument_types):
            return None
        if (self.receiver_type is None) != (receiver is None):
            return None
        bindings: dict[str, ValueType] = {}
        if (
            self.receiver_type is not None
            and receiver is not None
            and not _match(self.receiver_type, receiver, bindings)
        ):
            return None
        if not all(
            _match(pattern, actual, bindings)
            for pattern, actual in zip(self.argument_types, arguments)
        ):
            return None
        result = _substitute(self.return_type, bindings)
        concrete_args = tuple(_substitute(t, bindings) for t in self.argument_types)
        if result is None or any(arg is None for arg in concrete_args):
            return None
        if (
            isinstance(self.return_type, ValueType)
            and all(isinstance(t, ValueType) for t in self.argument_types)
            and (
                self.receiver_type is None or isinstance(self.receiver_type, ValueType)
            )
        ):
            return self
        return IntrinsicDefinition(
            self.name,
            _substitute(self.receiver_type, bindings)
            if self.receiver_type is not None
            else None,
            tuple(arg for arg in concrete_args if arg is not None),
            result,
            self.obligations,
        )


@dataclass(frozen=True)
class IntrinsicCall(Value):
    """A statically resolved call with concrete types and provider obligations."""

    definition: IntrinsicDefinition
    receiver: Value | None
    arguments: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver"})

    def __post_init__(self) -> None:
        if not isinstance(self.definition, IntrinsicDefinition):
            raise ConstructError("Intrinsic call needs a declared definition")
        if not isinstance(self.arguments, tuple) or not all(
            isinstance(arg, Value) for arg in self.arguments
        ):
            raise ConstructError("Intrinsic call requires typed argument Values")
        declared_receiver = self.definition.receiver_type
        if (declared_receiver is None) != (self.receiver is None):
            raise ConstructError("Intrinsic receiver presence does not match signature")
        if self.receiver is not None and not isinstance(self.receiver, Value):
            raise ConstructError("Intrinsic receiver must be a Value")
        if len(self.arguments) != len(self.definition.argument_types):
            raise ConstructError("Intrinsic argument arity mismatch")
        concrete = self.definition.resolve(
            self.receiver.value_type if self.receiver is not None else None,
            tuple(arg.value_type for arg in self.arguments),
        )
        if concrete is None:
            if self.receiver is not None and not self.definition.receiver_matches(
                self.receiver.value_type
            ):
                raise ConstructError("Intrinsic receiver type mismatch")
            raise ConstructError("Intrinsic argument type mismatch")
        # The Model holds the *resolved* static signature, not free variables.
        object.__setattr__(self, "definition", concrete)

    @property
    def value_type(self) -> ValueType:
        assert isinstance(self.definition.return_type, ValueType)
        return self.definition.return_type

    VARIANTS: ClassVar[frozenset[str] | None] = None

    def variant(self) -> str:
        return self.definition.key

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return name == "receiver" or (
            name.startswith("arg")
            and name[3:].isdecimal()
            and str(int(name[3:])) == name[3:]
        )

    def parts(self) -> Mapping[str, object]:
        parts: dict[str, object] = {}
        if self.receiver is not None:
            parts["receiver"] = self.receiver
        parts.update({f"arg{i}": arg for i, arg in enumerate(self.arguments)})
        return parts
