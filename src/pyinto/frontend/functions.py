"""Per-parse function, lambda, and lexical name normalization.

The normalizer owns its function-domain operations and uses a small typed
service surface for annotation, class receiver, body, and value normalization.
"""

from __future__ import annotations

import ast
from typing import Protocol

from pyinto.constructs import (
    Block,
    BooleanLiteral,
    FloatingLiteral,
    FunctionCall,
    FunctionDefinition,
    FunctionSignature,
    FunctionValueCall,
    LambdaValue,
    Literal,
    MethodKind,
    NoneLiteral,
    ParameterRole,
    Return,
    Symbol,
    TupleType,
    Value,
    ValueKind,
    ValueType,
)
from pyinto.constructs.type_rules import assignable

from .context import ParseContext
from .decorators import DecoratorRegistry
from .decorators import FunctionNormalizer as FunctionDecoratorNormalizer
from .docstrings import split_docstring
from .errors import reject


class FunctionServices(Protocol):
    """Only the cross-domain operations used by function normalization."""

    def _annotation(self, node: ast.expr) -> tuple[str, ValueType | None]: ...

    def _method_kind(self, node: ast.FunctionDef) -> MethodKind: ...

    def _block(self, body: list[ast.stmt]) -> Block: ...

    def _value(self, node: ast.expr, expected: ValueType | None = None) -> Value: ...


class FunctionNormalizer:
    """Normalize typed functions without inheriting the frontend parser."""

    def __init__(
        self,
        context: ParseContext,
        decorators: DecoratorRegistry,
        services: FunctionServices,
    ) -> None:
        self._context = context
        self._decorators = decorators
        self._services = services

    _reject = staticmethod(reject)

    def _function_decorator_normalizer(
        self, node: ast.FunctionDef
    ) -> FunctionDecoratorNormalizer | None:
        if not node.decorator_list:
            return None
        if len(node.decorator_list) != 1 or not isinstance(
            node.decorator_list[0], ast.Name
        ):
            raise self._reject(
                node, "Only one registered function decorator is supported"
            )
        rule = self._decorators.lookup(
            node.decorator_list[0].id,
            target="function",
            shadowed=(
                set(self._context.names.symbols)
                | (set(self._context.names.functions) - {node.name})
                | set(self._context.classes.class_types)
                | set(self._context.names.interface_aliases)
                | set(self._context.names.module_aliases)
            ),
        )
        if rule is None:
            raise self._reject(
                node,
                "Function requires simple typed parameters and return: unknown decorator",
            )
        try:
            return self._decorators.require_function_normalizer(rule)
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc

    def _scalar_parameter_default(self, node: ast.expr, symbol: Symbol) -> Value:
        """Accept inert scalar constants only, without evaluating user code."""
        literal: Value
        if isinstance(node, ast.Constant):
            value = node.value
            if value is None:
                literal = NoneLiteral()
            elif type(value) is bool:
                literal = BooleanLiteral(value)
            elif type(value) is int or type(value) is str:
                literal = Literal(value)
            elif type(value) is float:
                try:
                    literal = FloatingLiteral(value)
                except ValueError as exc:
                    raise self._reject(node, str(exc)) from exc
            else:
                raise self._reject(node, "Unsupported default argument literal")
        elif (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, (ast.UAdd, ast.USub))
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) in (int, float)
        ):
            value = node.operand.value
            assert isinstance(value, (int, float)) and type(value) in (int, float)
            signed = value if isinstance(node.op, ast.UAdd) else -value
            try:
                literal = (
                    Literal(signed) if type(signed) is int else FloatingLiteral(signed)
                )
            except ValueError as exc:
                raise self._reject(node, str(exc)) from exc
        else:
            raise self._reject(
                node, "Only immutable scalar literal default arguments are supported"
            )
        if not self._default_type_compatible(symbol, literal):
            raise self._reject(node, "Function default argument type mismatch")
        return literal

    @staticmethod
    def _default_type_compatible(symbol: Symbol, value: Value) -> bool:
        return assignable(symbol.value_type, value.value_type)

    def _collect_functions(self, statements: list[ast.stmt]) -> None:
        """Predeclare signatures of *this* block's immediate functions only."""
        for statement in statements:
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(statement, ast.AsyncFunctionDef):
                raise self._reject(statement, "Async functions are unsupported")
            name = statement.name
            if (
                name in self._context.names.functions
                or name in {"print", "range"}
                or name in self._context.names.type_aliases
                or name in self._context.names.callable_aliases
                or name in self._context.names.module_aliases
                or name in self._context.names.interface_aliases
                or name in self._decorators.imported_names
                or (
                    not self._context.classes.collecting_methods
                    and name in self._context.classes.class_types
                )
            ):
                raise self._reject(statement, "Duplicate or reserved function name")
            args = statement.args
            if not self._context.classes.collecting_methods:
                self._function_decorator_normalizer(statement)
            if (
                getattr(statement, "type_params", ())
                or args.posonlyargs
                or args.kwonlyargs
                or args.kwarg is not None
                or any(default is not None for default in args.kw_defaults)
                or statement.returns is None
            ):
                raise self._reject(
                    statement, "Function requires simple typed parameters and return"
                )
            # A variadic parameter is a runtime tuple, not a Frontend-only
            # expansion into a fixed tuple. Methods/nested functions are not
            # admitted in this first scope of self-defined *args support.
            if args.vararg is not None and (
                self._context.classes.collecting_methods or self._declaration_scope()
            ):
                raise self._reject(
                    args.vararg, "Variadic parameters require a top-level function"
                )
            parameters: list[Symbol] = []
            method_kind = (
                self._services._method_kind(statement)
                if self._context.classes.collecting_methods
                else None
            )
            if self._context.classes.collecting_methods:
                if method_kind is not MethodKind.STATIC and (
                    not args.args or args.args[0].annotation is not None
                ):
                    raise self._reject(
                        statement,
                        "Method receiver must be an unannotated first argument",
                    )
                if method_kind is MethodKind.STATIC and not args.args and args.defaults:
                    raise self._reject(statement, "Invalid static method defaults")
                if name == "__init__" and method_kind is not MethodKind.INSTANCE:
                    raise self._reject(
                        statement,
                        "Function requires simple typed parameters and return",
                    )
                if name.startswith("__") and name.endswith("__") and name != "__init__":
                    raise self._reject(
                        statement, "Only __init__ is a supported special method"
                    )
            for index, arg in enumerate(args.args):
                is_receiver = (
                    self._context.classes.collecting_methods
                    and method_kind is not MethodKind.STATIC
                    and index == 0
                )
                if is_receiver:
                    assert self._context.classes.active_class_type is not None
                    annotation = self._context.classes.active_class_type.annotation()
                    value_type = (
                        ValueType(ValueKind.OBJECT)
                        if method_kind is MethodKind.CLASS
                        else ValueType(
                            ValueKind.INSTANCE,
                            instance_type=self._context.classes.active_class_type,
                        )
                    )
                else:
                    if arg.annotation is None:
                        raise self._reject(arg, "Function parameter needs annotation")
                    annotation, value_type = self._services._annotation(arg.annotation)
                if value_type is None:
                    raise self._reject(
                        arg, "interface mapping parameter shape is not yet supported"
                    )
                if value_type.kind is ValueKind.NONE:
                    raise self._reject(arg, "None is not a parameter type")
                owner = (*self._declaration_scope(), name)
                parameters.append(
                    Symbol(
                        arg.arg,
                        value_type,
                        annotation,
                        scope=owner,
                        role=ParameterRole.CLASS_RECEIVER
                        if is_receiver and method_kind is MethodKind.CLASS
                        else ParameterRole.RECEIVER
                        if is_receiver
                        else ParameterRole.ORDINARY,
                    )
                )
            vararg_symbol: Symbol | None = None
            if args.vararg is not None:
                arg = args.vararg
                if arg.annotation is None:
                    raise self._reject(
                        arg, "Variadic parameter needs an element annotation"
                    )
                _, element_type = self._services._annotation(arg.annotation)
                if element_type is None or element_type.kind in {
                    ValueKind.NONE,
                    ValueKind.MAPPED_OBJECT,
                }:
                    raise self._reject(
                        arg, "Unsupported variadic parameter element type"
                    )
                try:
                    shape = ValueType(
                        ValueKind.TUPLE,
                        tuple_type=TupleType(variadic_element_type=element_type),
                    )
                    vararg_symbol = Symbol(
                        arg.arg,
                        shape,
                        shape.annotation(),
                        scope=(*self._declaration_scope(), name),
                        role=ParameterRole.VARIADIC,
                    )
                except ValueError as exc:
                    raise self._reject(arg, str(exc)) from exc
            annotation, return_type = self._services._annotation(statement.returns)
            if return_type is None:
                raise self._reject(
                    statement, "interface mapping return shape is not yet supported"
                )
            # Python's positional defaults belong to the last N parameters.
            # Receiver has no default. Each accepted value is an inert literal;
            # mutable defaults and definition-time expressions are rejected.
            if len(args.defaults) > len(parameters) - int(
                self._context.classes.collecting_methods
                and method_kind is not MethodKind.STATIC
            ):
                raise self._reject(statement, "Method receiver cannot have a default")
            defaults: list[Value | None] = [None] * len(parameters)
            for index, default_node in enumerate(
                args.defaults, start=len(parameters) - len(args.defaults)
            ):
                defaults[index] = self._scalar_parameter_default(
                    default_node, parameters[index]
                )
            try:
                signature = FunctionSignature(
                    name,
                    tuple(parameters),
                    annotation,
                    return_type,
                    scope=self._declaration_scope(),
                    parameter_defaults=tuple(defaults) if args.defaults else (),
                    method_kind=method_kind,
                    variadic_parameter=vararg_symbol,
                )
            except ValueError as exc:
                raise self._reject(statement, str(exc)) from exc
            if any(
                parameter.name == signature.name
                or parameter.name in {"print", "range"}
                or parameter.name in self._context.names.functions
                or parameter.name in self._context.names.module_aliases
                or parameter.name in self._context.names.interface_aliases
                or parameter.name in self._context.names.type_aliases
                or parameter.name in self._context.names.callable_aliases
                or (
                    parameter.role is not ParameterRole.RECEIVER
                    and parameter.name in self._context.classes.class_types
                )
                for parameter in (
                    *signature.parameters,
                    *(
                        ()
                        if signature.variadic_parameter is None
                        else (signature.variadic_parameter,)
                    ),
                )
            ):
                raise self._reject(statement, "Reserved function parameter name")
            self._context.names.functions[name] = signature

    def _declaration_scope(self) -> tuple[str, ...]:
        """Lexical path of the block declaring a function or variable."""
        active = self._context.names.active_function
        if active is not None:
            return (*active.scope, active.name)
        if (
            self._context.classes.collecting_methods
            and self._context.classes.active_class_type is not None
        ):
            return (self._context.classes.active_class_type.name,)
        return ()

    @staticmethod
    def _function_locals(node: ast.FunctionDef) -> set[str]:
        """Reserve function-local names without traversing nested functions.

        This reservation prevents reads before a typed local declaration from
        silently resolving to an identically named enclosing binding.
        """
        names: set[str] = set()

        class Collect(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                names.add(node.name)
                # A nested function is an opaque lexical scope here.

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                names.add(node.name)

            def visit_Lambda(self, node: ast.Lambda) -> None:
                pass

            def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                if isinstance(node.target, ast.Name):
                    names.add(node.target.id)
                self.generic_visit(node)

            def visit_Assign(self, node: ast.Assign) -> None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
                self.generic_visit(node)

            def visit_AugAssign(self, node: ast.AugAssign) -> None:
                # Augmented assignment also binds a name in Python's lexical
                # scope, even though it reads that binding before writing it.
                if isinstance(node.target, ast.Name):
                    names.add(node.target.id)
                self.generic_visit(node)

            def visit_For(self, node: ast.For) -> None:
                if isinstance(node.target, ast.Name):
                    names.add(node.target.id)
                self.generic_visit(node)

            def visit_With(self, node: ast.With) -> None:
                for item in node.items:
                    if isinstance(item.optional_vars, ast.Name):
                        names.add(item.optional_vars.id)
                self.generic_visit(node)

        visitor = Collect()
        for statement in node.body:
            visitor.visit(statement)
        return names

    def _leading_globals(
        self,
        node: ast.FunctionDef,
        signature: FunctionSignature,
        body: list[ast.stmt],
    ) -> tuple[set[str], list[ast.stmt]]:
        """Admit only leading, explicit bindings to earlier typed module names.

        ``global`` is a lexical directive, never a runtime Construct. Restrict
        its placement to the initial suite prefix (after an optional docstring)
        rather than attempting Python's full function-wide directive grammar.
        """
        names: set[str] = set()
        index = 0
        while index < len(body) and isinstance(body[index], ast.Global):
            declaration = body[index]
            assert isinstance(declaration, ast.Global)
            if signature.scope or signature.method_kind is not None:
                raise self._reject(
                    declaration, "global is supported only in top-level functions"
                )
            for name in declaration.names:
                if name in names:
                    raise self._reject(declaration, "Duplicate global declaration")
                if any(parameter.name == name for parameter in signature.parameters):
                    raise self._reject(
                        declaration, "global cannot declare a function parameter"
                    )
                symbol = self._context.names.symbols.get(name)
                if (
                    symbol is None
                    or symbol.scope != ()
                    or not isinstance(symbol.type, ValueType)
                ):
                    raise self._reject(
                        declaration,
                        "global requires an earlier typed module variable: " + name,
                    )
                names.add(name)
            index += 1

        class RejectMisplacedGlobal(ast.NodeVisitor):
            def visit_Global(self, node: ast.Global) -> None:
                raise reject(node, "global must be a leading function directive")

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                # A nested definition has its own binding directives.
                pass

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                pass

        for statement in body[index:]:
            RejectMisplacedGlobal().visit(statement)
        return names, body[index:]

    def _lookup_symbol(self, name: str) -> Symbol | None:
        """Resolve a name from its nearest lexical declaration frame."""
        if name in self._context.names.global_names:
            # The first saved frame is the module, not an enclosing function.
            # Never resolve a global directive against a closure/local binding.
            module_symbols = self._context.names.enclosing_scopes[0][0]
            symbol = module_symbols.get(name)
            return symbol if symbol is not None and symbol.scope == () else None
        if name in self._context.names.functions:
            return None  # Function names are not first-class Values yet.
        if (
            self._context.names.active_function is None
            or name in self._context.names.local_names
        ):
            return self._context.names.symbols.get(name)
        for symbols, local_names, functions in reversed(
            self._context.names.enclosing_scopes
        ):
            if name in functions:
                return None
            if name in local_names:
                return symbols.get(name)
            if not local_names:  # Module: only declarations already visited.
                return symbols.get(name)
        return None

    def _lookup_function(self, name: str) -> FunctionSignature | None:
        """A local value declaration shadows callable names in outer scopes."""
        current = self._context.names.functions.get(name)
        if current is not None:
            return current
        if (
            self._context.names.active_function is not None
            and name in self._context.names.local_names
        ):
            return None
        for _, local_names, functions in reversed(self._context.names.enclosing_scopes):
            signature = functions.get(name)
            if signature is not None:
                return signature
            if name in local_names:
                return None
        return None

    def _function_definition(self, node: ast.FunctionDef) -> FunctionDefinition:
        signature = self._context.names.functions[node.name]
        # Class namespaces do not participate in unqualified lexical name
        # resolution within methods; only module functions are visible.
        lexical_functions = (
            self._context.classes.class_module_functions
            if signature.method_kind is not None or signature.receiver is not None
            else None
        )
        method_owner = (
            self._context.classes.active_class_type
            if signature.method_kind in {MethodKind.CLASS, MethodKind.STATIC}
            else signature.receiver.instance_type
            if signature.receiver is not None
            else None
        )
        docstring, executable = split_docstring(node.body)
        global_names, executable = self._leading_globals(node, signature, executable)
        with self._context.callable_scope(
            signature,
            local_names=self._function_locals(node) - global_names,
            global_names=global_names,
            function_body_depth=self._context.flow.block_depth + 1,
            enclosing_functions=lexical_functions,
            method_owner=method_owner,
            reset_method_state=True,
        ):
            # All immediate nested signatures are known before parsing bodies.
            self._collect_functions(node.body)
            for name in self._context.names.functions:
                if name in global_names:
                    raise self._reject(
                        node, "global cannot bind a nested function name: " + name
                    )
                if name in self._context.names.symbols:
                    raise self._reject(
                        node, f"Function name conflicts with a parameter: {name!r}"
                    )
            definition = FunctionDefinition(
                signature, self._services._block(executable), docstring
            )
            if signature.method_kind is None and node.decorator_list:
                normalizer = self._function_decorator_normalizer(node)
                assert normalizer is not None
                definition = normalizer(node, definition)
                if (
                    not isinstance(definition, FunctionDefinition)
                    or definition.signature != signature
                ):
                    raise self._reject(
                        node,
                        "Function decorator must preserve the declared function signature",
                    )
            return definition

    def _declared_call_arguments(
        self,
        node: ast.Call,
        parameters: tuple[Symbol, ...],
        defaults: tuple[Value | None, ...] = (),
        variadic: Symbol | None = None,
    ) -> tuple[tuple[Value, ...], tuple[int, ...], tuple[int, ...]]:
        """Bind static parameter names, without executing or reordering expressions.

        `arguments` are retained in declaration order for existing call slots.
        The permutation records the *source* evaluation order for Realization.
        """
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            raise self._reject(node, "Expanded call arguments are unsupported")
        if len(node.args) > len(parameters) and variadic is None:
            raise self._reject(
                node, "Function argument count mismatch: too many positional arguments"
            )
        bindings: list[tuple[int, ast.expr]] = []
        taken: set[int] = set()
        indexes = {parameter.name: i for i, parameter in enumerate(parameters)}
        for index, value in enumerate(node.args):
            bindings.append((index, value))
            if index < len(parameters):
                taken.add(index)
        for keyword in node.keywords:
            if keyword.arg is None:
                raise self._reject(
                    keyword, "Expanded keyword arguments are unsupported"
                )
            if keyword.arg not in indexes:
                raise self._reject(keyword, "Unknown keyword argument: " + keyword.arg)
            index = indexes[keyword.arg]
            if index in taken:
                raise self._reject(keyword, "Duplicate argument: " + keyword.arg)
            taken.add(index)
            bindings.append((index, keyword.value))
        declared_defaults = defaults or (None,) * len(parameters)
        if len(declared_defaults) != len(parameters):
            raise self._reject(node, "Function defaults do not match signature")
        missing = tuple(i for i in range(len(parameters)) if i not in taken)
        if any(declared_defaults[i] is None for i in missing):
            if not node.keywords:
                raise self._reject(node, "Function argument count mismatch")
            raise self._reject(node, "Missing required call argument")
        # Structural normalization proceeds in source expression order. The
        # completed argument tuple is still indexed by the declaration order.
        element_type = None
        if variadic is not None:
            shape = variadic.value_type.tuple_type
            assert shape is not None and shape.variadic_element_type is not None
            element_type = shape.variadic_element_type
        resolved = {
            index: self._services._value(
                expression,
                parameters[index].value_type
                if index < len(parameters)
                else element_type,
            )
            for index, expression in bindings
        }
        order = tuple(index for index, _ in bindings) + missing
        complete: list[Value] = []
        for i in range(len(parameters)):
            if i in resolved:
                complete.append(resolved[i])
            else:
                default = declared_defaults[i]
                assert default is not None  # Missing required arguments rejected.
                complete.append(default)
        # Keep each variadic operand as an individual Value, never a fabricated
        # fixed-length tuple or a prematurely evaluated Python argument tuple.
        complete.extend(resolved[i] for i in range(len(parameters), len(node.args)))
        return (
            tuple(complete),
            () if order == tuple(range(len(complete))) else order,
            missing,
        )

    def _function_call(self, node: ast.Call) -> FunctionCall:
        assert isinstance(node.func, ast.Name)
        signature = self._lookup_function(node.func.id)
        assert signature is not None
        arguments, evaluation, omitted = self._declared_call_arguments(
            node,
            signature.parameters,
            signature.defaults_by_parameter,
            signature.variadic_parameter,
        )
        try:
            return FunctionCall(signature, arguments, evaluation, omitted)
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc

    def _function_value_call(self, node: ast.Call, callee: Value) -> FunctionValueCall:
        """Normalize a statically typed value call without choosing its target."""
        if node.keywords:
            raise self._reject(
                node, "Function value calls accept positional arguments only"
            )
        shape = callee.callable_type
        arguments = (
            tuple(
                self._services._value(arg, expected)
                for arg, expected in zip(node.args, shape.parameter_types)
            )
            if shape is not None and len(node.args) == len(shape.parameter_types)
            else tuple(self._services._value(arg) for arg in node.args)
        )
        try:
            return FunctionValueCall(callee, arguments)
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc

    def _lambda_value(
        self, node: ast.Lambda, expected: ValueType | None
    ) -> LambdaValue:
        """Normalize an expression-scoped anonymous function under explicit type.

        Lambda parameters have no Python annotations. Only an explicitly
        provided Callable shape can bind their types and the result type;
        source/outer values are never executed to infer them.
        """
        if expected is None or expected.kind is not ValueKind.FUNCTION:
            raise self._reject(
                node, "Lambda requires an explicit Callable expected type"
            )
        shape = expected.callable_type
        assert shape is not None
        args = node.args
        if (
            args.posonlyargs
            or args.kwonlyargs
            or args.vararg is not None
            or args.kwarg is not None
            or args.defaults
            or any(default is not None for default in args.kw_defaults)
            or len(args.args) != len(shape.parameter_types)
            or any(arg.annotation is not None for arg in args.args)
        ):
            raise self._reject(
                node, "Lambda requires simple positional parameters matching Callable"
            )
        names = [arg.arg for arg in args.args]
        # Control-local bindings can be read within their enclosing body but
        # cannot escape indirectly through a lambda. That would require
        # cross-block lifetime/definite-binding semantics not admitted here.
        restricted = set().union(*self._context.flow.control_local_bindings)
        if restricted.difference(names) & {
            item.id
            for item in ast.walk(node.body)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
        }:
            raise self._reject(
                node, "Lambda capture of a control-local binding is unsupported"
            )
        if len(names) != len(set(names)):
            raise self._reject(node, "Duplicate lambda parameter")
        self._context.flow.lambda_counter += 1
        # A generated name identifies this lexical expression only; it is not
        # resolved as a Python name. Avoid collisions with user declarations.
        name = f"__henkan_lambda_{self._context.flow.lambda_counter}"
        reserved = (
            self._context.names.source_names
            | set(self._context.names.symbols)
            | self._context.names.local_names
            | set(self._context.names.functions)
        )
        for symbols, local_names, functions in self._context.names.enclosing_scopes:
            reserved.update(symbols)
            reserved.update(local_names)
            reserved.update(functions)
        while name in reserved:
            self._context.flow.lambda_counter += 1
            name = f"__henkan_lambda_{self._context.flow.lambda_counter}"
        scope = self._declaration_scope()
        owner = (*scope, name)
        parameters = tuple(
            Symbol(
                arg.arg,
                declared,
                declared.annotation(),
                scope=owner,
            )
            for arg, declared in zip(args.args, shape.parameter_types)
        )
        try:
            signature = FunctionSignature(
                name,
                parameters,
                shape.return_type.annotation(),
                shape.return_type,
                scope=scope,
            )
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc
        with self._context.callable_scope(
            signature,
            local_names=set(),
            function_body_depth=None,
        ):
            body_value = self._services._value(node.body, shape.return_type)
            if shape.return_type.kind is ValueKind.NONE:
                if not isinstance(body_value, NoneLiteral):
                    raise self._reject(
                        node.body, "None-returning lambda must yield None"
                    )
            elif shape.return_type.kind not in {ValueKind.ANY, ValueKind.OBJECT} and (
                body_value.kind is ValueKind.MAPPED_OBJECT
                or not assignable(shape.return_type, body_value.value_type)
            ):
                raise self._reject(
                    node.body, "Lambda body type does not match Callable return"
                )
            return LambdaValue(
                FunctionDefinition(signature, Block((Return(body_value),)))
            )
