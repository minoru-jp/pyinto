"""Typed class normalization with explicit cross-domain services."""

from __future__ import annotations

import ast
from typing import Protocol

from pyinto.constructs import (
    ClassDefinition,
    ClassMethodCall,
    ClassReceiverCreation,
    ClassReference,
    ClassSignature,
    FieldDefinition,
    FieldRead,
    FunctionDefinition,
    FunctionSignature,
    FunctionValueCall,
    InstanceCreation,
    InstanceType,
    KindLabel,
    MethodCall,
    MethodDispatch,
    MethodKind,
    ParameterRole,
    Reference,
    Symbol,
    Value,
    ValueKind,
    ValueType,
)
from pyinto.constructs.kinds import class_label
from pyinto.constructs.types import CLASS_LABELS

from .context import ParseContext
from .decorators import ClassDecorationPlan, DecoratorRegistry
from .docstrings import split_docstring
from .errors import UnsupportedPython, reject


class ClassServices(Protocol):
    """Only the operations from other normalization domains used by classes."""

    def _annotation(self, node: ast.expr) -> tuple[str, ValueType | None]: ...

    def _collect_functions(self, statements: list[ast.stmt]) -> None: ...

    def _function_definition(self, node: ast.FunctionDef) -> FunctionDefinition: ...

    def _declared_call_arguments(
        self,
        node: ast.Call,
        parameters: tuple[Symbol, ...],
        defaults: tuple[Value | None, ...] = (),
    ) -> tuple[tuple[Value, ...], tuple[int, ...], tuple[int, ...]]: ...

    def _lookup_symbol(self, name: str) -> Symbol | None: ...

    def _lookup_function(self, name: str) -> FunctionSignature | None: ...

    def _value(self, node: ast.expr, expected: ValueType | None = None) -> Value: ...

    def _function_value_call(
        self, node: ast.Call, callee: Value
    ) -> FunctionValueCall: ...

    @staticmethod
    def _is_super_expression(node: ast.expr) -> bool: ...


class ClassNormalizer:
    """Class rules belong to a per-parse component, not a parser mixin."""

    def __init__(
        self,
        context: ParseContext,
        decorators: DecoratorRegistry,
        services: ClassServices,
    ) -> None:
        self._context = context
        self._decorators = decorators
        self._services = services

    _reject = staticmethod(reject)

    def _collect_classes(self, statements: list[ast.stmt]) -> None:
        """Reserve nominal identities before resolving annotation trees."""
        for node in statements:
            if not isinstance(node, ast.ClassDef):
                continue
            if (
                node.name in self._context.classes.class_types
                or node.name
                in {
                    "print",
                    "range",
                    "int",
                    "str",
                    "bool",
                    "object",
                    "list",
                    "tuple",
                    "dict",
                    "super",
                    "staticmethod",
                    "classmethod",
                }
                or node.name in self._context.names.type_aliases
                or node.name in self._context.names.callable_aliases
                or node.name in self._context.names.module_aliases
                or node.name in self._context.names.interface_aliases
                or node.name in self._context.names.kind_aliases
                or node.name in self._decorators.imported_names
            ):
                raise self._reject(node, "Duplicate or reserved class name")
            decoration = self._class_decoration(node)
            if (
                len(node.bases) > 1
                or node.keywords
                or (not decoration.allow_bases and node.bases)
            ):
                raise self._reject(
                    node, "Inheritance is limited to static single inheritance"
                )
            base: InstanceType | None = None
            if node.bases:
                parent = node.bases[0]
                if (
                    not isinstance(parent, ast.Name)
                    or parent.id not in self._context.classes.class_types
                ):
                    raise self._reject(
                        parent,
                        "Inheritance requires a base class declared earlier in the module",
                    )
                base = self._context.classes.class_types[parent.id]
            self._context.classes.class_types[node.name] = InstanceType(
                node.name, base=base
            )

    def _class_decoration(self, node: ast.ClassDef) -> ClassDecorationPlan:
        # Class signatures are pre-collected. An adapter must still run only
        # once even though its plan is needed again while building the class.
        cached = self._context.classes.class_decorations.get(node)
        if cached is not None:
            return cached
        decorators = self._kind_class_labels(node)
        if not decorators:
            plan = ClassDecorationPlan()
            self._context.classes.class_decorations[node] = plan
            return plan
        if len(decorators) != 1:
            raise self._reject(node, "Only one registered class decorator is supported")
        decorator = decorators[0]
        rule = (
            self._decorators.lookup(
                decorator.id,
                target="class",
                shadowed=set(self._context.names.functions)
                | set(self._context.names.symbols),
            )
            if isinstance(decorator, ast.Name)
            else None
        )
        if rule is None:
            raise self._reject(
                node, "Inheritance is limited to registered class decorators"
            )
        try:
            plan = self._decorators.class_plan(rule, node)
        except (ValueError, TypeError) as exc:
            raise self._reject(node, str(exc)) from exc
        self._context.classes.class_decorations[node] = plan
        return plan

    def _kind_class_labels(self, node: ast.ClassDef) -> list[ast.expr]:
        """Record @Interface / @MixIn / @Implements; return other decorators.

        These vocabulary words carry no Host meaning. Implements may name only
        classes declared earlier in the module.
        """
        aliases = self._context.names.kind_aliases
        labels: list[KindLabel] = []
        remaining: list[ast.expr] = []
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            head = call.func if call is not None else decorator
            word = aliases.get(head.id) if isinstance(head, ast.Name) else None
            if word is None:
                remaining.append(decorator)
                continue
            if word not in CLASS_LABELS:
                raise self._reject(decorator, f"{word} is not a class decorator")
            if (word == "Implements") != (call is not None):
                raise self._reject(
                    decorator,
                    "Implements requires class arguments"
                    if word == "Implements"
                    else f"{word} takes no arguments",
                )
            implemented: list[InstanceType] = []
            if call is not None:
                if call.keywords or not call.args:
                    raise self._reject(
                        decorator, "Implements requires one or more classes"
                    )
                for argument in call.args:
                    if (
                        not isinstance(argument, ast.Name)
                        or argument.id not in self._context.classes.class_types
                        or argument.id == node.name
                    ):
                        raise self._reject(
                            argument,
                            "Implements requires classes declared earlier in the module",
                        )
                    implemented.append(self._context.classes.class_types[argument.id])
            try:
                labels.append(class_label(word, tuple(implemented)))
            except ValueError as exc:
                raise self._reject(decorator, str(exc)) from exc
        if len({label.name for label in labels}) != len(labels):
            raise self._reject(node, "Duplicate kind class decorator")
        # Python applies decorators bottom-up; record them in source order.
        self._context.classes.class_labels[node] = tuple(labels)
        return remaining

    def _method_kind(self, node: ast.FunctionDef) -> MethodKind:
        if not node.decorator_list:
            return MethodKind.INSTANCE
        if len(node.decorator_list) != 1 or not isinstance(
            node.decorator_list[0], ast.Name
        ):
            raise self._reject(
                node, "Only one registered method decorator is supported"
            )
        name = node.decorator_list[0].id
        rule = self._decorators.lookup(
            name,
            target="method",
            shadowed=(
                set(self._context.names.symbols)
                | set(self._context.classes.class_module_functions)
                | set(self._context.classes.class_types)
                | set(self._context.names.interface_aliases)
                | set(self._context.names.module_aliases)
            ),
        )
        if rule is None:
            raise self._reject(node, "Unknown or shadowed method decorator")
        try:
            return self._decorators.method_kind(rule, node)
        except (ValueError, TypeError) as exc:
            raise self._reject(node, str(exc)) from exc

    def _class_fields(
        self, node: ast.ClassDef, initializer: ast.FunctionDef
    ) -> tuple[FieldDefinition, ...]:
        """Require direct, initialized, typed instance fields inside __init__."""
        receiver_name = initializer.args.args[0].arg
        fields: list[FieldDefinition] = []
        after_fields = False
        is_derived = self._context.classes.class_types[node.name].base is not None
        _, initializer_body = split_docstring(initializer.body)
        for index, stmt in enumerate(initializer_body):
            if is_derived and index == 0 and self._is_super_init_statement(stmt):
                continue
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(
                stmt.target, ast.Attribute
            ):
                after_fields = True
                continue
            if after_fields:
                raise self._reject(
                    stmt, "Typed fields must be initialized at the start of __init__"
                )
            target = stmt.target
            if (
                not isinstance(target.value, ast.Name)
                or target.value.id != receiver_name
            ):
                raise self._reject(
                    stmt, "Typed instance field must use the initializer receiver"
                )
            if stmt.value is None or stmt.simple != 0:
                raise self._reject(stmt, "Instance field must be initialized")
            _, value_type = self._services._annotation(stmt.annotation)
            if value_type is None:
                raise self._reject(stmt, "interface mapping fields are not supported")
            try:
                field = FieldDefinition(target.attr, value_type)
            except ValueError as exc:
                raise self._reject(stmt, str(exc)) from exc
            if any(previous.name == field.name for previous in fields):
                raise self._reject(stmt, "Duplicate instance field declaration")
            fields.append(field)
        return tuple(fields)

    @staticmethod
    def _inherited_field_names(base: ClassSignature) -> set[str]:
        names = {f.name for f in base.fields}
        if base.base is not None:
            names.update(ClassNormalizer._inherited_field_names(base.base))
        return names

    @staticmethod
    def _is_super_init_statement(statement: ast.stmt) -> bool:
        if not isinstance(statement, ast.Expr) or not isinstance(
            statement.value, ast.Call
        ):
            return False
        method = statement.value.func
        return (
            isinstance(method, ast.Attribute)
            and method.attr == "__init__"
            and isinstance(method.value, ast.Call)
            and isinstance(method.value.func, ast.Name)
            and method.value.func.id == "super"
            and not method.value.args
            and not method.value.keywords
        )

    def _class_definition(self, node: ast.ClassDef) -> ClassDefinition:
        if (
            self._context.names.active_function is not None
            or self._context.flow.block_depth != 1
        ):
            raise self._reject(node, "Only module-level classes are supported")
        decoration = self._class_decoration(node)
        if (
            node.keywords
            or getattr(node, "type_params", ())
            or len(node.bases) > 1
            or (not decoration.allow_bases and node.bases)
        ):
            raise self._reject(node, "Unsupported dynamic class construction")
        docstring, class_body = split_docstring(node.body)
        methods_ast = tuple(
            stmt for stmt in class_body if isinstance(stmt, ast.FunctionDef)
        )
        if decoration.synthesized_methods:
            methods_ast = (*decoration.synthesized_methods, *methods_ast)
        if not decoration.allow_field_declarations and (
            not class_body
            or len(
                tuple(stmt for stmt in class_body if isinstance(stmt, ast.FunctionDef))
            )
            != len(class_body)
        ):
            raise self._reject(node, "Class body must contain only typed methods")
        identity = self._context.classes.class_types[node.name]
        base = (
            self._context.classes.classes.get(identity.base.name)
            if identity.base
            else None
        )
        if identity.base is not None and (
            base is None or base.identity != identity.base
        ):
            raise self._reject(node, "Base class must precede derived class")
        old_functions = self._context.names.functions
        old_type = self._context.classes.active_class_type
        old_collecting = self._context.classes.collecting_methods
        old_module_functions = self._context.classes.class_module_functions
        self._context.classes.class_module_functions = old_functions
        self._context.names.functions = {}
        self._context.classes.active_class_type = identity
        self._context.classes.collecting_methods = True
        try:
            self._services._collect_functions(list(methods_ast))
            initializer = next(
                (stmt for stmt in methods_ast if stmt.name == "__init__"), None
            )
            if initializer is None:
                raise self._reject(node, "Class requires an explicit __init__")
            if base is not None:
                _, initializer_body = split_docstring(initializer.body)
                if not initializer_body or not self._is_super_init_statement(
                    initializer_body[0]
                ):
                    raise self._reject(
                        initializer,
                        "Derived initializer must start with super().__init__()",
                    )
                super_inits = [
                    child
                    for child in ast.walk(initializer)
                    if isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "__init__"
                    and self._services._is_super_expression(child.func.value)
                ]
                if len(super_inits) != 1:
                    raise self._reject(
                        initializer, "Base initializer must be called exactly once"
                    )
            fields = self._class_fields(node, initializer)
            signature = ClassSignature(
                identity,
                fields,
                tuple(self._context.names.functions[stmt.name] for stmt in methods_ast),
                base,
            )
            self._context.classes.classes[node.name] = signature
            self._context.classes.collecting_methods = False
            methods = tuple(
                self._services._function_definition(stmt) for stmt in methods_ast
            )
            return ClassDefinition(
                signature,
                methods,
                docstring,
                self._context.classes.class_labels.get(node, ()),
            )
        except ValueError as exc:
            if isinstance(exc, UnsupportedPython):
                raise
            raise self._reject(node, str(exc)) from exc
        finally:
            self._context.names.functions = old_functions
            self._context.classes.active_class_type = old_type
            self._context.classes.collecting_methods = old_collecting
            self._context.classes.class_module_functions = old_module_functions

    def _instance_creation(self, node: ast.Call) -> InstanceCreation:
        assert isinstance(node.func, ast.Name)
        signature = self._context.classes.classes.get(node.func.id)
        if signature is None:
            raise self._reject(node, "Class instance creation requires a defined class")
        init = signature.method("__init__")
        assert init is not None
        args, evaluation, omitted = self._services._declared_call_arguments(
            node, init.parameters[1:], init.defaults_by_parameter[1:]
        )
        try:
            return InstanceCreation(signature, args, evaluation, omitted)
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc

    def _field(
        self, node: ast.Attribute, receiver: Value | None = None
    ) -> tuple[Value, ClassSignature, FieldDefinition]:
        if receiver is None:
            receiver = self._services._value(node.value)
        owner = receiver.instance_type
        if owner is None:
            raise self._reject(node, "Attribute receiver is not a class instance")
        declaration = self._context.classes.classes.get(owner.name)
        if declaration is None or declaration.identity != owner:
            raise self._reject(node, "Unknown class instance type")
        found = declaration.resolve_field(node.attr)
        if found is None:
            raise self._reject(node, "Undeclared instance field")
        owner_signature, field = found
        return receiver, owner_signature, field

    def _method_call(self, node: ast.Call, receiver: Value | None = None) -> MethodCall:
        assert isinstance(node.func, ast.Attribute)
        is_super = isinstance(node.func.value, ast.Call) and (
            isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == "super"
        )
        dispatch = MethodDispatch.SUPER if is_super else MethodDispatch.VIRTUAL
        if is_super:
            super_expr = node.func.value
            assert isinstance(super_expr, ast.Call)
            if super_expr.args or super_expr.keywords:
                raise self._reject(super_expr, "Only bare super() is supported")
            if (
                self._services._lookup_symbol("super") is not None
                or self._services._lookup_function("super") is not None
            ):
                raise self._reject(super_expr, "Shadowed super() is not supported")
            method = self._context.names.active_function
            if (
                method is None
                or method.receiver is None
                or self._context.classes.method_owner is None
            ):
                raise self._reject(node, "super() requires an instance method")
            lexical_class = self._context.classes.classes.get(
                self._context.classes.method_owner.name
            )
            if lexical_class is None or lexical_class.base is None:
                raise self._reject(node, "super() requires a declared base class")
            receiver = Reference(method.receiver)
            declaration = lexical_class
            lookup_start = lexical_class.base
        else:
            if receiver is None:
                receiver = self._services._value(node.func.value)
            owner = receiver.instance_type
            declaration = (
                self._context.classes.classes.get(owner.name)
                if owner is not None
                else None
            )
            if declaration is None or declaration.identity != owner:
                raise self._reject(node, "Method receiver must be a typed instance")
            lookup_start = None
        search = lookup_start if lookup_start is not None else declaration
        found = search.resolve_method(node.func.attr)
        if found is None or (node.func.attr == "__init__" and not is_super):
            raise self._reject(node, "Unknown or reserved instance method")
        _, signature = found
        if signature.method_kind in {MethodKind.CLASS, MethodKind.STATIC}:
            raise self._reject(
                node, "Class and static methods require a class receiver"
            )
        arguments, evaluation, omitted = self._services._declared_call_arguments(
            node, signature.parameters[1:], signature.defaults_by_parameter[1:]
        )
        try:
            return MethodCall(
                receiver,
                signature,
                arguments,
                declaration,
                dispatch,
                lookup_start,
                evaluation,
                omitted,
            )
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc

    def _class_receiver_source(
        self, node: ast.expr
    ) -> tuple[Value, ClassSignature] | None:
        if isinstance(node, ast.Name) and node.id in self._context.classes.classes:
            if (
                self._services._lookup_symbol(node.id) is not None
                or self._services._lookup_function(node.id) is not None
            ):
                raise self._reject(node, "Shadowed class name")
            owner = self._context.classes.classes[node.id]
            return ClassReference(owner), owner
        if isinstance(node, ast.Name):
            symbol = self._services._lookup_symbol(node.id)
            if symbol is not None and symbol.role is ParameterRole.CLASS_RECEIVER:
                owner = self._context.classes.classes.get(symbol.annotation or "")
                if owner is None:
                    raise self._reject(node, "Unresolved class receiver")
                return Reference(symbol), owner
        return None

    def _class_method_call(self, node: ast.Call) -> ClassMethodCall:
        assert isinstance(node.func, ast.Attribute)
        source = self._class_receiver_source(node.func.value)
        if source is None:
            raise self._reject(node, "Expected a statically resolved class receiver")
        class_source, owner = source
        found = owner.resolve_method(node.func.attr)
        if found is None:
            raise self._reject(node, "Undeclared class method")
        signature = found[1]
        if signature.method_kind not in {MethodKind.CLASS, MethodKind.STATIC}:
            raise self._reject(node, "Instance method requires an instance receiver")
        start = 0 if signature.method_kind is MethodKind.STATIC else 1
        args, order, omitted = self._services._declared_call_arguments(
            node, signature.parameters[start:], signature.defaults_by_parameter[start:]
        )
        try:
            return ClassMethodCall(class_source, signature, args, owner, order, omitted)
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc

    def _class_receiver_creation(self, node: ast.Call) -> ClassReceiverCreation:
        assert isinstance(node.func, ast.Name)
        source = self._class_receiver_source(node.func)
        if source is None or not isinstance(source[0], Reference):
            raise self._reject(node, "Class factory needs class receiver")
        receiver, owner = source
        assert isinstance(receiver, Reference)
        init = owner.method("__init__")
        assert init is not None
        args, order, omitted = self._services._declared_call_arguments(
            node, init.parameters[1:], init.defaults_by_parameter[1:]
        )
        try:
            return ClassReceiverCreation(receiver, owner, args, order, omitted)
        except ValueError as exc:
            raise self._reject(node, str(exc)) from exc

    def _instance_member_call(
        self, node: ast.Call, receiver: Value | None = None
    ) -> MethodCall | FunctionValueCall:
        """Keep method dispatch distinct from calling a typed function field.

        Both paths use the existing Model contracts. In particular a function
        stored in an instance field is called as a Value, not as an implicitly
        receiver-bound instance method.
        """
        assert isinstance(node.func, ast.Attribute)
        if self._services._is_super_expression(node.func.value):
            return self._method_call(node, receiver)
        if receiver is None:
            receiver = self._services._value(node.func.value)
        instance = receiver.instance_type
        owner = (
            self._context.classes.classes.get(instance.name)
            if instance is not None
            else None
        )
        if owner is not None and owner.identity == instance:
            field = owner.resolve_field(node.func.attr)
            if field is not None and field[1].type.kind is ValueKind.FUNCTION:
                field_owner, definition = field
                return self._services._function_value_call(
                    node, FieldRead(receiver, definition, field_owner)
                )
        return self._method_call(node, receiver)
