"""Target-independent types definitions for the pyinto Construct Model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConstructError(ValueError):
    """A Model contract or requested Realization cannot be satisfied."""


class ValueKind(Enum):
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    PORT_OBJECT = "port_object"
    ANY = "any"
    OBJECT = "object"
    ITERABLE = "iterable"
    NONE = "none"
    FUNCTION = "function"
    TUPLE = "tuple"
    LIST = "list"
    DICT = "dict"
    INSTANCE = "instance"


@dataclass(frozen=True)
class InstanceType:
    """Nominal identity of a statically declared class, not its Target layout."""

    name: str
    scope: tuple[str, ...] = ()
    base: InstanceType | None = None

    def __post_init__(self) -> None:
        if self.base is not None and not isinstance(self.base, InstanceType):
            raise ConstructError("Base class must be a declared InstanceType")
        if self.base is not None and (self.name, self.scope) == (
            self.base.name,
            self.base.scope,
        ):
            raise ConstructError("Class cannot inherit itself")
        if not self.name.isidentifier() or any(
            not n.isidentifier() for n in self.scope
        ):
            raise ConstructError("Class identity requires identifier names")

    def annotation(self) -> str:
        return self.name

    def is_subtype_of(self, other: InstanceType) -> bool:
        current: InstanceType | None = self
        while current is not None:
            if current == other:
                return True
            current = current.base
        return False


class ParameterRole(Enum):
    ORDINARY = "ordinary"
    RECEIVER = "receiver"
    CLASS_RECEIVER = "class_receiver"
    VARIADIC = "variadic"  # Homogeneous tuple bound by *args.


class MethodKind(Enum):
    INSTANCE = "instance"
    STATIC = "static"
    CLASS = "class"


@dataclass(frozen=True)
class ValueType:
    """A value kind with optional recursively declared callable or tuple shape."""

    kind: ValueKind
    callable_type: CallableType | None = None
    tuple_type: TupleType | None = None
    list_type: ListType | None = None
    dict_type: DictType | None = None
    instance_type: InstanceType | None = None

    def __post_init__(self) -> None:
        if (self.kind is ValueKind.FUNCTION) != (self.callable_type is not None):
            raise ConstructError(
                "Function value types require exactly one callable shape"
            )
        if (self.kind is ValueKind.TUPLE) != (self.tuple_type is not None):
            raise ConstructError("Tuple value types require exactly one tuple shape")
        if self.tuple_type is not None and not isinstance(self.tuple_type, TupleType):
            raise ConstructError("Tuple value type requires a valid tuple shape")
        if (self.kind is ValueKind.LIST) != (self.list_type is not None):
            raise ConstructError("List value types require exactly one element shape")
        if self.list_type is not None and not isinstance(self.list_type, ListType):
            raise ConstructError("List value type requires a valid list shape")
        if (self.kind is ValueKind.DICT) != (self.dict_type is not None):
            raise ConstructError("Dict value types require exactly one key/value shape")
        if self.dict_type is not None and not isinstance(self.dict_type, DictType):
            raise ConstructError("Dict value type requires a valid dict shape")
        if (self.kind is ValueKind.INSTANCE) != (self.instance_type is not None):
            raise ConstructError("Instance value types require a nominal class")
        if self.instance_type is not None and not isinstance(
            self.instance_type, InstanceType
        ):
            raise ConstructError("Instance type must identify a class")
        if self.kind is ValueKind.PORT_OBJECT:
            raise ConstructError(
                "Callable signatures cannot contain unshaped Port objects"
            )

    def annotation(self) -> str:
        if self.callable_type is not None:
            return self.callable_type.annotation()
        if self.tuple_type is not None:
            return self.tuple_type.annotation()
        if self.list_type is not None:
            return self.list_type.annotation()
        if self.dict_type is not None:
            return self.dict_type.annotation()
        if self.instance_type is not None:
            return self.instance_type.annotation()
        spelling = {
            ValueKind.INTEGER: "int",
            ValueKind.FLOAT: "float",
            ValueKind.STRING: "str",
            ValueKind.BOOLEAN: "bool",
            ValueKind.OBJECT: "object",
            ValueKind.ANY: "Any",
            ValueKind.NONE: "None",
            ValueKind.ITERABLE: "Iterable",
        }
        if self.kind not in spelling:
            raise ConstructError("This value type has no callable annotation")
        return spelling[self.kind]


@dataclass(frozen=True)
class CallableType:
    """Pure structural type of a function value, without a target ABI."""

    parameter_types: tuple[ValueType, ...]
    return_type: ValueType

    def __post_init__(self) -> None:
        if any(
            not isinstance(t, ValueType) or t.kind is ValueKind.NONE
            for t in self.parameter_types
        ):
            raise ConstructError("Callable parameters must have valid value types")
        if not isinstance(self.return_type, ValueType):
            raise ConstructError("Callable return type must be a value type")

    def annotation(self) -> str:
        parameters = ", ".join(t.annotation() for t in self.parameter_types)
        return f"Callable[[{parameters}], {self.return_type.annotation()}]"


@dataclass(frozen=True)
class TupleType:
    """Either a fixed tuple, or a homogeneous runtime-length tuple.

    Variadic tuples retain Python tuple identity and immutability. They are
    distinct from fixed-length tuples, including the fixed empty tuple.
    """

    element_types: tuple[ValueType, ...] = ()
    variadic_element_type: ValueType | None = None

    def __post_init__(self) -> None:
        if self.variadic_element_type is not None:
            if self.element_types:
                raise ConstructError("Variadic tuple cannot have fixed elements")
            if not isinstance(
                self.variadic_element_type, ValueType
            ) or self.variadic_element_type.kind in {
                ValueKind.NONE,
                ValueKind.PORT_OBJECT,
            }:
                raise ConstructError("Variadic tuple needs a supported element type")
        if any(not isinstance(t, ValueType) for t in self.element_types):
            raise ConstructError("Tuple elements require valid value types")
        if any(
            t.kind in {ValueKind.NONE, ValueKind.PORT_OBJECT}
            for t in self.element_types
        ):
            raise ConstructError("Tuple elements require supported value types")

    def annotation(self) -> str:
        if self.variadic_element_type is not None:
            return f"tuple[{self.variadic_element_type.annotation()}, ...]"
        if not self.element_types:
            return "tuple[()]"
        return "tuple[" + ", ".join(t.annotation() for t in self.element_types) + "]"


@dataclass(frozen=True)
class ListType:
    """Homogeneous mutable list, with recursive element type, not a fixed length."""

    element_type: ValueType

    def __post_init__(self) -> None:
        if not isinstance(self.element_type, ValueType) or self.element_type.kind in {
            ValueKind.NONE,
            ValueKind.PORT_OBJECT,
        }:
            raise ConstructError("List requires a supported element value type")

    def annotation(self) -> str:
        return f"list[{self.element_type.annotation()}]"


@dataclass(frozen=True)
class DictType:
    """Typed mutable mapping with scalar, statically known key kind.

    The Model does not select hashing, storage, or a Target dictionary ABI.
    """

    key_type: ValueType
    value_type: ValueType

    def __post_init__(self) -> None:
        if not isinstance(self.key_type, ValueType) or self.key_type.kind not in {
            ValueKind.INTEGER,
            ValueKind.STRING,
        }:
            raise ConstructError("Dict keys require int or str ValueType")
        if not isinstance(self.value_type, ValueType) or self.value_type.kind in {
            ValueKind.NONE,
            ValueKind.PORT_OBJECT,
        }:
            raise ConstructError("Dict values require a supported ValueType")

    def annotation(self) -> str:
        return f"dict[{self.key_type.annotation()}, {self.value_type.annotation()}]"


@dataclass(frozen=True)
class PortType:
    """Declared Python Port shape, not a target representation or identity."""

    source: str
    variant: str
    constraints: tuple[tuple[str, int], ...]

    @property
    def key(self) -> str:
        return f"port:{self.source}.{self.variant}"

    def options(self) -> dict[str, int]:
        return dict(self.constraints)


@dataclass(frozen=True)
class Symbol:
    """A lexical binding with one declared type.

    Built-in callables have no value type; external Port instances have a
    PortType instead of a regular ValueType. Neither case is silently coerced
    into an ordinary value type.
    """

    name: str
    type: ValueType | PortType | None
    annotation: str | None = None
    # Lexical owner of a declaration. Empty for module-level bindings.
    scope: tuple[str, ...] = ()
    role: ParameterRole = ParameterRole.ORDINARY

    def __post_init__(self) -> None:
        if self.type is not None and not isinstance(self.type, (ValueType, PortType)):
            raise ValueError("Symbol requires a declared ValueType or PortType")
        if not isinstance(self.role, ParameterRole):
            raise TypeError("Unknown parameter role")
        if self.role is ParameterRole.VARIADIC and (
            not isinstance(self.type, ValueType)
            or self.type.tuple_type is None
            or self.type.tuple_type.variadic_element_type is None
        ):
            raise ValueError("Variadic parameter requires a homogeneous tuple type")
        if self.role is ParameterRole.RECEIVER and self.kind is not ValueKind.INSTANCE:
            raise ValueError("Receiver must have an instance type")
        if (
            self.role is ParameterRole.CLASS_RECEIVER
            and self.kind is not ValueKind.OBJECT
        ):
            raise ValueError("Class receiver must be an object-role symbol")
        if self.type is not None and self.annotation is None:
            raise ValueError("Value symbols require an explicit type annotation")

    @property
    def kind(self) -> ValueKind | None:
        if isinstance(self.type, ValueType):
            return self.type.kind
        return ValueKind.PORT_OBJECT if isinstance(self.type, PortType) else None

    @property
    def value_type(self) -> ValueType:
        if not isinstance(self.type, ValueType):
            raise ConstructError("Port and built-in symbols have no ValueType")
        return self.type

    @property
    def port_type(self) -> PortType | None:
        return self.type if isinstance(self.type, PortType) else None

    @property
    def callable_type(self) -> CallableType | None:
        return self.type.callable_type if isinstance(self.type, ValueType) else None

    @property
    def tuple_type(self) -> TupleType | None:
        return self.type.tuple_type if isinstance(self.type, ValueType) else None

    @property
    def list_type(self) -> ListType | None:
        return self.type.list_type if isinstance(self.type, ValueType) else None

    @property
    def dict_type(self) -> DictType | None:
        return self.type.dict_type if isinstance(self.type, ValueType) else None

    @property
    def instance_type(self) -> InstanceType | None:
        return self.type.instance_type if isinstance(self.type, ValueType) else None


@dataclass(frozen=True)
class Identifier:
    """A source-level name to be validated and spelled by a Target.

    This is Model data, not a pre-rendered Target name.
    """

    value: str
