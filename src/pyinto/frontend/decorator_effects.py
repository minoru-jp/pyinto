"""Built-in, statically adopted declaration effects (not Python evaluation)."""

from __future__ import annotations

import ast
import copy

from .decorators import ClassDecorationPlan
from .docstrings import split_docstring
from .errors import reject


def dataclass_plan(node: ast.ClassDef) -> ClassDecorationPlan:
    """Normalize the selected dataclass subset into an existing __init__ body.

    This preserves the Phase 29 Model contract; it is not a generic execution
    of ``dataclasses.dataclass`` or other Python decorator code.
    """
    fields: list[ast.AnnAssign] = []
    seen_default = False
    _, class_body = split_docstring(node.body)
    for statement in class_body:
        if isinstance(statement, ast.Pass):
            if len(class_body) != 1:
                raise reject(statement, "pass cannot mix with data fields")
            continue
        if isinstance(statement, ast.FunctionDef):
            if statement.name == "__init__":
                raise reject(statement, "Data class cannot define __init__")
            continue
        if (
            not isinstance(statement, ast.AnnAssign)
            or not isinstance(statement.target, ast.Name)
            or statement.simple != 1
        ):
            raise reject(
                statement, "Data class requires typed field declarations and methods"
            )
        if statement.target.id in {"self", "cls"}:
            raise reject(statement, "Reserved data class field name")
        if statement.value is None and seen_default:
            raise reject(statement, "Required data class field after default")
        if statement.value is not None:
            seen_default = True
        fields.append(statement)
    args = [ast.arg(arg="self", annotation=None)] + [
        ast.arg(arg=f.target.id, annotation=copy.deepcopy(f.annotation))
        for f in fields
        if isinstance(f.target, ast.Name)
    ]
    defaults = [copy.deepcopy(f.value) for f in fields if f.value is not None]
    body: list[ast.stmt] = [
        ast.AnnAssign(
            target=ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr=f.target.id,
                ctx=ast.Store(),
            ),
            annotation=copy.deepcopy(f.annotation),
            value=ast.Name(id=f.target.id, ctx=ast.Load()),
            simple=0,
        )
        for f in fields
        if isinstance(f.target, ast.Name)
    ] or [ast.Return(value=None)]
    generated = ast.FunctionDef(
        name="__init__",
        args=ast.arguments(
            posonlyargs=[],
            args=args,
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=defaults,
        ),
        body=body,
        decorator_list=[],
        returns=ast.Constant(value=None),
        type_comment=None,
    )
    ast.copy_location(generated, node)
    ast.fix_missing_locations(generated)
    return ClassDecorationPlan(
        (generated,), allow_field_declarations=True, allow_bases=False
    )
