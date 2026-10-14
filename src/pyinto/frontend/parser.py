"""Explicitly typed Python source to target-independent Construct trees.

This frontend is deliberately not a general Python type inference engine.
Unregistered interface mapping operations and syntax outside the supported subset fail.
"""

from __future__ import annotations

import ast

from pyinto.constructs import (
    Block,
    ClassDefinition,
    ClassMethodCall,
    ClassReceiverCreation,
    ClassSignature,
    Construct,
    FieldDefinition,
    FunctionCall,
    FunctionDefinition,
    FunctionSignature,
    FunctionValueCall,
    InstanceCreation,
    LambdaValue,
    MethodCall,
    MethodKind,
    Program,
    Symbol,
    Value,
    ValueType,
)
from pyinto.interface_mapping import InterfaceMappingRegistry
from pyinto.intrinsics import IntrinsicRegistry, standard_intrinsics

from .annotations import AnnotationScope, parse_annotation
from .classes import ClassNormalizer
from .context import ParseContext
from .decorators import DecoratorRegistry, default_decorators
from .docstrings import split_docstring
from .errors import UnsupportedPython, reject
from .expressions import ExpressionNormalizer
from .functions import FunctionNormalizer
from .imports import ImportNormalizer
from .interface_mapping import InterfaceMappingNormalizer
from .statements import StatementNormalizer


class PythonFrontend:
    """Python syntax adapter. Never executes user code or interface mapping methods."""

    def __init__(
        self,
        interface_mappings: InterfaceMappingRegistry | None = None,
        *,
        decorators: DecoratorRegistry | None = None,
        intrinsics: IntrinsicRegistry | None = None,
    ) -> None:
        self._decorators = (decorators or default_decorators()).fresh()
        self._interface_mappings = (
            interface_mappings
            if interface_mappings is not None
            else InterfaceMappingRegistry()
        )
        self._intrinsics = (
            intrinsics if intrinsics is not None else standard_intrinsics()
        )
        self._reset_parse_state()

    def _reset_parse_state(self) -> None:
        """Create matched per-parse services with one shared, fresh context."""
        self._context = ParseContext()
        self._interface_mapping_normalizer = self._new_interface_mapping_normalizer()
        self._expressions = self._new_expression_normalizer()
        self._statements = StatementNormalizer(
            self._context, self._interface_mapping_normalizer, self
        )
        self._functions = FunctionNormalizer(self._context, self._decorators, self)
        self._classes = ClassNormalizer(self._context, self._decorators, self)

    def _new_interface_mapping_normalizer(self) -> InterfaceMappingNormalizer:
        return InterfaceMappingNormalizer(
            self._context,
            self._interface_mappings,
            value=self._value,
            declaration_scope=self._declaration_scope,
        )

    def parse(self, source: str) -> Program:
        self._reset_parse_state()
        self._decorators.clear_imports()
        tree = ast.parse(source)
        # Synthetic lambda declarations must never collide with any source
        # spelling, including declarations encountered later in the module.
        self._context.names.source_names = {
            node.id
            if isinstance(node, ast.Name)
            else node.arg
            if isinstance(node, ast.arg)
            else node.name
            for node in ast.walk(tree)
            if isinstance(
                node,
                (
                    ast.Name,
                    ast.arg,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            )
        }
        docstring, statements = split_docstring(tree.body)
        imports = ImportNormalizer(
            self._context.names, self._interface_mappings, self._decorators
        )
        start = 0
        while start < len(statements) and isinstance(
            statements[start], (ast.ImportFrom, ast.Import)
        ):
            statement = statements[start]
            assert isinstance(statement, (ast.ImportFrom, ast.Import))
            imports.accept(statement)
            start += 1
        self._collect_classes(statements[start:])
        self._collect_functions(statements[start:])
        return Program(self._block(statements[start:]), docstring)

    @staticmethod
    def _reject(node: ast.AST, reason: str) -> UnsupportedPython:
        return reject(node, reason)

    def _stringify(self, value: Value, node: ast.AST):
        return self._expressions._stringify(value, node)

    def _annotation(self, node: ast.expr) -> tuple[str, ValueType | None]:
        return parse_annotation(
            node,
            AnnotationScope(
                self._context.classes.class_types,
                self._context.names.type_aliases,
                self._context.names.callable_aliases,
                self._context.names.interface_aliases,
                self._interface_mappings,
            ),
        )

    def _new_expression_normalizer(self) -> ExpressionNormalizer:
        return ExpressionNormalizer(
            self._context, self._interface_mapping_normalizer, self, self._intrinsics
        )

    def _value(self, node: ast.expr, expected: ValueType | None = None) -> Value:
        return self._expressions._value(node, expected)

    def _instance_receiver(self, node: ast.expr) -> Value | None:
        return self._expressions._instance_receiver(node)

    @staticmethod
    def _is_super_expression(node: ast.expr) -> bool:
        return ExpressionNormalizer._is_super_expression(node)

    def _is_declared_intrinsic_call(self, node: ast.Call) -> bool:
        return self._expressions._is_declared_intrinsic_call(node)

    def _is_intrinsic_call(self, node: ast.Call) -> bool:
        return self._expressions._is_intrinsic_call(node)

    def _intrinsic_call(self, node: ast.Call) -> Value:
        return self._expressions._intrinsic_call(node)

    def _block(self, body: list[ast.stmt]) -> Block:
        return self._statements._block(body)

    def _statement(self, node: ast.stmt) -> Construct:
        return self._statements._statement(node)

    # Class-domain facade: only operations called from another component.
    def _collect_classes(self, statements: list[ast.stmt]) -> None:
        self._classes._collect_classes(statements)

    def _method_kind(self, node: ast.FunctionDef) -> MethodKind:
        return self._classes._method_kind(node)

    def _class_definition(self, node: ast.ClassDef) -> ClassDefinition:
        return self._classes._class_definition(node)

    def _instance_creation(self, node: ast.Call) -> InstanceCreation:
        return self._classes._instance_creation(node)

    def _field(
        self, node: ast.Attribute, receiver: Value | None = None
    ) -> tuple[Value, ClassSignature, FieldDefinition]:
        return self._classes._field(node, receiver)

    def _method_call(self, node: ast.Call, receiver: Value | None = None) -> MethodCall:
        return self._classes._method_call(node, receiver)

    def _class_receiver_source(
        self, node: ast.expr
    ) -> tuple[Value, ClassSignature] | None:
        return self._classes._class_receiver_source(node)

    def _class_method_call(self, node: ast.Call) -> ClassMethodCall:
        return self._classes._class_method_call(node)

    def _class_receiver_creation(self, node: ast.Call) -> ClassReceiverCreation:
        return self._classes._class_receiver_creation(node)

    def _instance_member_call(
        self, node: ast.Call, receiver: Value | None = None
    ) -> MethodCall | FunctionValueCall:
        return self._classes._instance_member_call(node, receiver)

    @staticmethod
    def _inherited_field_names(base: ClassSignature) -> set[str]:
        return ClassNormalizer._inherited_field_names(base)

    # Function-domain facade retained only for cross-domain composition.
    # The normalizer itself is independent of the parser's inheritance tree.
    def _collect_functions(self, statements: list[ast.stmt]) -> None:
        self._functions._collect_functions(statements)

    def _declaration_scope(self) -> tuple[str, ...]:
        return self._functions._declaration_scope()

    def _lookup_symbol(self, name: str) -> Symbol | None:
        return self._functions._lookup_symbol(name)

    def _lookup_function(self, name: str) -> FunctionSignature | None:
        return self._functions._lookup_function(name)

    def _function_definition(self, node: ast.FunctionDef) -> FunctionDefinition:
        return self._functions._function_definition(node)

    def _declared_call_arguments(
        self,
        node: ast.Call,
        parameters: tuple[Symbol, ...],
        defaults: tuple[Value | None, ...] = (),
    ) -> tuple[tuple[Value, ...], tuple[int, ...], tuple[int, ...]]:
        return self._functions._declared_call_arguments(node, parameters, defaults)

    def _function_call(self, node: ast.Call) -> FunctionCall:
        return self._functions._function_call(node)

    def _function_value_call(self, node: ast.Call, callee: Value) -> FunctionValueCall:
        return self._functions._function_value_call(node, callee)

    def _lambda_value(
        self, node: ast.Lambda, expected: ValueType | None
    ) -> LambdaValue:
        return self._functions._lambda_value(node, expected)
