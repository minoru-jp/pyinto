"""Recognize the trusted-Python runtime hook without normalizing its body.

The magic function is a module-level definition only. It is excluded from the
Construct Model, but its source remains available to the Host for execution.
"""

from __future__ import annotations

import ast

RUNTIME_HOOK = "__pyinto_runtime__"


def split_runtime(tree: ast.Module) -> tuple[ast.Module, bool]:
    """Remove one valid runtime definition from an AST module, without execution.

    The returned module shares its ordinary statements with ``tree``; neither
    those statements nor the original AST are mutated.
    """
    body: list[ast.stmt] = []
    found = False
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            reserved = statement.name == RUNTIME_HOOK
        elif isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (
                statement.targets
                if isinstance(statement, ast.Assign)
                else [statement.target]
            )
            reserved = any(
                isinstance(target, ast.Name) and target.id == RUNTIME_HOOK
                for target in targets
            )
        else:
            reserved = False
        if not reserved:
            body.append(statement)
            continue
        if found:
            raise ValueError(f"Duplicate {RUNTIME_HOOK} declaration")
        if not isinstance(statement, ast.FunctionDef):
            raise TypeError(
                f"{RUNTIME_HOOK} must be a synchronous module-level function"
            )
        args = statement.args
        if (
            statement.decorator_list
            or args.posonlyargs
            or args.args
            or args.vararg is not None
            or args.kwonlyargs
            or args.kwarg is not None
        ):
            raise ValueError(f"{RUNTIME_HOOK} must have no arguments or decorators")
        found = True
    return ast.Module(body=body, type_ignores=tree.type_ignores), found
