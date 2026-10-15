"""Iteration 21: actively emitted For/With obligations need checked recipes.

Admission keys are a gate, not a proof. The execution tests exercise the
particular C/Python recipes which claim these contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

import pytest

from devdocs.canonical_sources.reviews.realization_boundary import (
    SEMANTIC_ADMISSION_STATUS,
    STANDARD_PACK_PENDING_DEFERRED,
)
from pyinto import PythonFrontend, realize
from pyinto.constructs import (
    Block,
    Call,
    Construct,
    ConstructError,
    ContextEntry,
    For,
    Literal,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
    With,
)
from pyinto.constructs.admission import required_contracts
from pyinto.realizations.registry import Composer, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings
from tests.test_construct_pipeline import run_c


def _for(source: str) -> For:
    program = PythonFrontend().parse(source)
    return next(node for node in program.body.children if isinstance(node, For))


def _sample(with_else: bool = False) -> For:
    source = "i: int = 0\nfor i in range(3):\n    print('body')\n"
    if with_else:
        source += "else:\n    print('done')\n"
    return _for(source)


def _with() -> With:
    a = Symbol("outer", ValueType(ValueKind.OBJECT), "object")
    b = Symbol("inner", ValueType(ValueKind.OBJECT), "object")
    return With(
        (ContextEntry(Reference(a)), ContextEntry(Reference(b))),
        Block((Call(Symbol("print", None), (Literal("body"),)),)),
    )


def test_for_and_with_require_distinct_control_flow_contracts() -> None:
    assert required_contracts(_sample()) == {
        "iteration.source.range",
        "loop.for.break_continue",
    }
    assert required_contracts(_sample(with_else=True)) == {
        "iteration.source.range",
        "loop.for.break_continue",
        "loop.for.normal_completion_else",
    }
    assert required_contracts(_with()) == {"context.with.enter_exit_exception"}


@pytest.mark.parametrize("with_else", [False, True])
def test_for_rejects_missing_control_flow_support_before_renderer(
    with_else: bool,
) -> None:
    visited: list[str] = []

    def rendering(_node: Construct, _ctx: object) -> str:
        visited.append("render")
        return "${body}"

    @realizes(For)
    class UncheckedFor:
        render = rendering
        supports = ("iteration.source.range",)

    @realizes(For)
    class IncompleteElseFor:
        variant = "with_else"
        render = rendering
        supports = ("iteration.source.range", "loop.for.break_continue")

    entries = (UncheckedFor, IncompleteElseFor)
    # Having break/continue support alone still cannot emit a for-else.
    checked = RealizationRegistry("unsafe", entries)
    expected = (
        "loop.for.normal_completion_else" if with_else else "loop.for.break_continue"
    )
    with pytest.raises(ConstructError, match=expected):
        Composer(checked).source(_sample(with_else=with_else))
    assert visited == []


def test_with_rejects_unchecked_context_semantics_before_renderer() -> None:
    visited: list[str] = []

    def rendering(_node: Construct, _ctx: object) -> str:
        visited.append("render")
        return "${body}"

    @realizes(With)
    class UncheckedWith:
        render = rendering

    with pytest.raises(ConstructError, match="context.with.enter_exit_exception"):
        Composer(RealizationRegistry("unsafe", (UncheckedWith,))).source(_with())
    assert visited == []


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("    if i == 2:\n        continue\n    print('hit')\n", b"hit\nhit\nelse\n"),
        ("    if i == 2:\n        break\n    print('hit')\n", b"hit\nhit\n"),
        ("    i = 99\n    print('hit')\n", b"hit\nhit\nhit\nelse\n"),
    ],
)
def test_range_for_control_flow_realized_by_c_and_python(
    body: str, expected: bytes, tmp_path: Path
) -> None:
    source = "i: int = 0\nfor i in range(3):\n" + body + "else:\n    print('else')\n"
    model = PythonFrontend().parse(source)
    code_c = realize(model, realizations=c_bindings())
    result = run_c(code_c, tmp_path)
    assert result.returncode == 0
    assert result.stdout == expected

    printed: list[str] = []
    exec(realize(model, realizations=python_bindings()), {"print": printed.append})  # noqa: S102
    assert printed == expected.decode().splitlines()


def test_empty_range_executes_else_on_both_targets(tmp_path: Path) -> None:
    program = PythonFrontend().parse(
        "i: int = 0\nfor i in range(0):\n    print('body')\nelse:\n    print('else')\n"
    )
    assert (
        run_c(realize(program, realizations=c_bindings()), tmp_path).stdout == b"else\n"
    )
    printed: list[str] = []
    exec(realize(program, realizations=python_bindings()), {"print": printed.append})  # noqa: S102
    assert printed == ["else"]


def _run_with(
    *,
    fail_enter: bool = False,
    fail_body: bool = False,
    suppress: bool = False,
) -> tuple[list[str], bool]:
    events: list[str] = []

    class Manager:
        def __init__(self, name: str, *, fail: bool = False, suppress: bool = False):
            self.name = name
            self.fail = fail
            self.suppress = suppress

        def __enter__(self) -> Self:
            events.append(f"enter:{self.name}")
            if self.fail:
                raise ValueError("enter failed")
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object,
        ) -> bool:
            events.append(
                f"exit:{self.name}:{exc_type.__name__ if exc_type else 'none'}"
            )
            return self.suppress

    def body(text: str) -> None:
        events.append(text)
        if fail_body:
            raise ValueError("body failed")

    code = realize(_with(), realizations=python_bindings())
    failed = False
    try:
        exec(  # noqa: S102 - isolated execution of Target-generated test code
            code,
            {
                "outer": Manager("outer", suppress=suppress),
                "inner": Manager("inner", fail=fail_enter),
                "print": body,
            },
        )
    except ValueError:
        failed = True
    return events, failed


@pytest.mark.parametrize(
    ("fail_enter", "fail_body", "suppress", "events", "failed"),
    [
        (
            False,
            False,
            False,
            [
                "enter:outer",
                "enter:inner",
                "body",
                "exit:inner:none",
                "exit:outer:none",
            ],
            False,
        ),
        (
            False,
            True,
            False,
            [
                "enter:outer",
                "enter:inner",
                "body",
                "exit:inner:ValueError",
                "exit:outer:ValueError",
            ],
            True,
        ),
        (
            False,
            True,
            True,
            [
                "enter:outer",
                "enter:inner",
                "body",
                "exit:inner:ValueError",
                "exit:outer:ValueError",
            ],
            False,
        ),
        (
            True,
            False,
            False,
            ["enter:outer", "enter:inner", "exit:outer:ValueError"],
            True,
        ),
    ],
)
def test_python_with_runtime_enter_exit_and_exception(
    fail_enter: bool,
    fail_body: bool,
    suppress: bool,
    events: list[str],
    failed: bool,
) -> None:
    actual, raised = _run_with(
        fail_enter=fail_enter, fail_body=fail_body, suppress=suppress
    )
    assert actual == events
    assert raised is failed


def test_standard_pack_active_pending_obligations_are_explicitly_deferred() -> None:
    # Merely registering a recipe cannot silently clear a pending obligation.
    # Operand order for Comparison is a *known risk* scheduled for iteration 23,
    # not a claim that the C recipe currently preserves it.
    for pack in (c_bindings(), python_bindings()):
        active_names = {cls.__name__ for cls, _variant in pack._recipes}
        exposed = {
            (name, obligation)
            for name in active_names
            for obligation, status in SEMANTIC_ADMISSION_STATUS.get(name, {}).items()
            if status.startswith("pending:")
        }
        assert exposed == set(STANDARD_PACK_PENDING_DEFERRED[pack.target])
        assert all(
            explanation and "第23回" in explanation
            for explanation in STANDARD_PACK_PENDING_DEFERRED[pack.target].values()
        )
