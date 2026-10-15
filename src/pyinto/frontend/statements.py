"""Statements normalization: explicit syntax-to-Model rules."""

from __future__ import annotations

import ast

from pyinto.constructs import (
    SUPPORTED_EXCEPTION_NAMES,
    Assign,
    AugAssign,
    Block,
    Branch,
    Break,
    Call,
    Construct,
    ContextEntry,
    Continue,
    DictElementAssign,
    ExceptHandler,
    ExpressionStatement,
    FieldInitialize,
    FieldRead,
    FieldWrite,
    For,
    Initialize,
    IterationEntry,
    ListElementAssign,
    MethodCall,
    MethodDispatch,
    ParameterRole,
    Pass,
    PrintValues,
    Raise,
    Reference,
    Return,
    Symbol,
    Try,
    UnpackAssign,
    ValueKind,
    ValueType,
    While,
    With,
)
from pyinto.constructs.control import iteration_source_shape
from pyinto.constructs.type_rules import assignable

from .context import ParseContext
from .errors import reject
from .interface_mapping import InterfaceMappingNormalizer
from .kinds import MEMORY_OPERATIONS, memory_operation, pointer_operation
from .statement_services import StatementServices


class StatementNormalizer:
    """Normalize statements with a per-parse context and explicit services."""

    def __init__(
        self,
        context: ParseContext,
        interface_mappings: InterfaceMappingNormalizer,
        services: StatementServices,
    ) -> None:
        self._context = context
        self._interface_mapping_normalizer = interface_mappings
        self._services = services

    def _block(self, body: list[ast.stmt]) -> Block:
        self._context.flow.block_depth += 1
        try:
            return Block(tuple(self._statement(statement) for statement in body))
        finally:
            self._context.flow.block_depth -= 1

    def _control_block(
        self, body: list[ast.stmt], *, introduced: str | None = None
    ) -> Block:
        """Accept local typed initializers without exporting control-body names.

        Python does not have block lexical scopes. This is an *acceptance*
        restriction: no definite-assignment analysis is attempted, while each
        accepted Initialize retains the original function/module Symbol scope.
        Existing non-interface mapping symbols remain available for ordinary writes.
        """
        names = self._context.names
        before_symbols = dict(names.symbols)
        before_mappings = dict(names.interface_objects)
        restricted = {introduced} if introduced is not None else set()
        self._context.flow.control_local_bindings.append(restricted)
        try:
            result = self._block(body)
            if names.interface_objects != before_mappings:
                raise reject(
                    body[0],
                    "interface mapping declarations or rebinding inside control blocks are unsupported",
                )
            return result
        finally:
            self._context.flow.control_local_bindings.pop()
            # Do not let a conditional/possibly empty block make new symbols
            # look definitely bound in its enclosing sequential statements.
            names.symbols = before_symbols
            names.interface_objects = before_mappings

    def _exception_name(self, node: ast.expr) -> str:
        """Resolve only unshadowed built-in exception classes in this subset."""
        if not isinstance(node, ast.Name) or node.id not in SUPPORTED_EXCEPTION_NAMES:
            raise reject(node, "Unsupported exception class")
        name = node.id
        if (
            self._services._lookup_symbol(name) is not None
            or self._services._lookup_function(name) is not None
            or (
                self._context.names.active_function is not None
                and name in self._context.names.local_names
            )
            or name in self._context.names.module_aliases
            or name in self._context.names.interface_aliases
            or name in self._context.names.type_aliases
            or name in self._context.names.callable_aliases
        ):
            raise reject(node, "Exception class name is shadowed")
        return name

    def _exception_body(self, body: list[ast.stmt]) -> Block:
        """Retain the existing control-body policy against new declarations."""
        snapshot = dict(self._context.names.symbols)
        objects = dict(self._context.names.interface_objects)
        result = self._block(body)
        if (
            self._context.names.symbols != snapshot
            or self._context.names.interface_objects != objects
        ):
            raise reject(
                body[0],
                "New bindings or interface mapping rebinding inside try are unsupported",
            )
        return result

    def _try_statement(self, node: ast.Try) -> Try:
        body = self._exception_body(node.body)
        handlers: list[ExceptHandler] = []
        for handler in node.handlers:
            if handler.name is not None or handler.type is None:
                raise reject(
                    handler, "Exception handlers require named types without as-binding"
                )
            type_nodes = (
                handler.type.elts
                if isinstance(handler.type, ast.Tuple)
                else [handler.type]
            )
            if not type_nodes:
                raise reject(handler, "Exception handler requires a type")
            names = tuple(self._exception_name(item) for item in type_nodes)
            try:
                handlers.append(
                    ExceptHandler(names, self._exception_body(handler.body))
                )
            except ValueError as exc:
                raise reject(handler, str(exc)) from exc
        else_body = self._exception_body(node.orelse) if node.orelse else None
        finally_body = self._exception_body(node.finalbody) if node.finalbody else None
        try:
            return Try(body, tuple(handlers), else_body, finally_body)
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def _raise_statement(self, node: ast.Raise) -> Raise:
        if node.cause is not None:
            raise reject(node, "Exception chaining with from is unsupported")
        call = node.exc
        if not (
            isinstance(call, ast.Call) and not call.keywords and len(call.args) <= 1
        ):
            raise reject(
                node,
                "raise requires a supported exception constructor with 0 or 1 string argument",
            )
        name = self._exception_name(call.func)
        message = self._services._value(call.args[0]) if call.args else None
        try:
            return Raise(name, message)
        except ValueError as exc:
            raise reject(node, str(exc)) from exc

    def _statement(self, node: ast.stmt) -> Construct:
        if isinstance(node, ast.Pass):
            return Pass()
        if isinstance(node, ast.ClassDef):
            return self._services._class_definition(node)
        if isinstance(node, ast.Try):
            return self._try_statement(node)
        if isinstance(node, ast.Raise):
            return self._raise_statement(node)
        if isinstance(node, ast.TryStar):
            raise reject(node, "Exception groups and except* are unsupported")
        if isinstance(node, ast.FunctionDef):
            required_depth = self._context.names.function_body_depth or 1
            if self._context.flow.block_depth != required_depth:
                raise reject(
                    node, "Function definitions in control-flow blocks are unsupported"
                )
            return self._services._function_definition(node)
        if isinstance(node, ast.Return):
            signature = self._context.names.active_function
            if signature is None:
                raise reject(node, "return requires a function")
            if signature.return_type.kind is ValueKind.NONE:
                if node.value is not None and not (
                    isinstance(node.value, ast.Constant) and node.value.value is None
                ):
                    raise reject(node, "None-returning function cannot return a value")
                return Return()
            if node.value is None:
                raise reject(node, "Return value is required")
            value = self._services._value(
                node.value,
                signature.return_type,
            )
            if signature.return_type.kind not in (ValueKind.ANY, ValueKind.OBJECT) and (
                value.kind is ValueKind.MAPPED_OBJECT
                or not assignable(signature.return_type, value.value_type)
            ):
                raise reject(node, "Return type mismatch")
            return Return(value)
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Attribute):
                if (
                    self._context.classes.method_owner is None
                    or self._context.names.active_function is None
                    or self._context.names.active_function.name != "__init__"
                ):
                    raise reject(node, "Typed instance fields require __init__")
                receiver, owner, field = self._services._field(node.target)
                if (
                    not isinstance(receiver, Reference)
                    or receiver.symbol.role is not ParameterRole.RECEIVER
                ):
                    raise reject(node, "Typed instance field requires the receiver")
                _, declared_type = self._services._annotation(node.annotation)
                if field.type != declared_type:
                    raise reject(node, "Instance field declaration type mismatch")
                if (
                    field.name in self._context.classes.initialized_fields
                    or node.value is None
                ):
                    raise reject(node, "Instance field requires one typed initializer")
                value = self._services._value(node.value, field.type)
                try:
                    result = FieldInitialize(receiver, field, owner, value)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
                self._context.classes.initialized_fields.add(field.name)
                return result
            if not isinstance(node.target, ast.Name) or node.value is None:
                raise reject(node, "Typed initialization requires a name and value")
            name = node.target.id
            if name in self._context.names.global_names:
                raise reject(node, "global name cannot be redeclared with a type")
            if (
                name in {"print", "range"}
                or name in self._context.names.type_aliases
                or name in self._context.names.callable_aliases
                or name in self._context.names.module_aliases
                or name in self._context.names.interface_aliases
                or name in self._context.names.functions
                or name in self._context.classes.class_types
            ):
                raise reject(
                    node, "Cannot shadow a built-in, function or imported mapped name"
                )
            if name in self._context.names.symbols:
                raise reject(node, "Variable already declared; use assignment")
            annotation, declared_type = self._services._annotation(node.annotation)
            declared = (
                ValueKind.MAPPED_OBJECT if declared_type is None else declared_type.kind
            )
            if declared is ValueKind.NONE:
                raise reject(node, "None is not a variable type")
            if declared is ValueKind.MAPPED_OBJECT:
                if self._context.flow.control_local_bindings:
                    raise reject(
                        node,
                        "interface mapping declaration inside control blocks is unsupported",
                    )
                if isinstance(node.value, ast.Name):
                    source_symbol = self._context.names.symbols.get(node.value.id)
                    if (
                        source_symbol is None
                        or source_symbol.kind is not ValueKind.MAPPED_OBJECT
                    ):
                        raise reject(
                            node,
                            "interface mapping alias requires a declared interface mapping instance",
                        )
                    if source_symbol.annotation != annotation:
                        raise reject(
                            node,
                            "interface mapping alias type does not match annotation",
                        )
                    symbol = Symbol(
                        name,
                        source_symbol.mapped_type,
                        annotation,
                        scope=self._services._declaration_scope(),
                    )
                    self._context.names.symbols[name] = symbol
                    self._context.names.interface_objects[name] = (
                        self._context.names.interface_objects[node.value.id]
                    )
                    return Initialize(symbol, Reference(source_symbol))
                return self._interface_mapping_normalizer.object_constructor(
                    name, annotation, node.value
                )
            assert declared_type is not None
            value = self._services._value(node.value, declared_type)
            symbol = Symbol(
                name,
                declared_type,
                annotation,
                scope=self._services._declaration_scope(),
            )
            try:
                declaration = Initialize(symbol, value)
            except ValueError as exc:
                raise reject(node, "Annotated type does not match initializer") from exc
            self._context.names.symbols[name] = symbol
            if self._context.flow.control_local_bindings:
                self._context.flow.control_local_bindings[-1].add(name)
            return declaration

        if isinstance(node, ast.AugAssign):
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
                raise reject(node, "Unsupported augmented assignment operator")
            target_node = node.target
            if isinstance(target_node, ast.Name):
                # Explicit global names resolve to the original module Symbol;
                # other name targets must resolve to a declared local binding.
                symbol = self._services._lookup_symbol(target_node.id)
                if symbol is None:
                    raise reject(node, "Augmented assignment requires a declared name")
                if symbol.role in {
                    ParameterRole.RECEIVER,
                    ParameterRole.CLASS_RECEIVER,
                }:
                    raise reject(node, "Method receiver cannot be rebound")
                target = Reference(symbol)
            elif isinstance(target_node, ast.Attribute):
                receiver = self._services._instance_receiver(target_node.value)
                if receiver is None:
                    raise reject(
                        node, "Augmented assignment requires a typed field receiver"
                    )
                receiver, owner, field = self._services._field(target_node, receiver)
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
                target = FieldRead(receiver, field, owner)
            else:
                raise reject(
                    node,
                    "Only named scalar variables and typed fields support augmented assignment",
                )
            if target.kind not in {ValueKind.INTEGER, ValueKind.FLOAT}:
                raise reject(
                    node, "Augmented assignment requires a scalar int or float target"
                )
            value = self._services._value(node.value, target.value_type)
            try:
                return AugAssign(target, operator, value)
            except ValueError as exc:
                raise reject(node, str(exc)) from exc

        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
                unpack_target = node.targets[0]
                if any(not isinstance(item, ast.Name) for item in unpack_target.elts):
                    raise reject(node, "Unpack assignment requires plain named targets")
                targets: list[Reference] = []
                for item in unpack_target.elts:
                    assert isinstance(item, ast.Name)
                    symbol = self._context.names.symbols.get(item.id)
                    if symbol is None:
                        raise reject(
                            node, "Unpack assignment requires declared targets"
                        )
                    if symbol.kind is ValueKind.MAPPED_OBJECT:
                        raise reject(
                            node, "Unpack assignment cannot rebind mapped objects"
                        )
                    if symbol.role in {
                        ParameterRole.RECEIVER,
                        ParameterRole.CLASS_RECEIVER,
                    }:
                        raise reject(node, "Method receiver cannot be rebound")
                    targets.append(Reference(symbol))
                # Normalize the RHS exactly once. Its fixed tuple shape, not
                # Python evaluation or a Target-specific projection, supplies
                # the positional element types.
                value = self._services._value(node.value)
                try:
                    return UnpackAssign(tuple(targets), value)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute):
                receiver = self._services._instance_receiver(node.targets[0].value)
            else:
                receiver = None
            if receiver is not None:
                target = node.targets[0]
                assert isinstance(target, ast.Attribute)
                receiver, owner, field = self._services._field(target, receiver)
                if (
                    self._context.names.active_function is not None
                    and self._context.names.active_function.name == "__init__"
                    and self._context.classes.method_owner is not None
                    and self._context.classes.method_owner.is_subtype_of(owner.identity)
                    and isinstance(receiver, Reference)
                    and receiver.symbol.role is ParameterRole.RECEIVER
                    and field.name not in self._context.classes.initialized_fields
                ):
                    raise reject(
                        node,
                        "Instance fields require a typed initialization before assignment",
                    )
                value = self._services._value(node.value, field.type)
                try:
                    return FieldWrite(receiver, field, owner, value)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript):
                target = node.targets[0]
                if not isinstance(target.value, ast.Name):
                    raise reject(
                        target, "Collection mutation requires a direct variable"
                    )
                symbol = self._services._lookup_symbol(target.value.id)
                if symbol is None or symbol.kind not in (
                    ValueKind.LIST,
                    ValueKind.DICT,
                ):
                    raise reject(node, "Only simple name assignments are supported")
                index = self._services._value(target.slice)
                if symbol.kind is ValueKind.DICT:
                    assert symbol.dict_type is not None
                    value = self._services._value(
                        node.value, symbol.dict_type.value_type
                    )
                    try:
                        return DictElementAssign(Reference(symbol), index, value)
                    except ValueError as exc:
                        raise reject(node, str(exc)) from exc
                assert symbol.list_type is not None
                value = self._services._value(node.value, symbol.list_type.element_type)
                try:
                    return ListElementAssign(Reference(symbol), index, value)
                except ValueError as exc:
                    raise reject(node, str(exc)) from exc
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise reject(node, "Only simple name assignments are supported")
            name = node.targets[0].id
            if name in self._context.names.global_names:
                symbol = self._services._lookup_symbol(name)
                if symbol is None:
                    raise reject(node, "Unresolved typed global variable")
            else:
                symbol = self._context.names.symbols.get(name)
                if symbol is None:
                    raise reject(
                        node, "Variable definition requires an explicit type annotation"
                    )
            if symbol.role in {ParameterRole.RECEIVER, ParameterRole.CLASS_RECEIVER}:
                raise reject(node, "Method receiver cannot be rebound")
            assert symbol.kind is not None
            value = self._services._value(
                node.value,
                ValueType(
                    symbol.kind,
                    symbol.callable_type,
                    symbol.tuple_type,
                    symbol.list_type,
                    symbol.dict_type,
                    symbol.instance_type,
                )
                if symbol.kind is not ValueKind.MAPPED_OBJECT
                else None,
            )
            if symbol.kind not in (ValueKind.ANY, ValueKind.OBJECT) and (
                symbol.kind is not value.kind
                or (
                    symbol.kind is ValueKind.FUNCTION
                    and symbol.callable_type != value.callable_type
                )
                or (
                    symbol.kind is ValueKind.TUPLE
                    and symbol.tuple_type != value.tuple_type
                )
                or (
                    symbol.kind is ValueKind.LIST
                    and symbol.list_type != value.list_type
                )
                or (
                    symbol.kind is ValueKind.DICT
                    and symbol.dict_type != value.dict_type
                )
                or (
                    symbol.kind is ValueKind.INSTANCE
                    and (
                        symbol.instance_type is None
                        or value.instance_type is None
                        or not value.instance_type.is_subtype_of(symbol.instance_type)
                    )
                )
            ):
                raise reject(node, "Variable type cannot change")
            if symbol.kind is ValueKind.MAPPED_OBJECT:
                if (
                    not isinstance(value, Reference)
                    or value.symbol.mapped_type != symbol.mapped_type
                ):
                    raise reject(
                        node,
                        "interface mapping rebinding requires the same declared representation",
                    )
                self._context.names.interface_objects[name] = (
                    self._context.names.interface_objects[value.symbol.name]
                )
            return Assign(Reference(symbol), value)

        if isinstance(node, ast.If):
            condition = self._services._value(node.test)
            if condition.kind is not ValueKind.BOOLEAN:
                raise reject(node, "If requires a supported Boolean comparison")
            then_body = self._control_block(node.body)
            else_body = self._control_block(node.orelse) if node.orelse else None
            return Branch(condition, then_body, else_body)

        if isinstance(node, ast.Break):
            if self._context.flow.loop_depth == 0:
                raise reject(node, "break requires an enclosing loop")
            return Break()

        if isinstance(node, ast.Continue):
            if self._context.flow.loop_depth == 0:
                raise reject(node, "continue requires an enclosing loop")
            return Continue()

        if isinstance(node, ast.While):
            condition = self._services._value(node.test)
            if condition.kind is not ValueKind.BOOLEAN:
                raise reject(node, "While requires a supported Boolean condition")
            self._context.flow.loop_depth += 1
            try:
                body = self._control_block(node.body)
            finally:
                self._context.flow.loop_depth -= 1
            else_body = self._control_block(node.orelse) if node.orelse else None
            return While(condition, body, else_body)

        if isinstance(node, ast.For):
            if not isinstance(node.target, ast.Name):
                raise reject(node, "For requires a single iteration name")
            name = node.target.id
            # The iterable is evaluated in the *enclosing* binding environment.
            # A fresh target is not visible to its own source expression.
            source = self._services._value(node.iter)
            source_kind, element_types = iteration_source_shape(source)
            if element_types is None:
                raise reject(
                    node.iter,
                    f"Unsupported for iteration source: {source_kind}",
                )
            symbol = self._context.names.symbols.get(name)
            introduced = symbol is None
            if name in self._context.names.global_names:
                raise reject(node, "global for-target rebinding is unsupported")
            if introduced:
                if not element_types or any(
                    item != element_types[0] for item in element_types
                ):
                    raise reject(
                        node, "For introduction requires one known element type"
                    )
                if (
                    name in {"print", "range"}
                    or name in self._context.names.type_aliases
                    or name in self._context.names.callable_aliases
                    or name in self._context.names.module_aliases
                    or name in self._context.names.interface_aliases
                    or name in self._context.names.functions
                    or name in self._context.classes.class_types
                ):
                    raise reject(node, "For target conflicts with a reserved name")
                symbol = Symbol(
                    name,
                    element_types[0],
                    element_types[0].annotation(),
                    scope=self._services._declaration_scope(),
                )
            assert symbol is not None
            if any(not assignable(symbol.value_type, item) for item in element_types):
                raise reject(node, "For target type mismatch with iteration element")
            entry = IterationEntry(Reference(symbol), source, introduced)
            if introduced:
                # The body may read this binding, but it is not definitely
                # initialized outside the loop (including its else suite).
                self._context.names.symbols[name] = symbol
            self._context.flow.loop_depth += 1
            try:
                body = self._control_block(
                    node.body, introduced=name if introduced else None
                )
            finally:
                self._context.flow.loop_depth -= 1
                if introduced:
                    self._context.names.symbols.pop(name, None)
            else_body = self._control_block(node.orelse) if node.orelse else None
            return For(entry, body, else_body)

        if isinstance(node, ast.With):
            entries: list[ContextEntry] = []
            for item in node.items:
                context = self._services._value(item.context_expr)
                target = None
                if item.optional_vars is not None:
                    if not isinstance(item.optional_vars, ast.Name):
                        raise reject(
                            item.optional_vars, "With target must be a typed name"
                        )
                    symbol = self._context.names.symbols.get(item.optional_vars.id)
                    if symbol is None:
                        raise reject(
                            item,
                            "With target requires an explicit prior type declaration",
                        )
                    target = Reference(symbol)
                entries.append(ContextEntry(context, target))
            body = self._control_block(node.body)
            return With(tuple(entries), body)

        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            memory = memory_operation(call, self._context.names.kind_aliases)
            if memory is not None and MEMORY_OPERATIONS[memory][1]:
                return self._services._memory_statement(call, memory)
            if memory is not None:
                return ExpressionStatement(self._services._value(call))
            operation = pointer_operation(call, self._context.names.kind_aliases)
            if operation == "store":
                return self._services._pointer_store(call)
            if operation is not None:
                return ExpressionStatement(self._services._value(call))
            if self._interface_mapping_normalizer.is_module_call(call):
                return ExpressionStatement(
                    self._interface_mapping_normalizer.mapped_call(call)
                )
            if isinstance(call.func, ast.Name) and call.func.id == "print":
                if call.keywords or any(
                    isinstance(arg, ast.Starred) for arg in call.args
                ):
                    raise reject(call, "print supports positional arguments only")
                # Preserve the existing one-string Call path and its Pack recipes.
                # Expanded prints use a distinct Model node and admission check;
                # they are not silently sent to an old single-arg recipe.
                values = tuple(self._services._value(arg) for arg in call.args)
                if len(values) == 1 and values[0].kind is ValueKind.STRING:
                    return Call(Symbol("print", None), values)
                return PrintValues(
                    tuple(
                        self._services._stringify(value, source)
                        for value, source in zip(values, call.args)
                    )
                )
            if isinstance(call.func, ast.Attribute):
                if self._services._class_receiver_source(call.func.value) is not None:
                    return ExpressionStatement(self._services._class_method_call(call))
                is_super = self._services._is_super_expression(call.func.value)
                receiver = (
                    None
                    if is_super
                    else self._services._instance_receiver(call.func.value)
                )
                if is_super or receiver is not None:
                    result = self._services._instance_member_call(call, receiver)
                    if (
                        isinstance(result, MethodCall)
                        and result.dispatch is MethodDispatch.SUPER
                        and result.signature.name == "__init__"
                    ):
                        if (
                            self._context.names.active_function is None
                            or self._context.names.active_function.name != "__init__"
                        ):
                            raise reject(
                                call, "super().__init__ only allowed in constructor"
                            )
                        base = result.lookup_start
                        assert base is not None
                        self._context.classes.initialized_fields.update(
                            self._services._inherited_field_names(base)
                        )
                    return ExpressionStatement(result)
                if self._services._is_declared_intrinsic_call(call):
                    return ExpressionStatement(self._services._value(call))
                return self._interface_mapping_normalizer.object_method(call)
            if (
                isinstance(call.func, ast.Name)
                and call.func.id in self._context.classes.classes
            ):
                return ExpressionStatement(self._services._instance_creation(call))
            if isinstance(call.func, ast.Name):
                symbol = self._services._lookup_symbol(call.func.id)
                if symbol is not None and symbol.role is ParameterRole.CLASS_RECEIVER:
                    return ExpressionStatement(
                        self._services._class_receiver_creation(call)
                    )
            if (
                isinstance(call.func, ast.Name)
                and self._services._lookup_function(call.func.id) is not None
            ):
                return ExpressionStatement(self._services._function_call(call))
            if isinstance(call.func, ast.Name):
                callee = self._services._lookup_symbol(call.func.id)
                if callee is not None and callee.kind is ValueKind.FUNCTION:
                    return ExpressionStatement(
                        self._services._function_value_call(call, Reference(callee))
                    )
            if isinstance(call.func, (ast.Call, ast.Subscript)):
                callee_value = self._services._value(call.func)
                return ExpressionStatement(
                    self._services._function_value_call(call, callee_value)
                )
            if self._services._is_declared_intrinsic_call(call):
                return ExpressionStatement(self._services._value(call))
            if self._services._is_intrinsic_call(call):
                return ExpressionStatement(self._services._intrinsic_call(call))
            return ExpressionStatement(
                self._interface_mapping_normalizer.mapped_call(call)
            )
        raise reject(node, "Unsupported statement")
