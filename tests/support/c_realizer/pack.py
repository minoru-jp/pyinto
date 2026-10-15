"""Non-distributable C reference Realizer using the public pyinto APIs.

Kept with tests to verify meaning-preserving Composition without coupling
Host distribution to a particular language Target.
"""

from __future__ import annotations

from functools import lru_cache

from pyinto.constructs import (
    Comparison,
    ConstructError,
    For,
    Literal,
    Range,
    Reference,
    While,
)
from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations.layout import TemplatePlan, Text
from pyinto.realizations.registry import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import (
    naming,
    realizes,
)


def _integer(value: int) -> str:
    if not -(2**63) <= value < 2**63:
        raise ValueError("Integer literal exceeds signed 64-bit range")
    if value == -(2**63):
        return "(-9223372036854775807LL - 1LL)"
    return f"{value}LL"


def _string(value: str) -> str:
    if "\x00" in value:
        raise ValueError("C print prototype does not support NUL in strings")
    pieces: list[str] = []
    for byte in value.encode("utf-8"):
        if byte == 34:
            pieces.append('\\"')
        elif byte == 92:
            pieces.append("\\\\")
        elif 32 <= byte < 127:
            pieces.append(chr(byte))
        else:
            pieces.append(f"\\{byte:03o}")
    return '"' + "".join(pieces) + '"'


@realizes(lang.Program)
class CProgram:
    template = "${requirements}\nint main(void) {\n    ${body}\n    return 0;\n}"


@realizes(lang.Block)
class CBlock:
    template = "${children}"


@realizes(lang.Initialize)
class CInitialize:
    template = "${type} ${name} = ${value};"


@realizes(lang.Assign)
class CAssign:
    template = "${target} = ${value};"


@realizes(lang.ExpressionStatement)
class CExpressionStatement:
    template = "${expression};"


def _c_comparison(node: Comparison, context: object) -> str:
    # ISO C does not sequence operands. Only two plain non-mutating values,
    # or one literal paired with any operand, avoid observable ordering.
    # A Reference must not be assumed independent of a call modifying it.
    left, right = node.left, node.right
    if not (
        isinstance(left, Literal)
        or isinstance(right, Literal)
        or (isinstance(left, Reference) and isinstance(right, Reference))
    ):
        raise ConstructError("C comparison cannot guarantee operand evaluation order")
    return "(${left} ${op} ${right})"


@realizes(lang.Comparison)
class CComparison:
    supports = ("evaluation.operands.left_to_right",)
    render = _c_comparison


@realizes(lang.Reference)
class CReference:
    template = "${name}"


@realizes(lang.Branch)
class CBranch:
    template = "if (${condition}) {\n    ${then}\n}"


@realizes(lang.Branch)
class CBranchWithElse:
    variant = "with_else"
    template = "if (${condition}) {\n    ${then}\n} else {\n    ${otherwise}\n}"


@realizes(lang.While)
class CWhile:
    template = "while (${condition}) {\n    ${body}\n}"


def _while_with_else(node: While, context: object) -> str:
    # The C loop update clause runs on a normal iteration and on `continue`,
    # but is skipped by `break`. That difference precisely controls `else`.
    from pyinto.realizations.registry import EmitContext

    assert isinstance(context, EmitContext)
    flag = context.fresh("while_aborted")
    return (
        "{\n"
        f"    int {flag} = 0;\n"
        f"    for (; ${{condition}}; {flag} = 0) {{\n"
        f"        {flag} = 1;\n"
        "        ${body}\n"
        "    }\n"
        f"    if (!{flag}) {{\n"
        "        ${otherwise}\n"
        "    }\n}"
    )


@realizes(lang.While)
class CWhileWithElse:
    variant = "with_else"
    render = _while_with_else


@realizes(lang.Break)
class CBreak:
    template = "break;"


@realizes(lang.Continue)
class CContinue:
    template = "continue;"


def _c_for_range(node: For, context: object) -> TemplatePlan:
    """Realize Python range iteration with once-evaluated bounds and step.

    The induction variable is *not* the Python target variable: assigning to
    the target inside the body must not alter the next iteration's value.
    """
    from pyinto.realizations.registry import EmitContext

    assert isinstance(context, EmitContext)
    if not isinstance(node.entry.iterable, Range):
        raise TypeError("C for Binding requires a range iteration source")
    if len(node.entry.iterable.arguments) == 3:
        chosen_step = node.entry.iterable.arguments[2]
        if isinstance(chosen_step, Literal) and chosen_step.value == 0:
            raise ValueError("C range Binding cannot realize a zero step")
    if node.entry.target.kind.value != "integer":
        raise TypeError("C range iteration target must be a declared integer")
    suffix = context.fresh("range")
    start, stop, step, index = (
        f"{suffix}_{part}" for part in ("start", "stop", "step", "index")
    )
    flag = f"{suffix}_aborted"
    with_else = node.else_body is not None
    template = (
        "{\n"
        f"    long long {start} = ${{start}};\n"
        f"    long long {stop} = ${{stop}};\n"
        f"    long long {step} = ${{step}};\n"
        f"    if ({step} == 0) {{ abort(); }}\n"
    )
    context.headers.add("stdlib.h")
    if with_else:
        template += f"    int {flag} = 0;\n"
    update = f"{index} += {step}"
    if with_else:
        update += f", {flag} = 0"
    template += (
        f"    for (long long {index} = {start};\n"
        f"         ({step} > 0 ? {index} < {stop} : {index} > {stop});\n"
        f"         {update}) {{\n"
    )
    if with_else:
        template += f"        {flag} = 1;\n"
    template += (
        "        ${target} = "
        + index
        + ";\n        (void) ${target};\n        ${body}\n    }\n"
    )
    if with_else:
        template += f"    if (!{flag}) {{\n        ${{otherwise}}\n    }}\n"
    # The Model preserves only entry/body/else. These additional placements
    # are C-specific Realization choices, not For.parts() projections.
    start_value, stop_value, step_value = node.entry.iterable.bounds()
    return TemplatePlan(
        template + "}",
        {
            "target": node.entry.target,
            "start": start_value,
            "stop": stop_value,
            "step": step_value,
        },
    )


@realizes(lang.For)
class CFor:
    supports = ("iteration.source.range", "loop.for.break_continue")
    render = _c_for_range


@realizes(lang.For)
class CForWithElse:
    variant = "with_else"
    supports = (
        "iteration.source.range",
        "loop.for.break_continue",
        "loop.for.normal_completion_else",
    )
    render = _c_for_range


@realizes(vt.Integer)
class CInteger:
    type_name = "long long"


@realizes(vt.Boolean)
class CBoolean:
    type_name = "_Bool"


@realizes(vt.String)
class CString:
    type_name = "const char *"


@realizes(lang.Literal)
class CIntegerLiteral:
    variant = "integer"
    render = lambda node, context: Text(_integer(node.value))


@realizes(lang.Literal)
class CStringLiteral:
    variant = "string"
    render = lambda node, context: Text(_string(node.value))


@naming
class CNames:
    reserved = frozenset(
        [
            "auto",
            "break",
            "case",
            "char",
            "const",
            "continue",
            "default",
            "do",
            "double",
            "else",
            "enum",
            "extern",
            "float",
            "for",
            "goto",
            "if",
            "inline",
            "int",
            "long",
            "register",
            "restrict",
            "return",
            "short",
            "signed",
            "sizeof",
            "static",
            "struct",
            "switch",
            "typedef",
            "union",
            "unsigned",
            "void",
            "volatile",
            "while",
            "_Bool",
            "_Complex",
            "_Imaginary",
            "_Alignas",
            "_Alignof",
            "_Atomic",
            "_Generic",
            "_Noreturn",
            "_Static_assert",
            "_Thread_local",
            "main",
        ]
    )
    forbidden_prefixes = ("__", "sk_")
    requirement_line = "#include <${name}>"


@realizes(builtin.PrintCall)
class CPrint:
    accepts = ("string",)
    requires = ("stdio.h",)
    template = "puts(${arg0});"


C_DECLARATIONS = (
    CProgram,
    CBlock,
    CInitialize,
    CAssign,
    CComparison,
    CExpressionStatement,
    CReference,
    CBranch,
    CBranchWithElse,
    CWhile,
    CWhileWithElse,
    CBreak,
    CContinue,
    CFor,
    CForWithElse,
    CInteger,
    CBoolean,
    CString,
    CIntegerLiteral,
    CStringLiteral,
    CNames,
    CPrint,
)


class CTargetPack:
    target = "c"
    entries = C_DECLARATIONS
    dispatch = "composition"
    session = TextArtifactSession


@lru_cache(maxsize=1)
def c_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(CTargetPack)
