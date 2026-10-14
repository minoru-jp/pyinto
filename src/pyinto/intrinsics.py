"""Provider-owned static catalog of primitive operation families and signatures.

No Target recipe is selected here. Every signature is checked using explicit
known types, without coercion, dynamic dispatch, or overload ranking.
"""

from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType

from pyinto.constructs.intrinsic import IntrinsicDefinition
from pyinto.constructs.types import ConstructError, ValueType


class IntrinsicRegistry:
    """Immutable operation-family catalog with deterministic static matching."""

    def __init__(self, definitions: Iterable[IntrinsicDefinition] = ()) -> None:
        families: dict[str, list[IntrinsicDefinition]] = {}
        for definition in definitions:
            if not isinstance(definition, IntrinsicDefinition):
                raise TypeError(
                    "Intrinsic registry requires IntrinsicDefinition entries"
                )
            if definition.receiver_type is None and definition.name in {
                "range",
                "super",
            }:
                raise ValueError("Intrinsic cannot replace special syntax: range/super")
            family = families.setdefault(definition.key, [])
            if any(
                current.receiver_type == definition.receiver_type
                and current.argument_types == definition.argument_types
                for current in family
            ):
                raise ValueError(f"Duplicate intrinsic signature: {definition.key}")
            family.append(definition)
        self._families = MappingProxyType(
            {key: tuple(items) for key, items in families.items()}
        )

    @property
    def definitions(self) -> tuple[IntrinsicDefinition, ...]:
        return tuple(d for family in self._families.values() for d in family)

    def global_candidates(self, name: str) -> tuple[IntrinsicDefinition, ...]:
        return self._families.get(f"intrinsic.global.{name}", ())

    def method_candidates(
        self, name: str, receiver_type: ValueType
    ) -> tuple[IntrinsicDefinition, ...]:
        return tuple(
            candidate
            for family in self._families.values()
            for candidate in family
            if candidate.name == name
            and candidate.receiver_type is not None
            and candidate.receiver_matches(receiver_type)
        )

    def global_call(self, name: str) -> IntrinsicDefinition | None:
        """Convenience for callers expecting a uniquely registered definition."""
        candidates = self.global_candidates(name)
        return candidates[0] if len(candidates) == 1 else None

    def has_global_name(self, name: str) -> bool:
        return bool(self.global_candidates(name))

    def method(self, name: str, receiver_type: ValueType) -> IntrinsicDefinition | None:
        candidates = self.method_candidates(name, receiver_type)
        return candidates[0] if len(candidates) == 1 else None

    def has_method_name(self, name: str) -> bool:
        return any(
            definition.name == name and definition.receiver_type is not None
            for definition in self.definitions
        )

    @staticmethod
    def select(
        candidates: Iterable[IntrinsicDefinition],
        receiver_type: ValueType | None,
        argument_types: tuple[ValueType, ...],
    ) -> IntrinsicDefinition | None:
        matches = tuple(
            concrete
            for candidate in candidates
            if (concrete := candidate.resolve(receiver_type, argument_types))
            is not None
        )
        if len(matches) > 1:
            raise ConstructError("Ambiguous intrinsic signatures")
        return matches[0] if matches else None

    def extend(self, definitions: Iterable[IntrinsicDefinition]) -> IntrinsicRegistry:
        """Make a new immutable catalog; never replace an exact signature."""
        try:
            return IntrinsicRegistry((*self.definitions, *tuple(definitions)))
        except ValueError as exc:
            raise ConstructError(str(exc)) from exc


def standard_intrinsics() -> IntrinsicRegistry:
    """Provider-owned, Target-neutral catalog of adopted Python primitives.

    This is a table of *signatures and contracts*, not Python implementations.
    Explicit ``PythonFrontend(intrinsics=...)`` catalogs replace this default;
    callers may use ``standard_intrinsics().extend(...)`` to add operations.
    """
    from pyinto.constructs.types import ValueKind

    boolean = ValueType(ValueKind.BOOLEAN)
    integer = ValueType(ValueKind.INTEGER)
    floating = ValueType(ValueKind.FLOAT)
    string = ValueType(ValueKind.STRING)

    def global_op(
        name: str,
        inputs: tuple[ValueType, ...],
        output: ValueType,
        contract: str,
    ) -> IntrinsicDefinition:
        return IntrinsicDefinition(name, None, inputs, output, frozenset({contract}))

    def string_method(name: str, contract: str) -> IntrinsicDefinition:
        return IntrinsicDefinition(name, string, (), string, frozenset({contract}))

    return IntrinsicRegistry(
        (
            global_op("str", (), string, "intrinsic.stringify.empty"),
            global_op("str", (string,), string, "intrinsic.stringify.identity"),
            global_op("str", (integer,), string, "intrinsic.stringify.int_repr"),
            global_op("str", (floating,), string, "intrinsic.stringify.float_repr"),
            global_op("str", (boolean,), string, "intrinsic.stringify.bool_repr"),
            global_op("int", (), integer, "intrinsic.convert.int.default_zero"),
            global_op("int", (integer,), integer, "intrinsic.convert.int.identity"),
            global_op("int", (boolean,), integer, "intrinsic.convert.int.from_bool"),
            global_op("int", (floating,), integer, "intrinsic.convert.int.from_float"),
            global_op("int", (string,), integer, "intrinsic.convert.int.from_str"),
            global_op("float", (), floating, "intrinsic.convert.float.default_zero"),
            global_op(
                "float", (floating,), floating, "intrinsic.convert.float.identity"
            ),
            global_op(
                "float", (boolean,), floating, "intrinsic.convert.float.from_bool"
            ),
            global_op(
                "float", (integer,), floating, "intrinsic.convert.float.from_int"
            ),
            global_op("float", (string,), floating, "intrinsic.convert.float.from_str"),
            string_method("upper", "intrinsic.string.upper_unicode"),
            string_method("lower", "intrinsic.string.lower_unicode"),
        )
    )
