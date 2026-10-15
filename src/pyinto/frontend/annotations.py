"""Pure normalization of explicit type annotations into Model value shapes.

No AST execution or type inference is performed; dependencies are passed in
explicitly instead of reading the state of a PythonFrontend instance.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from types import MappingProxyType

from pyinto.constructs import (
    CallableType,
    DictType,
    InstanceType,
    ListType,
    TupleType,
    ValueKind,
    ValueType,
)
from pyinto.interface_mapping import InterfaceMappingRegistry

from .errors import reject
from .kinds import generic_annotation, plain_annotation

_ANNOTATIONS = {
    "int": ValueKind.INTEGER,
    "float": ValueKind.FLOAT,
    "str": ValueKind.STRING,
    "bool": ValueKind.BOOLEAN,
    "object": ValueKind.OBJECT,
}


@dataclass(frozen=True)
class AnnotationScope:
    classes: Mapping[str, InstanceType]
    type_aliases: AbstractSet[str]
    callable_aliases: AbstractSet[str]
    interface_aliases: Mapping[str, str]
    interface_mappings: InterfaceMappingRegistry
    # Local import name -> pyinto.kinds word.
    kind_aliases: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


def parse_annotation(
    node: ast.expr, scope: AnnotationScope
) -> tuple[str, ValueType | None]:
    """Return source spelling and one ValueType; None denotes a interface mapping annotation.

    The interface mapping class variant is resolved on construction, not from
    the type annotation. It is deliberately not fabricated as a ValueType.
    """
    if isinstance(node, ast.Constant) and node.value is None:
        return "None", ValueType(ValueKind.NONE)
    if (
        isinstance(node, ast.Constant)
        and type(node.value) is str
        and node.value in scope.classes
    ):
        return node.value, ValueType(
            ValueKind.INSTANCE, instance_type=scope.classes[node.value]
        )
    if isinstance(node, ast.Name) and node.id in scope.kind_aliases:
        return node.id, plain_annotation(scope.kind_aliases[node.id], node)
    if isinstance(node, ast.Name):
        name = node.id
        if name in scope.classes:
            return name, ValueType(
                ValueKind.INSTANCE, instance_type=scope.classes[name]
            )
        if name in scope.type_aliases:
            return name, ValueType(ValueKind.ANY)
        if name in _ANNOTATIONS:
            return name, ValueType(_ANNOTATIONS[name])
        source = scope.interface_aliases.get(name)
        if (
            source is not None
            and scope.interface_mappings.get_class(source) is not None
        ):
            return source, None
        raise reject(node, f"Unknown type annotation: {name!r}")
    if not isinstance(node, ast.Subscript) or not isinstance(node.value, ast.Name):
        raise reject(
            node,
            "Only explicit simple, fixed tuple, list, dict or Callable annotations are supported",
        )
    generic = node.value.id

    def typed(expr: ast.expr) -> ValueType:
        _, parsed = parse_annotation(expr, scope)
        if parsed is None:
            raise reject(
                expr, "interface mapping annotation cannot be nested in a value type"
            )
        return parsed

    if generic in scope.kind_aliases:
        return ast.unparse(node), generic_annotation(
            scope.kind_aliases[generic], node, typed
        )
    if generic == "dict":
        if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2:
            raise reject(node, "dict requires exactly two explicit types")
        try:
            shape = DictType(typed(node.slice.elts[0]), typed(node.slice.elts[1]))
        except ValueError as exc:
            raise reject(node, str(exc)) from exc
        return ast.unparse(node), ValueType(ValueKind.DICT, dict_type=shape)
    if generic == "list":
        try:
            element_type = typed(node.slice)
            if element_type.kind is ValueKind.NONE:
                raise reject(node.slice, "Unsupported list element type")
            shape = ListType(element_type)
        except ValueError as exc:
            raise reject(node, str(exc)) from exc
        return ast.unparse(node), ValueType(ValueKind.LIST, list_type=shape)
    if generic == "tuple":
        if (
            isinstance(node.slice, ast.Tuple)
            and len(node.slice.elts) == 2
            and isinstance(node.slice.elts[1], ast.Constant)
            and node.slice.elts[1].value is Ellipsis
        ):
            try:
                shape = TupleType(variadic_element_type=typed(node.slice.elts[0]))
            except ValueError as exc:
                raise reject(node, str(exc)) from exc
            return ast.unparse(node), ValueType(ValueKind.TUPLE, tuple_type=shape)
        elements = (
            node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        )
        try:
            element_types = tuple(typed(item) for item in elements)
            if any(t.kind is ValueKind.NONE for t in element_types):
                raise reject(node, "Unsupported tuple element type")
            shape = TupleType(element_types)
        except ValueError as exc:
            raise reject(node, str(exc)) from exc
        return ast.unparse(node), ValueType(ValueKind.TUPLE, tuple_type=shape)
    if generic in scope.callable_aliases:
        arguments = node.slice
        if not (
            isinstance(arguments, ast.Tuple)
            and len(arguments.elts) == 2
            and isinstance(arguments.elts[0], ast.List)
        ):
            raise reject(node, "Callable requires explicit parameter list and result")
        try:
            parameter_types = tuple(typed(a) for a in arguments.elts[0].elts)
            if any(t.kind is ValueKind.NONE for t in parameter_types):
                raise reject(node, "Unsupported Callable parameter type")
            shape = CallableType(parameter_types, typed(arguments.elts[1]))
        except ValueError as exc:
            raise reject(node, str(exc)) from exc
        return ast.unparse(node), ValueType(ValueKind.FUNCTION, callable_type=shape)
    raise reject(
        node,
        "Only explicitly imported Callable or built-in list/tuple/dict types are supported",
    )
