"""Target-independent functions definitions for the pyinto Construct Model."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import ClassVar

from .base import Construct, Value
from .control import Block, Branch, For, Try, While, With
from .type_rules import _compatible, _value_type_compatible
from .types import (
    CallableType,
    ConstructError,
    Identifier,
    MethodKind,
    ParameterRole,
    Symbol,
    ValueKind,
    ValueType,
)
from .values import BooleanLiteral, FloatingLiteral, Literal, NoneLiteral


@dataclass(frozen=True)
class FunctionSignature:
    """Statically resolved, target-independent callable declaration."""

    name: str
    parameters: tuple[Symbol, ...]
    return_annotation: str
    return_type: ValueType
    # Declaration scope, not the scope of the function body.
    scope: tuple[str, ...] = ()
    # One optional scalar default per declared parameter; None means required.
    # NoneLiteral() is the distinct, explicit default value None.
    parameter_defaults: tuple[Value | None, ...] = ()
    method_kind: MethodKind | None = None
    # Body binding for *args, typed as tuple[T, ...], not as one T argument.
    variadic_parameter: Symbol | None = None
    _value_symbol: Symbol | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.parameter_defaults and len(self.parameter_defaults) != len(
            self.parameters
        ):
            raise ConstructError("Function defaults must align with parameters")
        seen_default = False
        for param, default in zip(self.parameters, self.defaults_by_parameter):
            if default is None:
                if seen_default and param.role is not ParameterRole.RECEIVER:
                    raise ConstructError("Required parameter after default")
                continue
            if param.role in {ParameterRole.RECEIVER, ParameterRole.CLASS_RECEIVER}:
                raise ConstructError("Method receiver cannot have a default")
            if not isinstance(
                default, (Literal, FloatingLiteral, BooleanLiteral, NoneLiteral)
            ):
                raise ConstructError(
                    "Only immutable scalar default literals are supported"
                )
            if not _compatible(param, default):
                raise ConstructError("Function default argument type mismatch")
            seen_default = True
        if not isinstance(self.return_type, ValueType):
            raise ConstructError("Function requires a valid return ValueType")
        if self.variadic_parameter is not None and (
            not isinstance(self.variadic_parameter, Symbol)
            or self.variadic_parameter.role is not ParameterRole.VARIADIC
            or self.method_kind is not None
            or self.variadic_parameter.scope != (*self.scope, self.name)
        ):
            raise ConstructError(
                "Variadic parameters require a plain function and tuple binding"
            )
        receivers = [
            i for i, p in enumerate(self.parameters) if p.role is ParameterRole.RECEIVER
        ]
        class_receivers = [
            i
            for i, p in enumerate(self.parameters)
            if p.role is ParameterRole.CLASS_RECEIVER
        ]
        if receivers and (
            receivers != [0] or self.method_kind not in {None, MethodKind.INSTANCE}
        ):
            raise ConstructError(
                "Instance receiver must be first in an instance method"
            )
        if class_receivers and (
            class_receivers != [0] or self.method_kind is not MethodKind.CLASS
        ):
            raise ConstructError("Class receiver must be first in a class method")
        if self.method_kind is MethodKind.INSTANCE and receivers != [0]:
            raise ConstructError("Instance method requires receiver")
        if self.method_kind is MethodKind.CLASS and class_receivers != [0]:
            raise ConstructError("Class method requires class receiver")
        if self.method_kind is MethodKind.STATIC and (receivers or class_receivers):
            raise ConstructError("Static method cannot have a receiver")
        if not self.name.isidentifier():
            raise ConstructError("Function name must be an identifier")
        names = [symbol.name for symbol in self.parameters]
        if self.variadic_parameter is not None:
            names.append(self.variadic_parameter.name)
        if len(names) != len(set(names)):
            raise ConstructError("Duplicate function parameter")
        if any(
            symbol.kind is None or symbol.role is ParameterRole.VARIADIC
            for symbol in self.parameters
        ):
            raise ConstructError(
                "Fixed parameters require ordinary or receiver value types"
            )
        if not self.return_annotation:
            raise ConstructError("Function requires an explicit return annotation")
        if self.variadic_parameter is not None or any(
            p.kind is ValueKind.PORT_OBJECT for p in self.parameters
        ):
            # Variadic function *values* are not representable as the existing
            # fixed-arity CallableType. Direct calls remain fully supported.
            object.__setattr__(self, "_value_symbol", None)
        else:
            shape = self.callable_type
            object.__setattr__(
                self,
                "_value_symbol",
                Symbol(
                    self.name,
                    ValueType(ValueKind.FUNCTION, callable_type=shape),
                    shape.annotation(),
                    scope=self.scope,
                ),
            )

    @property
    def defaults_by_parameter(self) -> tuple[Value | None, ...]:
        """Parameter-aligned defaults; None is absence, not NoneLiteral."""
        return self.parameter_defaults or (None,) * len(self.parameters)

    @property
    def callable_type(self) -> CallableType:
        if self.variadic_parameter is not None:
            raise ConstructError("Variadic function values are unsupported")
        if any(p.kind is ValueKind.PORT_OBJECT for p in self.parameters):
            raise ConstructError(
                "Unshaped Port types cannot be used as function values"
            )
        return CallableType(
            tuple(p.value_type for p in self.parameters),
            self.return_type,
        )

    @property
    def receiver(self) -> Symbol | None:
        return (
            self.parameters[0]
            if self.parameters and self.parameters[0].role is ParameterRole.RECEIVER
            else None
        )

    @property
    def class_receiver(self) -> Symbol | None:
        return self.parameters[0] if self.method_kind is MethodKind.CLASS else None

    @property
    def value_symbol(self) -> Symbol:
        """One stable, declaration-owned symbol used by function-value References."""
        if self._value_symbol is None:
            raise ConstructError("Function declaration has no supported value type")
        return self._value_symbol


@dataclass(frozen=True)
class Parameter(Construct):
    """A declared parameter, including its original type annotation."""

    symbol: Symbol
    default: Value | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"name", "type", "default"})

    def __post_init__(self) -> None:
        if self.symbol.kind is None:
            raise ConstructError("Parameter must have a value type")
        if self.default is not None and (
            not isinstance(
                self.default, (Literal, FloatingLiteral, BooleanLiteral, NoneLiteral)
            )
            or not _compatible(self.symbol, self.default)
        ):
            raise ConstructError("Parameter requires a type-compatible scalar default")

    def parts(self) -> Mapping[str, object]:
        parts: dict[str, object] = {
            "name": Identifier(self.symbol.name),
            "type": self.symbol,
        }
        if self.default is not None:
            parts["default"] = self.default
        return parts


def _returns_in_body(body: Block) -> Iterator[Return]:
    """Yield returns owned by this function, without walking expression trees.

    Only statement-level control containers introduce sub-blocks. Nested
    FunctionDefinitions (including LambdaValues inside expressions) own their
    returns independently; no Target execution paths are evaluated here.
    """
    for statement in body.children:
        if isinstance(statement, Return):
            yield statement
        elif isinstance(statement, Block):
            yield from _returns_in_body(statement)
        elif isinstance(statement, Branch):
            yield from _returns_in_body(statement.then_body)
            if statement.else_body is not None:
                yield from _returns_in_body(statement.else_body)
        elif isinstance(statement, (While, For)):
            yield from _returns_in_body(statement.body)
            if statement.else_body is not None:
                yield from _returns_in_body(statement.else_body)
        elif isinstance(statement, With):
            yield from _returns_in_body(statement.body)
        elif isinstance(statement, Try):
            yield from _returns_in_body(statement.body)
            for handler in statement.handlers:
                yield from _returns_in_body(handler.body)
            if statement.else_body is not None:
                yield from _returns_in_body(statement.else_body)
            if statement.finally_body is not None:
                yield from _returns_in_body(statement.finally_body)


@dataclass(frozen=True)
class FunctionDefinition(Construct):
    """A declared function and its normalized body, without Target code."""

    signature: FunctionSignature
    body: Block
    docstring: str | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset(
        {"name", "return_type", "parameters", "variadic_parameter", "body"}
    )

    def __post_init__(self) -> None:
        if not isinstance(self.signature, FunctionSignature) or not isinstance(
            self.body, Block
        ):
            raise ConstructError("Function definition requires a signature and Block")
        if self.docstring is not None and not isinstance(self.docstring, str):
            raise ConstructError("Function docstring must be text")
        expected = self.signature.return_type
        for statement in _returns_in_body(self.body):
            result = statement.value
            if expected.kind is ValueKind.NONE:
                if result is not None and not isinstance(result, NoneLiteral):
                    raise ConstructError("Function return type mismatch")
            elif result is None or (
                expected.kind not in (ValueKind.ANY, ValueKind.OBJECT)
                and not _value_type_compatible(expected, result)
            ):
                raise ConstructError("Function return type mismatch")

    def parts(self) -> Mapping[str, object]:
        parts: dict[str, object] = {
            "name": Identifier(self.signature.name),
            "return_type": self.signature.return_type,
            "parameters": tuple(
                Parameter(p, d)
                for p, d in zip(
                    self.signature.parameters, self.signature.defaults_by_parameter
                )
            ),
            "body": self.body,
        }
        if self.signature.variadic_parameter is not None:
            parts["variadic_parameter"] = Parameter(self.signature.variadic_parameter)
        return parts


@dataclass(frozen=True)
class LambdaValue(Value):
    """An anonymous, typed function value created at its expression site.

    Its enclosed FunctionDefinition reuses the ordinary declaration, body and
    lexical Symbol contracts. The expression creates a callable that retains
    the needed lexical environment; runtime closure allocation is a Realization
    responsibility. No Python function-object protocol is inferred.
    """

    definition: FunctionDefinition
    HOLES: ClassVar[frozenset[str]] = frozenset({"definition"})

    def __post_init__(self) -> None:
        if not isinstance(self.definition, FunctionDefinition):
            raise ConstructError("Lambda requires a function definition")
        body = self.definition.body.children
        if len(body) != 1 or not isinstance(body[0], Return):
            raise ConstructError("Lambda body must contain a single return")

    @property
    def value_type(self) -> ValueType:
        return ValueType(
            ValueKind.FUNCTION, callable_type=self.definition.signature.callable_type
        )

    def parts(self) -> Mapping[str, object]:
        return {"definition": self.definition}


@dataclass(frozen=True)
class Return(Construct):
    """An explicit function exit with an optional result expression."""

    value: Value | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"value"})

    def __post_init__(self) -> None:
        if self.value is not None and not isinstance(self.value, Value):
            raise ConstructError("Return requires a Value or no value")

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"default", "with_value"})

    def variant(self) -> str:
        return "with_value" if self.value is not None else "default"

    def parts(self) -> Mapping[str, object]:
        return {"value": self.value} if self.value is not None else {}


def _call_evaluation_order(
    arguments: tuple[Value, ...], order: tuple[int, ...]
) -> tuple[int, ...]:
    """Validate bound argument evaluation sequence (including inert defaults)."""
    if not isinstance(order, tuple) or any(type(i) is not int for i in order):
        raise ConstructError("Call evaluation order must be integer indices")
    if order and sorted(order) != list(range(len(arguments))):
        raise ConstructError("Call evaluation order must be a parameter permutation")
    return order if order else tuple(range(len(arguments)))


def _validate_omitted_defaults(
    arguments: tuple[Value, ...],
    evaluation_order: tuple[int, ...],
    omitted: tuple[int, ...],
    defaults: tuple[Value | None, ...],
) -> None:
    """Omitted arguments are immutable defaults, never dynamic evaluations.

    All argument slots remain filled for existing Realizations. Evaluation
    order puts supplied expressions first, and inert defaults last.
    """
    if not isinstance(omitted, tuple) or any(type(i) is not int for i in omitted):
        raise ConstructError("Omitted parameter indices must be integers")
    if tuple(sorted(set(omitted))) != omitted or any(
        i < 0 or i >= len(arguments) for i in omitted
    ):
        raise ConstructError("Omitted parameters must be sorted unique indices")
    if omitted:
        order = _call_evaluation_order(arguments, evaluation_order)
        if order[-len(omitted) :] != omitted:
            raise ConstructError("Omitted defaults must follow supplied evaluations")
    for i in omitted:
        if defaults[i] is None or arguments[i] != defaults[i]:
            raise ConstructError("Omitted call argument does not match its default")


@dataclass(frozen=True)
class FunctionCall(Value):
    """A statically resolved function reference and typed call arguments."""

    signature: FunctionSignature
    arguments: tuple[Value, ...]
    evaluation_order: tuple[
        int, ...
    ] = ()  # Parameter indices in source-evaluation order.
    omitted_arguments: tuple[int, ...] = ()  # Indices filled from declared defaults.

    def __post_init__(self) -> None:
        _call_evaluation_order(self.arguments, self.evaluation_order)
        fixed = len(self.signature.parameters)
        if len(self.arguments) < fixed or (
            len(self.arguments) > fixed and self.signature.variadic_parameter is None
        ):
            raise ConstructError("Function argument count mismatch")
        if any(i >= fixed for i in self.omitted_arguments):
            raise ConstructError("Variadic call arguments cannot be omitted defaults")
        _validate_omitted_defaults(
            self.arguments,
            self.evaluation_order,
            self.omitted_arguments,
            self.signature.defaults_by_parameter
            + (None,) * (len(self.arguments) - len(self.signature.parameters)),
        )
        if not all(isinstance(argument, Value) for argument in self.arguments):
            raise ConstructError("Function call arguments must be Value objects")
        for parameter, value in zip(self.signature.parameters, self.arguments[:fixed]):
            if not _compatible(parameter, value):
                raise ConstructError("Function argument type mismatch")
        if self.signature.variadic_parameter is not None:
            shape = self.signature.variadic_parameter.value_type.tuple_type
            assert shape is not None and shape.variadic_element_type is not None
            if any(
                not _value_type_compatible(shape.variadic_element_type, argument)
                for argument in self.arguments[fixed:]
            ):
                raise ConstructError("Variadic function argument type mismatch")

    @property
    def value_type(self) -> ValueType:
        return self.signature.return_type

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return name == "callee" or (
            name.startswith("arg")
            and name[3:].isascii()
            and name[3:].isdecimal()
            and (name[3:] == "0" or not name[3:].startswith("0"))
        )

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
            "callee": Identifier(self.signature.name),
            **{f"arg{i}": value for i, value in enumerate(self.arguments)},
        }


@dataclass(frozen=True)
class FunctionValueCall(Value):
    """Call a typed first-class function Value rather than a declaration.

    The callee is evaluated once before the positional arguments, which are
    evaluated in source order. Any captured environment belongs to the value;
    the Model does not choose its representation or lifetime strategy.
    """

    callee: Value
    arguments: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"callee"})

    def __post_init__(self) -> None:
        if not isinstance(self.callee, Value):
            raise ConstructError("Function value callee must be a Value")
        if self.callee.kind is not ValueKind.FUNCTION:
            raise ConstructError("Function value callee must be a function")
        shape = self.callee.callable_type
        if shape is None:
            raise ConstructError("Function value callee has no callable shape")
        if not all(isinstance(argument, Value) for argument in self.arguments):
            raise ConstructError("Function value arguments must be Values")
        if len(self.arguments) != len(shape.parameter_types):
            raise ConstructError("Function value argument count mismatch")
        for expected, actual in zip(shape.parameter_types, self.arguments):
            if not _value_type_compatible(expected, actual):
                raise ConstructError("Function value argument type mismatch")

    @property
    def value_type(self) -> ValueType:
        shape = self.callee.callable_type
        assert shape is not None
        return shape.return_type

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        return name == "callee" or (
            name.startswith("arg")
            and name[3:].isascii()
            and name[3:].isdecimal()
            and (name[3:] == "0" or not name[3:].startswith("0"))
        )

    def parts(self) -> Mapping[str, object]:
        return {
            "callee": self.callee,
            **{f"arg{i}": value for i, value in enumerate(self.arguments)},
        }
