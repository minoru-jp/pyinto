"""Per-parse statement normalization with explicit cross-domain services.

Statement rules share a ParseContext with the other normalizers but do not
inherit the whole frontend. StatementServices lists only their external needs.
"""

from __future__ import annotations

import ast
from typing import Protocol

from pyinto.constructs import (
    ClassDefinition,
    ClassMethodCall,
    ClassReceiverCreation,
    ClassSignature,
    FieldDefinition,
    FunctionCall,
    FunctionDefinition,
    FunctionSignature,
    FunctionValueCall,
    InstanceCreation,
    MethodCall,
    Symbol,
    Value,
    ValueType,
)


class StatementServices(Protocol):
    """Cross-domain operations required by statement normalization."""

    def _annotation(self, node: ast.expr) -> tuple[str, ValueType | None]: ...

    @staticmethod
    def _inherited_field_names(base: ClassSignature) -> set[str]: ...

    def _class_definition(self, node: ast.ClassDef) -> ClassDefinition: ...

    def _instance_creation(self, node: ast.Call) -> InstanceCreation: ...

    def _field(
        self, node: ast.Attribute, receiver: Value | None = None
    ) -> tuple[Value, ClassSignature, FieldDefinition]: ...

    def _class_receiver_source(
        self, node: ast.expr
    ) -> tuple[Value, ClassSignature] | None: ...

    def _class_method_call(self, node: ast.Call) -> ClassMethodCall: ...

    def _class_receiver_creation(self, node: ast.Call) -> ClassReceiverCreation: ...

    def _instance_member_call(
        self, node: ast.Call, receiver: Value | None = None
    ) -> MethodCall | FunctionValueCall: ...

    def _declaration_scope(self) -> tuple[str, ...]: ...

    def _lookup_symbol(self, name: str) -> Symbol | None: ...

    def _lookup_function(self, name: str) -> FunctionSignature | None: ...

    def _function_definition(self, node: ast.FunctionDef) -> FunctionDefinition: ...

    def _function_call(self, node: ast.Call) -> FunctionCall: ...

    def _function_value_call(
        self, node: ast.Call, callee: Value
    ) -> FunctionValueCall: ...

    @staticmethod
    def _is_super_expression(node: ast.expr) -> bool: ...

    def _instance_receiver(self, node: ast.expr) -> Value | None: ...

    def _is_declared_intrinsic_call(self, node: ast.Call) -> bool: ...

    def _is_intrinsic_call(self, node: ast.Call) -> bool: ...

    def _intrinsic_call(self, node: ast.Call) -> Value: ...

    def _stringify(self, value: Value, node: ast.AST) -> Value: ...

    def _value(self, node: ast.expr, expected: ValueType | None = None) -> Value: ...
