"""Non-public Python realizer for pyinto regression and meaning-preservation tests.

This fixture is intentionally incomplete and must not ship in the Host wheel.
"""

from __future__ import annotations

import keyword
from functools import lru_cache

from pyinto.constructs import (
    With,
)
from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.realizations.layout import Text
from pyinto.realizations.registry import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import (
    naming,
    realizes,
)


@realizes(lang.Program)
class PythonProgram:
    template = "${body}"


@realizes(lang.Block)
class PythonBlock:
    render = lambda node, ctx: "${children}" if node.children else "pass"


@realizes(lang.Initialize)
class PythonInitialize:
    template = "${name} = ${value}"


@realizes(lang.Assign)
class PythonAssign:
    template = "${target} = ${value}"


@realizes(lang.ExpressionStatement)
class PythonExpressionStatement:
    template = "${expression}"


@realizes(lang.Comparison)
class PythonComparison:
    supports = ("evaluation.operands.left_to_right",)
    template = "(${left} ${op} ${right})"


@realizes(lang.Reference)
class PythonReference:
    template = "${name}"


@realizes(lang.Branch)
class PythonBranch:
    template = "if ${condition}:\n    ${then}"


@realizes(lang.Branch)
class PythonBranchWithElse:
    variant = "with_else"
    template = "if ${condition}:\n    ${then}\nelse:\n    ${otherwise}"


@realizes(lang.While)
class PythonWhile:
    template = "while ${condition}:\n    ${body}"


@realizes(lang.While)
class PythonWhileWithElse:
    variant = "with_else"
    template = "while ${condition}:\n    ${body}\nelse:\n    ${otherwise}"


@realizes(lang.Break)
class PythonBreak:
    template = "break"


@realizes(lang.Continue)
class PythonContinue:
    template = "continue"


@realizes(builtin.Range)
class PythonRangeOne:
    variant = "1"
    template = "range(${arg0})"


@realizes(builtin.Range)
class PythonRangeTwo:
    variant = "2"
    template = "range(${arg0}, ${arg1})"


@realizes(builtin.Range)
class PythonRangeThree:
    variant = "3"
    template = "range(${arg0}, ${arg1}, ${arg2})"


@realizes(lang.IterationEntry)
class PythonIteration:
    supports = (
        "iteration.source.range",
        "iteration.source.string",
        "iteration.source.list",
        "iteration.source.tuple",
        "iteration.source.iterable",
    )
    template = "${target} in ${iterable}"


@realizes(lang.For)
class PythonFor:
    supports = (
        "iteration.source.range",
        "iteration.source.string",
        "iteration.source.list",
        "iteration.source.tuple",
        "iteration.source.iterable",
        "loop.for.break_continue",
    )
    template = "for ${entry}:\n    ${body}"


@realizes(lang.For)
class PythonForWithElse:
    supports = (
        "iteration.source.range",
        "iteration.source.string",
        "iteration.source.list",
        "iteration.source.tuple",
        "iteration.source.iterable",
        "loop.for.break_continue",
        "loop.for.normal_completion_else",
    )
    variant = "with_else"
    template = "for ${entry}:\n    ${body}\nelse:\n    ${otherwise}"


@realizes(lang.ContextEntry)
class PythonContextEntry:
    template = "${context}"


@realizes(lang.ContextEntry)
class PythonContextEntryWithTarget:
    variant = "with_target"
    template = "${context} as ${target}"


def _python_with(node: With, context: object) -> str:
    entries = ", ".join(f"${{entry{i}}}" for i in range(len(node.entries)))
    return f"with {entries}:\n    ${{body}}"


@realizes(lang.With)
class PythonWith:
    supports = ("context.with.enter_exit_exception",)
    render = _python_with


@realizes(lang.Literal)
class PythonIntegerLiteral:
    variant = "integer"
    render = lambda node, context: Text(repr(node.value))


@realizes(lang.Literal)
class PythonStringLiteral:
    variant = "string"
    render = lambda node, context: Text(repr(node.value))


@naming
class PythonNames:
    reserved = frozenset(keyword.kwlist)


@realizes(builtin.PrintCall)
class PythonPrint:
    template = "print(${arg0})"


PYTHON_DECLARATIONS = (
    PythonProgram,
    PythonBlock,
    PythonInitialize,
    PythonAssign,
    PythonComparison,
    PythonExpressionStatement,
    PythonReference,
    PythonBranch,
    PythonBranchWithElse,
    PythonWhile,
    PythonWhileWithElse,
    PythonBreak,
    PythonContinue,
    PythonRangeOne,
    PythonRangeTwo,
    PythonRangeThree,
    PythonIteration,
    PythonFor,
    PythonForWithElse,
    PythonContextEntry,
    PythonContextEntryWithTarget,
    PythonWith,
    PythonIntegerLiteral,
    PythonStringLiteral,
    PythonNames,
    PythonPrint,
)


class PythonTargetPack:
    target = "python"
    entries = PYTHON_DECLARATIONS
    dispatch = "composition"
    session = TextArtifactSession


@lru_cache(maxsize=1)
def python_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(PythonTargetPack)
