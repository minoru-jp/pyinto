"""Per-parse expression normalizer with explicit cross-domain dependencies.

Expression rules do not inherit the PythonFrontend service surface. They
receive only the naming, function and class operations used by expressions.
"""

from __future__ import annotations

import ast
from typing import Protocol

from pyinto.constructs import (
    Absolute,
    AddressOf,
    Arithmetic,
    BooleanAggregate,
    BooleanLiteral,
    BooleanNot,
    BooleanOperation,
    ClassMethodCall,
    ClassReceiverCreation,
    ClassSignature,
    Comparison,
    ComparisonChain,
    ConditionalExpression,
    Construct,
    ConstructError,
    DictElement,
    DictEntry,
    DictValue,
    Extremum,
    FieldDefinition,
    FieldRead,
    FloatingArithmetic,
    FloatingComparison,
    FloatingLiteral,
    FloatingUnary,
    FormattedString,
    FunctionCall,
    FunctionSignature,
    FunctionValueCall,
    InstanceCreation,
    IntegerSum,
    IntegerTrueDivision,
    IntegerUnary,
    IntrinsicCall,
    LambdaValue,
    Length,
    ListElement,
    ListValue,
    Literal,
    Membership,
    MemoryBorrow,
    MemoryCopy,
    MemoryFill,
    MemoryLength,
    MemoryNew,
    MemoryNewBuffer,
    MemoryRelease,
    MemoryResize,
    MethodCall,
    NoneAlias,
    NoneAliasComparison,
    NoneLiteral,
    ParameterRole,
    PointerLoad,
    PointerStore,
    Range,
    Reference,
    SliceValue,
    StringComparison,
    StringConcat,
    StringContains,
    StringElement,
    StringRepeat,
    Symbol,
    TupleElement,
    TupleValue,
    Value,
    ValueKind,
    ValueType,
)
from pyinto.constructs.type_rules import is_none_alias
from pyinto.constructs.types import NONE_ALIASES
from pyinto.intrinsics import IntrinsicRegistry

from .context import ParseContext
from .errors import UnsupportedPython, reject
from .interface_mapping import InterfaceMappingNormalizer
from .kinds import MEMORY_OPERATIONS, memory_operation, pointer_operation


class ExpressionServices(Protocol):
    """Only non-expression operations that can be requested by expressions."""

    def _lookup_symbol(self, name: str) -> Symbol | None: ...

    def _annotation(self, node: ast.expr) -> tuple[str, ValueType | None]: ...

    def _lookup_function(self, name: str) -> FunctionSignature | None: ...

    def _field(
        self, node: ast.Attribute, receiver: Value | None = None
    ) -> tuple[Value, ClassSignature, FieldDefinition]: ...

    def _class_receiver_source(
        self, node: ast.expr
    ) -> tuple[Value, ClassSignature] | None: ...

    def _class_method_call(self, node: ast.Call) -> ClassMethodCall: ...

    def _class_receiver_creation(self, node: ast.Call) -> ClassReceiverCreation: ...

    def _instance_creation(self, node: ast.Call) -> InstanceCreation: ...

    def _instance_member_call(
        self, node: ast.Call, receiver: Value | None = None
    ) -> MethodCall | FunctionValueCall: ...

    def _function_call(self, node: ast.Call) -> FunctionCall: ...

    def _function_value_call(
        self, node: ast.Call, callee: Value
    ) -> FunctionValueCall: ...

    def _lambda_value(
        self, node: ast.Lambda, expected: ValueType | None
    ) -> LambdaValue: ...


class ExpressionNormalizer:
    """Normalize expressions with no inherited frontend behavior."""

    def __init__(
        self,
        context: ParseContext,
        interface_mappings: InterfaceMappingNormalizer,
        services: ExpressionServices,
        intrinsics: IntrinsicRegistry | None = None,
    ) -> None:
        self._context = context
        self._interface_mapping_normalizer = interface_mappings
        self._services = services
        self._intrinsics = intrinsics if intrinsics is not None else IntrinsicRegistry()

    @staticmethod
    def _is_super_expression(node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "super"
        )

    def _instance_receiver(self, node: ast.expr) -> Value | None:
        """Normalize a candidate receiver at most once per expression path.

        This is an explicit type check of a constructed Value, not a second
        normalization pass or an inference of Python runtime behavior.
        """
        if isinstance(node, ast.Name):
            symbol = self._services._lookup_symbol(node.id)
            return (
                Reference(symbol)
                if symbol is not None and symbol.kind is ValueKind.INSTANCE
                else None
            )
        if isinstance(node, (ast.Call, ast.Subscript)):
            value = self._value(node)
            return value if value.kind is ValueKind.INSTANCE else None
        if isinstance(node, ast.Attribute):
            parent = self._instance_receiver(node.value)
            if parent is None or parent.instance_type is None:
                return None
            owner = self._context.classes.classes.get(parent.instance_type.name)
            if owner is None or owner.identity != parent.instance_type:
                return None
            found = owner.resolve_field(node.attr)
            if found is None or found[1].type.kind is not ValueKind.INSTANCE:
                return None
            return self._instance_field_read(node, parent)
        return None

    def _instance_field_read(self, node: ast.Attribute, receiver: Value) -> FieldRead:
        receiver, owner, field = self._services._field(node, receiver)
        if (
            self._context.names.active_function is not None
            and self._context.names.active_function.name == "__init__"
            and self._context.classes.method_owner is not None
            and self._context.classes.method_owner.is_subtype_of(owner.identity)
            and isinstance(receiver, Reference)
            and receiver.symbol.role is ParameterRole.RECEIVER
            and field.name not in self._context.classes.initialized_fields
        ):
            raise reject(node, "Read before instance field initialization")
        return FieldRead(receiver, field, owner)

    def _unshadowed_intrinsic_name(self, name: str) -> bool:
        """Only unbound direct names denote provider-defined operations.

        Existing declarations, imported mapped names and classes always take priority.
        """
        return (
            self._services._lookup_function(name) is None
            and self._services._lookup_symbol(name) is None
            and name not in self._context.names.module_aliases
            and name not in self._context.names.interface_aliases
            and name not in self._context.names.type_aliases
            and name not in self._context.names.callable_aliases
            and name not in self._context.classes.class_types
        )

    def _is_intrinsic_call(self, node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Name)
            and node.func.id in {"len", "abs", "min", "max", "sum", "any", "all"}
            and self._unshadowed_intrinsic_name(node.func.id)
        )

    def _is_declared_intrinsic_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Name):
            return self._intrinsics.has_global_name(
                node.func.id
            ) and self._unshadowed_intrinsic_name(node.func.id)
        return (
            isinstance(node.func, ast.Attribute)
            and self._intrinsics.has_method_name(node.func.attr)
            and not (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id in self._context.names.interface_objects
            )
        )

    def _declared_intrinsic_call(
        self, node: ast.Call, receiver: Value | None = None
    ) -> IntrinsicCall:
        """Match one exact typed signature, without executing source code."""
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            raise reject(node, "Intrinsic requires positional arguments only")
        receiver_type = receiver.value_type if receiver is not None else None
        if isinstance(node.func, ast.Name):
            candidates = self._intrinsics.global_candidates(node.func.id)
        else:
            assert isinstance(node.func, ast.Attribute)
            assert receiver_type is not None
            candidates = self._intrinsics.method_candidates(
                node.func.attr, receiver_type
            )
        if not candidates:
            raise reject(node, "No exact typed intrinsic signature")
        by_arity = tuple(
            candidate
            for candidate in candidates
            if len(node.args) == len(candidate.argument_types)
        )
        if not by_arity:
            raise reject(node, "Intrinsic argument arity mismatch")
        # Normalize each source operand exactly once. If there is only one
        # candidate, concrete receiver bindings provide expected types for
        # contextual literals/lambdas. Overloads never guess an expectation.
        expectations = (
            by_arity[0].expected_arguments(receiver_type)
            if len(by_arity) == 1
            else (None,) * len(node.args)
        )
        args = tuple(
            self._value(arg, expected=expected)
            for arg, expected in zip(node.args, expectations)
        )
        try:
            definition = self._intrinsics.select(
                by_arity, receiver_type, tuple(arg.value_type for arg in args)
            )
            if definition is None:
                raise reject(node, "Intrinsic argument type mismatch")
            return IntrinsicCall(definition, receiver, args)
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def _stringify(self, value: Value, node: ast.AST) -> IntrinsicCall:
        """Select an explicitly registered string conversion without execution.

        This reuses the same signature and obligations as a direct ``str(x)``.
        An alternative IntrinsicRegistry must itself provide the conversion.
        """
        try:
            definition = self._intrinsics.select(
                self._intrinsics.global_candidates("str"),
                None,
                (value.value_type,),
            )
        except ValueError as exc:
            raise reject(node, str(exc)) from exc
        if definition is None or definition.return_type != ValueType(ValueKind.STRING):
            raise reject(node, "No typed str conversion for formatted value")
        return IntrinsicCall(definition, None, (value,))

    def _intrinsic_call(self, node: ast.Call) -> Value:
        """Normalize a small, explicitly typed subset of Python built-ins."""
        assert isinstance(node.func, ast.Name)
        name = node.func.id
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            raise reject(node, f"{name} requires positional arguments only")
        if name in {"len", "abs"} and len(node.args) != 1:
            raise reject(node, f"{name} requires exactly one argument")
        if name in {"min", "max"} and len(node.args) < 2:
            raise reject(node, f"{name} requires at least two scalar arguments")
        if name == "sum" and len(node.args) not in {1, 2}:
            raise reject(node, "sum requires one iterable and optional start")
        if name in {"any", "all"} and len(node.args) != 1:
            raise reject(node, f"{name} requires exactly one iterable")
        operands = tuple(self._value(arg) for arg in node.args)
        try:
            if name == "sum":
                return IntegerSum(
                    operands[0], operands[1] if len(operands) == 2 else None
                )
            if name in {"any", "all"}:
                return BooleanAggregate(name, operands[0])
            if name == "len":
                return Length(operands[0])
            if name == "abs":
                return Absolute(operands[0])
            return Extremum(name, operands)
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def _pointer_value(self, node: ast.Call, operation: str) -> Value:
        """``Pointer.address(x)`` / ``Pointer.load(p)`` as Model values."""
        if operation == "store":
            raise reject(node, "Pointer.store is a statement, not a value")
        argument = node.args[0]
        try:
            if operation == "address":
                if not isinstance(argument, ast.Name):
                    raise reject(argument, "Pointer.address requires a variable name")
                target = self._value(argument)
                if not isinstance(target, Reference):
                    raise reject(argument, "Pointer.address requires a variable name")
                return AddressOf(target)
            return PointerLoad(self._value(argument))
        except UnsupportedPython:
            raise
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def _memory_type(self, node: ast.expr) -> ValueType:
        _, element = self._services._annotation(node)
        if element is None:
            raise reject(node, "Memory operations require a value type")
        return element

    def _memory_value(self, node: ast.Call, operation: str) -> Value:
        """``Memory.new`` / ``new_buffer`` / ``length`` / ``borrow`` as values."""
        if MEMORY_OPERATIONS[operation][1]:
            raise reject(node, f"Memory.{operation} is a statement, not a value")
        arguments = node.args
        try:
            if operation == "new":
                element = self._memory_type(arguments[0])
                return MemoryNew(element, self._value(arguments[1], element))
            if operation == "new_buffer":
                element = self._memory_type(arguments[0])
                return MemoryNewBuffer(
                    element,
                    self._value(arguments[1]),
                    self._value(arguments[2], element),
                )
            if operation == "length":
                return MemoryLength(self._value(arguments[0]))
            return MemoryBorrow(self._value(arguments[0]))
        except UnsupportedPython:
            raise
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def memory_statement(self, node: ast.Call, operation: str) -> Construct:
        """``Memory.release`` / ``resize`` / ``copy`` / ``fill`` as statements."""
        arguments = node.args
        try:
            if operation == "release":
                return MemoryRelease(self._value(arguments[0]))
            if operation == "resize":
                if not isinstance(arguments[0], ast.Name):
                    raise reject(arguments[0], "Memory.resize requires a variable name")
                target = self._value(arguments[0])
                if not isinstance(target, Reference):
                    raise reject(arguments[0], "Memory.resize requires a variable name")
                return MemoryResize(target, self._value(arguments[1]))
            if operation == "copy":
                return MemoryCopy(self._value(arguments[0]), self._value(arguments[1]))
            return MemoryFill(self._value(arguments[0]), self._value(arguments[1]))
        except UnsupportedPython:
            raise
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def pointer_store(self, node: ast.Call) -> PointerStore:
        try:
            return PointerStore(self._value(node.args[0]), self._value(node.args[1]))
        except UnsupportedPython:
            raise
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def _value(self, node: ast.expr, expected: ValueType | None = None) -> Value:
        if isinstance(node, ast.JoinedStr):
            fragments: list[Value] = []
            for part in node.values:
                if isinstance(part, ast.Constant) and type(part.value) is str:
                    fragments.append(Literal(part.value))
                elif isinstance(part, ast.FormattedValue):
                    if part.format_spec is not None or part.conversion not in (-1, 115):
                        raise reject(
                            part,
                            "Formatted value supports only default/!s without format spec",
                        )
                    value = self._value(part.value)
                    fragments.append(self._stringify(value, part))
                else:
                    raise reject(part, "Unsupported formatted string component")
            return FormattedString(tuple(fragments) if fragments else (Literal(""),))
        if isinstance(node, ast.Lambda):
            return self._services._lambda_value(node, expected)
        if isinstance(node, ast.Constant):
            if type(node.value) is bool:
                return BooleanLiteral(node.value)
            if node.value is None:
                return NoneLiteral()
        if isinstance(node, ast.IfExp):
            condition = self._value(node.test)
            if condition.kind is not ValueKind.BOOLEAN:
                raise reject(
                    node.test, "Conditional expression requires a Boolean condition"
                )
            when_true = self._value(node.body, expected)
            when_false = self._value(node.orelse, expected)
            if expected is None:
                if when_true.value_type != when_false.value_type:
                    raise reject(
                        node,
                        "Conditional expression branches need the same type or an explicit expected type",
                    )
                result_type = when_true.value_type
            else:
                result_type = expected
            try:
                return ConditionalExpression(
                    condition, when_true, when_false, result_type
                )
            except ValueError as exc:
                raise reject(node, str(exc)) from exc
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                raise reject(node, "Dictionary unpacking is unsupported")
            shape = (
                expected.dict_type
                if expected is not None and expected.kind is ValueKind.DICT
                else None
            )
            if shape is None and not node.keys:
                raise reject(node, "Empty dict needs an explicit dict type")
            entries = tuple(
                DictEntry(
                    self._value(key, shape.key_type if shape is not None else None),
                    self._value(value, shape.value_type if shape is not None else None),
                )
                for key, value in zip(node.keys, node.values)
                if key is not None
            )
            key_type = (
                shape.key_type if shape is not None else entries[0].key.value_type
            )
            value_type = (
                shape.value_type if shape is not None else entries[0].value.value_type
            )
            try:
                return DictValue(entries, key_type, value_type)
            except ValueError as exc:
                raise reject(node, str(exc)) from exc
        if isinstance(node, ast.List):
            if expected is not None and expected.kind is ValueKind.TUPLE:
                raise reject(node, "Unsupported expression")
            element_type = (
                expected.list_type.element_type
                if expected is not None
                and expected.kind is ValueKind.LIST
                and expected.list_type is not None
                else None
            )
            items = tuple(self._value(item, element_type) for item in node.elts)
            if element_type is None:
                if not items:
                    raise reject(node, "Empty list needs an explicit list type")
                element_type = items[0].value_type
            try:
                return ListValue(items, element_type)
            except ValueError as exc:
                raise reject(node, str(exc)) from exc
        if isinstance(node, ast.Tuple):
            expected_items = (
                expected.tuple_type.element_types
                if expected is not None
                and expected.kind is ValueKind.TUPLE
                and expected.tuple_type is not None
                else None
            )
            if (
                expected is not None
                and expected.tuple_type is not None
                and expected.tuple_type.variadic_element_type is not None
            ):
                return TupleValue(
                    tuple(
                        self._value(item, expected.tuple_type.variadic_element_type)
                        for item in node.elts
                    )
                )
            if expected_items is not None and len(node.elts) == len(expected_items):
                return TupleValue(
                    tuple(
                        self._value(item, declared)
                        for item, declared in zip(node.elts, expected_items)
                    )
                )
            return TupleValue(tuple(self._value(item) for item in node.elts))
        if isinstance(node, ast.Subscript):
            source = self._value(node.value)
            if isinstance(node.slice, ast.Slice):
                if source.kind not in {ValueKind.LIST, ValueKind.STRING}:
                    raise reject(node, "Slicing requires a typed list or string")
                try:
                    return SliceValue(
                        source,
                        self._value(node.slice.lower)
                        if node.slice.lower is not None
                        else None,
                        self._value(node.slice.upper)
                        if node.slice.upper is not None
                        else None,
                        self._value(node.slice.step)
                        if node.slice.step is not None
                        else None,
                    )
                except ConstructError as exc:
                    raise reject(node, str(exc)) from exc
            if source.kind is ValueKind.TUPLE:
                if not (
                    isinstance(node.slice, ast.Constant)
                    and type(node.slice.value) is int
                    and node.slice.value >= 0
                ):
                    raise reject(
                        node, "Tuple access requires a nonnegative static integer index"
                    )
                try:
                    return TupleElement(source, node.slice.value)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if source.kind is ValueKind.LIST:
                index = self._value(node.slice)
                try:
                    return ListElement(source, index)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if source.kind is ValueKind.STRING:
                try:
                    return StringElement(source, self._value(node.slice))
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if source.kind is ValueKind.DICT:
                key = self._value(node.slice)
                try:
                    return DictElement(source, key)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            raise reject(node, "Indexing requires a tuple, list or dict")
        if isinstance(node, ast.BinOp):
            operators = {
                ast.Add: "+",
                ast.Sub: "-",
                ast.Mult: "*",
                ast.Div: "/",
                ast.FloorDiv: "//",
                ast.Mod: "%",
                ast.BitAnd: "&",
                ast.BitOr: "|",
                ast.BitXor: "^",
                ast.LShift: "<<",
                ast.RShift: ">>",
            }
            operator = operators.get(type(node.op))
            if operator is None:
                raise reject(node, "Unsupported arithmetic operator")
            left, right = self._value(node.left), self._value(node.right)
            if left.kind is ValueKind.INTEGER and right.kind is ValueKind.INTEGER:
                if operator == "/":
                    return IntegerTrueDivision(left, right)
                return Arithmetic(left, operator, right)
            if left.kind is ValueKind.FLOAT and right.kind is ValueKind.FLOAT:
                if operator not in {"+", "-", "*", "/"}:
                    raise reject(node, "Unsupported floating arithmetic operator")
                return FloatingArithmetic(left, operator, right)
            if (
                left.kind is ValueKind.STRING
                and right.kind is ValueKind.STRING
                and operator == "+"
            ):
                return StringConcat(left, right)
            if operator == "*" and (left.kind, right.kind) in {
                (ValueKind.STRING, ValueKind.INTEGER),
                (ValueKind.INTEGER, ValueKind.STRING),
            }:
                return StringRepeat(left, right)
            raise reject(node, "Unsupported operand types for arithmetic")
        if isinstance(node, ast.BoolOp):
            operator = "and" if isinstance(node.op, ast.And) else "or"
            operands = tuple(self._value(value) for value in node.values)
            if any(value.kind is not ValueKind.BOOLEAN for value in operands):
                raise reject(node, "Boolean operation requires Boolean operands")
            return BooleanOperation(operator, operands)
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                operand = self._value(node.operand)
                if operand.kind is not ValueKind.BOOLEAN:
                    raise reject(node, "Boolean not requires a Boolean operand")
                return BooleanNot(operand)
            operators = {ast.UAdd: "+", ast.USub: "-", ast.Invert: "~"}
            operator = operators.get(type(node.op))
            if operator is None:
                raise reject(node, "Unsupported unary operator")
            operand = self._value(node.operand)
            if operand.kind is ValueKind.FLOAT:
                if operator == "~":
                    raise reject(node, "Bitwise complement requires an integer")
                return FloatingUnary(operator, operand)
            if operand.kind is not ValueKind.INTEGER:
                raise reject(node, "Integer unary operation requires an integer")
            # Preserve the historical signed-integer Literal representation.
            if isinstance(operand, Literal) and operator in {"+", "-"}:
                return Literal(+operand.value if operator == "+" else -operand.value)  # type: ignore[operator]
            return IntegerUnary(operator, operand)
        if isinstance(node, ast.Attribute):
            receiver = self._instance_receiver(node.value)
            if receiver is not None:
                return self._instance_field_read(node, receiver)
            definition, origin, interface_receiver = (
                self._interface_mapping_normalizer.object_receiver(node)
            )
            factory = definition.properties.get(node.attr)
            if factory is None:
                raise reject(node, "Unregistered interface mapping object property")
            try:
                result = factory(origin, interface_receiver)
            except (TypeError, ValueError) as exc:
                raise reject(
                    node, f"Invalid interface mapping property: {exc}"
                ) from exc
            if not isinstance(result, Value):
                raise reject(node, "interface mapping property must produce a Value")
            return result
        if isinstance(node, ast.Call):
            operation = pointer_operation(node, self._context.names.kind_aliases)
            if operation is not None:
                return self._pointer_value(node, operation)
            operation = memory_operation(node, self._context.names.kind_aliases)
            if operation is not None:
                return self._memory_value(node, operation)
            if self._interface_mapping_normalizer.is_module_call(node):
                return self._interface_mapping_normalizer.mapped_call(node)
            if isinstance(node.func, ast.Name):
                symbol = self._services._lookup_symbol(node.func.id)
                if symbol is not None and symbol.role is ParameterRole.CLASS_RECEIVER:
                    return self._services._class_receiver_creation(node)
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in self._context.classes.classes
            ):
                return self._services._instance_creation(node)
            if (
                isinstance(node.func, ast.Attribute)
                and self._services._class_receiver_source(node.func.value) is not None
            ):
                return self._services._class_method_call(node)
            if isinstance(node.func, ast.Attribute):
                if self._is_super_expression(node.func.value):
                    return self._services._instance_member_call(node)
                if self._intrinsics.has_method_name(node.func.attr):
                    # A Call/Subscript receiver may itself be a Value with
                    # effects or lexical captures. Do not normalize it once to
                    # test for an instance and a second time for an intrinsic.
                    typed_receiver = self._value(node.func.value)
                    if typed_receiver.kind is ValueKind.INSTANCE:
                        return self._services._instance_member_call(
                            node, typed_receiver
                        )
                    if typed_receiver.kind is ValueKind.MAPPED_OBJECT:
                        raise reject(node, "Intrinsic receiver needs a typed Value")
                    return self._declared_intrinsic_call(node, typed_receiver)
                receiver = self._instance_receiver(node.func.value)
                if receiver is not None:
                    return self._services._instance_member_call(node, receiver)
            if (
                isinstance(node.func, ast.Name)
                and self._services._lookup_function(node.func.id) is not None
            ):
                return self._services._function_call(node)
            if isinstance(node.func, ast.Name):
                callee = self._services._lookup_symbol(node.func.id)
                if callee is not None and callee.kind is ValueKind.FUNCTION:
                    return self._services._function_value_call(node, Reference(callee))
            if isinstance(node.func, (ast.Call, ast.Subscript)):
                callee_value = self._value(node.func)
                return self._services._function_value_call(node, callee_value)
            if isinstance(node.func, ast.Name) and node.func.id == "range":
                if node.keywords or not 1 <= len(node.args) <= 3:
                    raise reject(node, "range requires 1 to 3 positional arguments")
                arguments = tuple(self._value(arg) for arg in node.args)
                if any(arg.kind is not ValueKind.INTEGER for arg in arguments):
                    raise reject(node, "range arguments must be typed integers")
                return Range(arguments)
            if (
                isinstance(node.func, ast.Name)
                and self._unshadowed_intrinsic_name(node.func.id)
                and self._intrinsics.has_global_name(node.func.id)
            ):
                return self._declared_intrinsic_call(node)
            if self._is_intrinsic_call(node):
                return self._intrinsic_call(node)
            return self._interface_mapping_normalizer.mapped_call(node)
        if isinstance(node, ast.Constant) and type(node.value) is float:
            try:
                return FloatingLiteral(node.value)
            except ValueError as exc:
                raise reject(node, str(exc)) from exc
        if isinstance(node, ast.Constant) and (
            type(node.value) is str or type(node.value) is int
        ):
            return Literal(node.value)
        if isinstance(node, ast.Name):
            symbol = self._services._lookup_symbol(node.id)
            if symbol is not None and symbol.role is ParameterRole.CLASS_RECEIVER:
                raise reject(
                    node,
                    "Class receiver can only be used for class calls or construction",
                )
            if symbol is None:
                signature = self._services._lookup_function(node.id)
                if signature is not None:
                    try:
                        return Reference(signature.value_symbol)
                    except ConstructError as exc:
                        raise reject(node, str(exc)) from exc
                word = self._context.names.kind_aliases.get(node.id)
                if word in NONE_ALIASES:
                    return NoneAlias(word)
                if word is not None:
                    raise reject(node, f"Kind {word} is not a value")
                raise reject(node, f"Unresolved name: {node.id!r}")
            return Reference(symbol)
        if isinstance(node, ast.Compare):
            if len(node.ops) >= 2:
                operators = {
                    ast.Gt: ">",
                    ast.GtE: ">=",
                    ast.Lt: "<",
                    ast.LtE: "<=",
                    ast.Eq: "==",
                    ast.NotEq: "!=",
                }
                selected = tuple(operators.get(type(op)) for op in node.ops)
                if any(op is None for op in selected):
                    raise reject(node, "Unsupported chained comparison operator")
                operands = tuple(
                    self._value(expr) for expr in (node.left, *node.comparators)
                )
                try:
                    return ComparisonChain(operands, selected)  # type: ignore[arg-type]
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if isinstance(node.ops[0], (ast.In, ast.NotIn)):
                needle_value = self._value(node.left)
                haystack = self._value(node.comparators[0])
                try:
                    if haystack.kind is ValueKind.STRING:
                        return StringContains(
                            needle_value,
                            haystack,
                            isinstance(node.ops[0], ast.NotIn),
                        )
                    return Membership(
                        needle_value, haystack, isinstance(node.ops[0], ast.NotIn)
                    )
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            operators = {
                ast.Gt: ">",
                ast.GtE: ">=",
                ast.Lt: "<",
                ast.LtE: "<=",
                ast.Eq: "==",
                ast.NotEq: "!=",
            }
            operator = operators.get(type(node.ops[0]))
            if operator is None:
                raise reject(node, "Unsupported comparison operator")
            left, right = self._value(node.left), self._value(node.comparators[0])
            if is_none_alias(left.value_type) or is_none_alias(right.value_type):
                try:
                    return NoneAliasComparison(left, operator, right)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if left.kind is ValueKind.INTEGER and right.kind is ValueKind.INTEGER:
                return Comparison(left, operator, right)
            if left.kind is ValueKind.FLOAT and right.kind is ValueKind.FLOAT:
                return FloatingComparison(left, operator, right)
            if left.kind is ValueKind.STRING and right.kind is ValueKind.STRING:
                return StringComparison(left, operator, right)
            raise reject(
                node, "Comparison requires matching integer, float or string operands"
            )
        raise reject(node, "Unsupported expression")
