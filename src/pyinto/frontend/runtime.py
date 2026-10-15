"""Recognize the trusted-Python runtime hook without normalizing its body.

The magic function is a module-level definition only. It is excluded from the
Construct Model, but its source remains available to the Host for execution.
"""

from __future__ import annotations

import ast

from .errors import UnsupportedPython

RUNTIME_HOOK = "__pyinto_runtime__"
KINDS = "pyinto.kinds"


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
    if found:
        _reject_kinds_with_runtime(tree)
    return ast.Module(body=body, type_ignores=tree.type_ignores), found


def _reject_kinds_with_runtime(tree: ast.Module) -> None:
    """A Source with a runtime hook is executed; kinds are never executed.

    ``pyinto.kinds`` describes information for conversion only, so a Source
    that also defines ``__pyinto_runtime__`` contradicts itself. The rule is
    the Source's own and does not depend on the selected Target.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module or ""]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        if any(name == KINDS or name.startswith(KINDS + ".") for name in names):
            raise UnsupportedPython(
                f"line {node.lineno}: a source with {RUNTIME_HOOK} cannot "
                f"import {KINDS}; kinds are for conversion and are not executed"
            )
