"""Target-independent classes definitions for the pyinto Construct Model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from .base import Construct, Value
from .functions import (
    FunctionDefinition,
    FunctionSignature,
    _call_evaluation_order,
    _validate_omitted_defaults,
)
from .type_rules import _compatible, _value_type_compatible
from .types import (
    ConstructError,
    Identifier,
    InstanceType,
    MethodKind,
    ParameterRole,
    ValueKind,
    ValueType,
)
from .values import Reference


@dataclass(frozen=True)
class FieldDefinition(Construct):
    """A declared, typed instance field, independent of object storage layout."""

    name: str
    type: ValueType
    HOLES: ClassVar[frozenset[str]] = frozenset({"name", "type"})

    def __post_init__(self) -> None:
        if not self.name.isidentifier() or not isinstance(self.type, ValueType):
            raise ConstructError("Field requires a name and a value type")
        if self.type.kind is ValueKind.NONE:
            raise ConstructError("Instance field cannot have None type")

    def parts(self) -> Mapping[str, object]:
        return {"name": Identifier(self.name), "type": self.type}


@dataclass(frozen=True)
class ClassSignature:
    """Nominal class declaration and static field/method membership."""

    identity: InstanceType
    fields: tuple[FieldDefinition, ...]
    methods: tuple[FunctionSignature, ...]
    base: ClassSignature | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.identity, InstanceType)
            or any(not isinstance(f, FieldDefinition) for f in self.fields)
            or any(not isinstance(m, FunctionSignature) for m in self.methods)
        ):
            raise ConstructError(
                "Class needs an identity, fields, and method declarations"
            )
        if self.identity.base != (self.base.identity if self.base else None):
            raise ConstructError("Class signature base must match nominal identity")
        if len({f.name for f in self.fields}) != len(self.fields):
            raise ConstructError("Duplicate instance field")
        if len({m.name for m in self.methods}) != len(self.methods):
            raise ConstructError("Duplicate method")
        if {f.name for f in self.fields} & {m.name for m in self.methods}:
            raise ConstructError("Field conflicts with method")
        for signature in self.methods:
            if signature.scope != (*self.identity.scope, self.identity.name):
                raise ConstructError(
                    "Method requires matching declared receiver and class scope"
                )
            if signature.method_kind in {None, MethodKind.INSTANCE}:
                receiver = signature.receiver
                if receiver is None or receiver.instance_type != self.identity:
                    raise ConstructError("Instance method requires its class receiver")
            elif signature.method_kind is MethodKind.CLASS:
                receiver = signature.class_receiver
                if receiver is None or receiver.annotation != self.identity.name:
                    raise ConstructError("Class method requires a class receiver")
            elif signature.method_kind is not MethodKind.STATIC:
                raise ConstructError("Unknown method kind")
        init = self.method("__init__")
        if (
            init is None
            or init.return_type.kind is not ValueKind.NONE
            or init.method_kind not in {None, MethodKind.INSTANCE}
        ):
            raise ConstructError("Class requires a None-returning initializer")
        if self.base is not None:
            for field in self.fields:
                if (
                    self.base.resolve_field(field.name) is not None
                    or self.base.resolve_method(field.name) is not None
                ):
                    raise ConstructError(
                        "Inherited member conflicts with declared field"
                    )
            for method in self.methods:
                if self.base.resolve_field(method.name) is not None:
                    raise ConstructError("Method conflicts with inherited field")
                if method.name == "__init__":
                    continue  # Derived constructor arguments may differ.
                inherited = self.base.resolve_method(method.name)
                if inherited is not None:
                    old = inherited[1]
                    # Static default expansion must be valid even when a
                    # base-typed receiver dispatches to an override.
                    if method.method_kind != old.method_kind:
                        raise ConstructError("Override must retain method kind")
                    shift = 0 if method.method_kind is MethodKind.STATIC else 1
                    if (
                        method.defaults_by_parameter[shift:]
                        != old.defaults_by_parameter[shift:]
                    ):
                        raise ConstructError(
                            "Override must preserve parameter defaults"
                        )
                    if (
                        tuple(p.value_type for p in method.parameters[shift:])
                        != tuple(p.value_type for p in old.parameters[shift:])
                        or method.return_type != old.return_type
                    ):
                        raise ConstructError(
                            "Override must preserve parameter and return types"
                        )

    def resolve_field(self, name: str) -> tuple[ClassSignature, FieldDefinition] | None:
        local = self.field(name)
        if local is not None:
            return self, local
        return self.base.resolve_field(name) if self.base is not None else None

    def resolve_method(
        self, name: str
    ) -> tuple[ClassSignature, FunctionSignature] | None:
        local = self.method(name)
        if local is not None:
            return self, local
        return self.base.resolve_method(name) if self.base is not None else None

    def field(self, name: str) -> FieldDefinition | None:
        return next((f for f in self.fields if f.name == name), None)

    def method(self, name: str) -> FunctionSignature | None:
        return next((m for m in self.methods if m.name == name), None)


class MethodDispatch(Enum):
    """Whether a call selects its method by runtime type or lexically by super."""

    VIRTUAL = "virtual"
    SUPER = "super"


@dataclass(frozen=True)
class ClassDefinition(Construct):
    """Static nominal class with existing FunctionDefinition method bodies."""

    signature: ClassSignature
    methods: tuple[FunctionDefinition, ...]
    docstring: str | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"name", "fields", "methods"})

    def __post_init__(self) -> None:
        if tuple(m.signature for m in self.methods) != self.signature.methods:
            raise ConstructError("Class methods must match their declaration")
        if self.docstring is not None and not isinstance(self.docstring, str):
            raise ConstructError("Class docstring must be text")

    def parts(self) -> Mapping[str, object]:
        return {
            "name": Identifier(self.signature.identity.name),
            "fields": self.signature.fields,
            "methods": self.methods,
        }


@dataclass(frozen=True)
class InstanceCreation(Value):
    """Create a fresh instance, then invoke its declared initializer once."""

    signature: ClassSignature
    arguments: tuple[Value, ...]
    evaluation_order: tuple[
        int, ...
    ] = ()  # Parameter indices in source-evaluation order.
    omitted_arguments: tuple[int, ...] = ()  # Indices filled from declared defaults.
    HOLES: ClassVar[frozenset[str]] = frozenset({"class_name"})

    def __post_init__(self) -> None:
        _call_evaluation_order(self.arguments, self.evaluation_order)
        if not isinstance(self.signature, ClassSignature):
            raise ConstructError("Instance creation requires a class signature")
        init = self.signature.method("__init__")
        assert init is not None
        _validate_omitted_defaults(
            self.arguments,
            self.evaluation_order,
            self.omitted_arguments,
            init.defaults_by_parameter[1:],
        )
        params = init.parameters[1:]
        if (
            len(self.arguments) != len(params)
            or any(not isinstance(v, Value) for v in self.arguments)
            or any(not _compatible(p, v) for p, v in zip(params, self.arguments))
        ):
            raise ConstructError("Instance initializer argument mismatch")

    @property
    def value_type(self) -> ValueType:
        return ValueType(ValueKind.INSTANCE, instance_type=self.signature.identity)

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return super().accepts_part_name(name) or _numbered_part(name, "arg")

    @property
    def argument_evaluation_order(self) -> tuple[int, ...]:
        """Parameter indices in the order their source expressions must run."""
        return _call_evaluation_order(self.arguments, self.evaluation_order)

    @property
    def evaluation_arguments(self) -> tuple[Value, ...]:
        """Expressions in source evaluation order, independent of slot order."""
        return tuple(self.arguments[i] for i in self.argument_evaluation_order)

    @property
    def supplied_evaluation_arguments(self) -> tuple[Value, ...]:
        """Only expressions written at the call site, in source order."""
        omitted = set(self.omitted_arguments)
        return tuple(
            self.arguments[i]
            for i in self.argument_evaluation_order
            if i not in omitted
        )

    def parts(self) -> Mapping[str, object]:
        return {
            "class_name": Identifier(self.signature.identity.name),
            **{f"arg{i}": v for i, v in enumerate(self.arguments)},
        }


@dataclass(frozen=True)
class ClassReference(Value):
    """Statically named class receiver. Not a general Python class object."""

    signature: ClassSignature
    HOLES: ClassVar[frozenset[str]] = frozenset({"class_name"})

    def __post_init__(self) -> None:
        if not isinstance(self.signature, ClassSignature):
            raise ConstructError("ClassReference requires a class signature")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.OBJECT

    def parts(self) -> Mapping[str, object]:
        return {"class_name": Identifier(self.signature.identity.name)}


@dataclass(frozen=True)
class ClassMethodCall(Value):
    """Static/class method invocation with explicit class receiver provenance.

    A CLASS method receives the runtime class identified by `class_source`;
    STATIC methods ignore that receiver. Neither implies Python descriptors.
    """

    class_source: Value
    signature: FunctionSignature
    arguments: tuple[Value, ...]
    owner: ClassSignature
    evaluation_order: tuple[int, ...] = ()
    omitted_arguments: tuple[int, ...] = ()
    HOLES: ClassVar[frozenset[str]] = frozenset({"class_source", "method"})

    def __post_init__(self) -> None:
        _call_evaluation_order(self.arguments, self.evaluation_order)
        identity = (
            self.class_source.signature.identity
            if isinstance(self.class_source, ClassReference)
            else None
        )
        if (
            isinstance(self.class_source, Reference)
            and self.class_source.symbol.role is ParameterRole.CLASS_RECEIVER
            and self.class_source.symbol.annotation == self.owner.identity.name
        ):
            # A class receiver's nominal base is identified by its annotation.
            identity = self.owner.identity
        resolved = self.owner.resolve_method(self.signature.name)
        if (
            identity is None
            or not identity.is_subtype_of(self.owner.identity)
            or self.signature.method_kind not in {MethodKind.STATIC, MethodKind.CLASS}
            or resolved is None
            or resolved[1] != self.signature
        ):
            raise ConstructError("Class method call has incompatible owner or method")
        start = 0 if self.signature.method_kind is MethodKind.STATIC else 1
        _validate_omitted_defaults(
            self.arguments,
            self.evaluation_order,
            self.omitted_arguments,
            self.signature.defaults_by_parameter[start:],
        )
        if len(self.arguments) != len(self.signature.parameters[start:]) or any(
            not _compatible(p, v)
            for p, v in zip(self.signature.parameters[start:], self.arguments)
        ):
            raise ConstructError("Class method argument mismatch")

    @property
    def value_type(self) -> ValueType:
        return self.signature.return_type

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return super().accepts_part_name(name) or _numbered_part(name, "arg")

    @property
    def argument_evaluation_order(self) -> tuple[int, ...]:
        return _call_evaluation_order(self.arguments, self.evaluation_order)

    @property
    def supplied_evaluation_arguments(self) -> tuple[Value, ...]:
        omitted = set(self.omitted_arguments)
        return tuple(
            self.arguments[i]
            for i in self.argument_evaluation_order
            if i not in omitted
        )

    def parts(self) -> Mapping[str, object]:
        return {
            "class_source": self.class_source,
            "method": Identifier(self.signature.name),
            **{f"arg{i}": v for i, v in enumerate(self.arguments)},
        }


@dataclass(frozen=True)
class ClassReceiverCreation(Value):
    """Construct an instance of the runtime class bound to a class receiver.

    Receiver remains dynamic; its nominal lower bound is `signature.identity`.
    Target Realization must preserve runtime class identity, not instantiate
    the lexical base unconditionally.
    """

    receiver: Reference
    signature: ClassSignature
    arguments: tuple[Value, ...]
    evaluation_order: tuple[int, ...] = ()
    omitted_arguments: tuple[int, ...] = ()
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver"})

    def __post_init__(self) -> None:
        if (
            self.receiver.symbol.role is not ParameterRole.CLASS_RECEIVER
            or self.receiver.symbol.annotation != self.signature.identity.name
        ):
            raise ConstructError("Class factory requires a class receiver")
        init = self.signature.method("__init__")
        assert init is not None
        _call_evaluation_order(self.arguments, self.evaluation_order)
        _validate_omitted_defaults(
            self.arguments,
            self.evaluation_order,
            self.omitted_arguments,
            init.defaults_by_parameter[1:],
        )
        if len(self.arguments) != len(init.parameters) - 1 or any(
            not _compatible(p, v) for p, v in zip(init.parameters[1:], self.arguments)
        ):
            raise ConstructError("Class factory argument mismatch")

    @property
    def value_type(self) -> ValueType:
        return ValueType(ValueKind.INSTANCE, instance_type=self.signature.identity)

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return super().accepts_part_name(name) or _numbered_part(name, "arg")

    @property
    def argument_evaluation_order(self) -> tuple[int, ...]:
        return _call_evaluation_order(self.arguments, self.evaluation_order)

    @property
    def supplied_evaluation_arguments(self) -> tuple[Value, ...]:
        omitted = set(self.omitted_arguments)
        return tuple(
            self.arguments[i]
            for i in self.argument_evaluation_order
            if i not in omitted
        )

    def parts(self) -> Mapping[str, object]:
        return {
            "receiver": self.receiver,
            **{f"arg{i}": v for i, v in enumerate(self.arguments)},
        }


@dataclass(frozen=True)
class FieldRead(Value):
    """Read a statically declared field of a receiver instance."""

    receiver: Value
    field: FieldDefinition
    owner: ClassSignature
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver", "field"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.owner, ClassSignature)
            or self.receiver.instance_type is None
            or not self.receiver.instance_type.is_subtype_of(self.owner.identity)
            or not isinstance(self.field, FieldDefinition)
            or self.field not in self.owner.fields
        ):
            raise ConstructError(
                "Field access receiver/type mismatch or undeclared field"
            )

    @property
    def value_type(self) -> ValueType:
        return self.field.type

    def parts(self) -> Mapping[str, object]:
        return {"receiver": self.receiver, "field": Identifier(self.field.name)}


@dataclass(frozen=True)
class FieldWrite(Construct):
    """Mutate a previously declared field on an existing instance."""

    receiver: Value
    field: FieldDefinition
    owner: ClassSignature
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver", "field", "value"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.owner, ClassSignature)
            or self.receiver.instance_type is None
            or not self.receiver.instance_type.is_subtype_of(self.owner.identity)
            or self.field not in self.owner.fields
            or not _value_type_compatible(self.field.type, self.value)
        ):
            raise ConstructError("Field assignment type mismatch")

    def parts(self) -> Mapping[str, object]:
        return {
            "receiver": self.receiver,
            "field": Identifier(self.field.name),
            "value": self.value,
        }


@dataclass(frozen=True)
class FieldInitialize(FieldWrite):
    """First explicit typed initialization of a field inside __init__."""


@dataclass(frozen=True)
class MethodCall(Value):
    """Typed method call; virtual dispatch retains runtime instance semantics."""

    receiver: Value
    signature: FunctionSignature
    arguments: tuple[Value, ...]
    owner: ClassSignature
    dispatch: MethodDispatch = MethodDispatch.VIRTUAL
    lookup_start: ClassSignature | None = None
    evaluation_order: tuple[
        int, ...
    ] = ()  # Parameter indices in source-evaluation order.
    omitted_arguments: tuple[int, ...] = ()  # Indices filled from declared defaults.
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver", "method"})

    def __post_init__(self) -> None:
        _call_evaluation_order(self.arguments, self.evaluation_order)
        parameter = self.signature.receiver
        if (
            not isinstance(self.owner, ClassSignature)
            or not isinstance(self.dispatch, MethodDispatch)
            or parameter is None
            or self.receiver.instance_type is None
            or not self.receiver.instance_type.is_subtype_of(self.owner.identity)
        ):
            raise ConstructError("Method call receiver mismatch")
        if self.dispatch is MethodDispatch.VIRTUAL:
            found = self.owner.resolve_method(self.signature.name)
            if (
                self.lookup_start is not None
                or found is None
                or found[1] != self.signature
            ):
                raise ConstructError(
                    "Method call receiver mismatch or undeclared method"
                )
        else:
            if (
                self.lookup_start is None
                or self.owner.base is None
                or self.lookup_start != self.owner.base
            ):
                raise ConstructError("Super call requires lexical base method")
            found = self.lookup_start.resolve_method(self.signature.name)
            if found is None or found[1] != self.signature:
                raise ConstructError("Super call requires lexical base method")
        _validate_omitted_defaults(
            self.arguments,
            self.evaluation_order,
            self.omitted_arguments,
            self.signature.defaults_by_parameter[1:],
        )
        params = self.signature.parameters[1:]
        if (
            len(self.arguments) != len(params)
            or any(not isinstance(v, Value) for v in self.arguments)
            or any(not _compatible(p, v) for p, v in zip(params, self.arguments))
        ):
            raise ConstructError("Method argument mismatch")

    @property
    def value_type(self) -> ValueType:
        return self.signature.return_type

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return super().accepts_part_name(name) or _numbered_part(name, "arg")

    @property
    def argument_evaluation_order(self) -> tuple[int, ...]:
        """Parameter indices in the order their source expressions must run."""
        return _call_evaluation_order(self.arguments, self.evaluation_order)

    @property
    def evaluation_arguments(self) -> tuple[Value, ...]:
        """Expressions in source evaluation order, independent of slot order."""
        return tuple(self.arguments[i] for i in self.argument_evaluation_order)

    @property
    def supplied_evaluation_arguments(self) -> tuple[Value, ...]:
        """Only expressions written at the call site, in source order."""
        omitted = set(self.omitted_arguments)
        return tuple(
            self.arguments[i]
            for i in self.argument_evaluation_order
            if i not in omitted
        )

    def parts(self) -> Mapping[str, object]:
        return {
            "receiver": self.receiver,
            "method": Identifier(self.signature.name),
            **{f"arg{i}": v for i, v in enumerate(self.arguments)},
        }


def _numbered_part(name: str, prefix: str) -> bool:
    suffix = name[len(prefix) :] if name.startswith(prefix) else ""
    return bool(
        suffix
        and suffix.isascii()
        and suffix.isdecimal()
        and (suffix == "0" or not suffix.startswith("0"))
    )
