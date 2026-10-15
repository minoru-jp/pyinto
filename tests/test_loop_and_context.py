"""Loop and context-entry Constructs stay target-neutral; implementations vary."""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import fields, is_dataclass

import pytest
from shikumi_contrace import binds, upholds

from pyinto import ConstructError, PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Block,
    Break,
    Comparison,
    ContextEntry,
    Continue,
    For,
    IterationEntry,
    Literal,
    Program,
    Range,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
    While,
    With,
)
from pyinto.contracts.boundaries.pipeline import CompositionBoundary, FrontendBoundary
from pyinto.contracts.construct_contract import ConstructContract, FrontendContract
from pyinto.realizations import Composer
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings
from tests.test_construct_pipeline import run_c


def has_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, (tuple, list)):
        return any(has_ast(x) for x in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(has_ast(getattr(value, f.name)) for f in fields(value))
    return False


def run_py(source: str) -> bytes:
    program = PythonFrontend().parse(source)
    result = subprocess.run(
        [sys.executable, "-c", realize(program, realizations=python_bindings())],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@binds[FrontendBoundary](PythonFrontend)
class TestNormalization:
    @upholds(FrontendContract.parse.WhileStructure)
    def test_while_break_continue_and_normal_else(self) -> None:
        program = PythonFrontend().parse(
            "n: int = 0\nwhile n < 3:\n"
            + "    if n == 0:\n        n = 1\n        continue\n"
            "    break\nelse:\n    print('no')"
        )
        loop = program.body.children[1]
        assert isinstance(loop, While)
        assert isinstance(loop.condition, Comparison)
        assert isinstance(loop.body, Block)
        assert isinstance(loop.body.children[0].then_body.children[-1], Continue)  # type: ignore[attr-defined]
        assert isinstance(loop.body.children[1], Break)
        assert isinstance(loop.else_body, Block)
        assert not has_ast(program)

    @upholds(FrontendContract.parse.ForStructure)
    def test_for_entry_keeps_target_source_and_else(self) -> None:
        program = PythonFrontend().parse(
            "item: int = 0\nfor item in range(1, 5, 2):\n"
            + "    if item == 3:\n        break\nelse:\n    print('done')"
        )
        loop = program.body.children[1]
        assert isinstance(loop, For)
        assert isinstance(loop.entry, IterationEntry)
        assert isinstance(loop.entry.target, Reference)
        assert isinstance(loop.entry.iterable, Range)
        assert len(loop.entry.iterable.arguments) == 3
        assert isinstance(loop.else_body, Block)
        assert not has_ast(program)

    @upholds(FrontendContract.parse.WithStructure)
    def test_with_context_entries_and_body_preserved(self) -> None:
        program = PythonFrontend().parse(
            "a: object = 1\nb: object = 2\nc: object = 3\n"
            + "with a as b, c:\n    print('inside')"
        )
        node = program.body.children[3]
        assert isinstance(node, With)
        assert len(node.entries) == 2
        assert isinstance(node.entries[0], ContextEntry)
        assert isinstance(node.entries[0].target, Reference)
        assert node.entries[1].target is None
        assert isinstance(node.body, Block)
        assert not has_ast(program)
        py = realize(program, realizations=python_bindings())
        assert "with a as b, c:" in py
        assert "print('inside')" in py
        with pytest.raises(ConstructError, match="No 'c' realization for With"):
            realize(program, realizations=c_bindings())

    @upholds(FrontendContract.parse.RejectsUnknown)
    @pytest.mark.parametrize(
        "code, message",
        [
            ("break", "enclosing loop"),
            ("continue", "enclosing loop"),
            ("ctx: object = 1\nwith ctx as x:\n    pass", "prior type declaration"),
        ],
    )
    def test_missing_type_or_loop_context(self, code: str, message: str) -> None:
        with pytest.raises(UnsupportedPython, match=message):
            PythonFrontend().parse(code)


@binds[CompositionBoundary](Composer)
class TestBindingIntegration:
    @upholds(ConstructContract.WhileRealization)
    @pytest.mark.parametrize(
        "source, expected",
        [
            (
                "n: int = 0\nwhile n < 3:\n    n = 3\n    break\n"
                + "else:\n    print('unexpected')\nprint('end')",
                b"end\n",
            ),
            (
                "n: int = 0\nwhile n < 3:\n    n = 3\n    continue\n"
                + "else:\n    print('done')",
                b"done\n",
            ),
            (
                "n: int = 4\nwhile n < 3:\n    print('never')\n"
                + "else:\n    print('empty')",
                b"empty\n",
            ),
            (
                "n: int = 0\nm: int = 0\n" + "while n < 1:\n    m = 0\n"
                "    while m < 1:\n        m = 1\n        break\n"
                + "    n = 1\nelse:\n    print('outer else')",
                b"outer else\n",
            ),
        ],
    )
    def test_while_break_continue_else_on_both_targets(
        self, source: str, expected: bytes, tmp_path: object
    ) -> None:
        program = PythonFrontend().parse(source)
        assert (
            run_c(realize(program, realizations=c_bindings()), tmp_path).stdout
            == expected
        )  # type: ignore[arg-type]
        assert run_py(source) == expected

    @upholds(ConstructContract.ForRealization)
    @pytest.mark.parametrize(
        "source, expected",
        [
            (
                "i: int = 0\nfor i in range(3):\n    print('loop')\n"
                + "else:\n    print('done')",
                b"loop\nloop\nloop\ndone\n",
            ),
            (
                "i: int = 0\nfor i in range(0):\n    print('never')\n"
                + "else:\n    print('empty')",
                b"empty\n",
            ),
            (
                "i: int = 0\nfor i in range(2, 6, 2):\n"
                + "    if i == 4:\n        break\n"
                "else:\n    print('wrong')\nprint('end')",
                b"end\n",
            ),
            (
                "i: int = 0\nfor i in range(3, 0, -1):\n" + "    print('down')\n"
                "else:\n    print('end')",
                b"down\ndown\ndown\nend\n",
            ),
            (
                "i: int = 0\nfor i in range(3):\n"
                + "    if i == 1:\n        continue\n"
                "    print('seen')\nelse:\n    print('complete')",
                b"seen\nseen\ncomplete\n",
            ),
            (
                "i: int = 0\nfor i in range(3):\n" + "    i = 99\n    print('again')",
                b"again\nagain\nagain\n",
            ),
        ],
    )
    def test_c_for_range_matches_python(
        self, source: str, expected: bytes, tmp_path: object
    ) -> None:
        program = PythonFrontend().parse(source)
        assert (
            run_c(realize(program, realizations=c_bindings()), tmp_path).stdout
            == expected
        )  # type: ignore[arg-type]
        assert run_py(source) == expected

    @upholds(ConstructContract.ForRealization)
    def test_for_unrealizable_source_rejected_by_c_only(self) -> None:
        program = PythonFrontend().parse(
            "i: str = 'x'\nitems: str = 'ab'\n" + "for i in items:\n    print('ok')"
        )
        assert "for i in items:" in realize(program, realizations=python_bindings())
        with pytest.raises(
            ConstructError, match=r"iteration\.source\.(?:iterable|string)"
        ):
            realize(program, realizations=c_bindings())

    @upholds(ConstructContract.WithRealization)
    def test_python_with_executes_context_protocol(self) -> None:
        # The constructed tree doesn't need a Target-specific context manager.
        from pyinto.constructs import Call, Literal, Program, Symbol, ValueKind

        ctx = Symbol("ctx", ValueType(ValueKind.OBJECT), "object")
        result = Symbol("result", ValueType(ValueKind.OBJECT), "object")
        node = Program(
            Block(
                (
                    With(
                        (ContextEntry(Reference(ctx), Reference(result)),),
                        Block((Call(Symbol("print", None), (Literal("body"),)),)),
                    ),
                )
            )
        )
        generated = realize(node, realizations=python_bindings())
        seen: list[str] = []

        class Manager:
            def __enter__(self) -> object:
                seen.append("enter")
                return "value"

            def __exit__(self, *args: object) -> None:
                seen.append("exit")

        import contextlib
        import io

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(generated, {"ctx": Manager(), "result": None})  # noqa: S102
        assert output.getvalue() == "body\n"
        assert seen == ["enter", "exit"]


def test_nested_for_and_while_else_obey_innermost_break(tmp_path: object) -> None:
    source = (
        "outer: int = 0\nitem: int = 0\n"
        "while outer < 1:\n"
        "    for item in range(4):\n"
        "        if item == 2:\n"
        "            break\n"
        "    else:\n"
        "        print('inner completed')\n"
        "    outer = 1\n"
        "else:\n"
        "    print('outer completed')"
    )
    expected = b"outer completed\n"
    assert (
        run_c(
            realize(PythonFrontend().parse(source), realizations=c_bindings()), tmp_path
        ).stdout
        == expected
    )  # type: ignore[arg-type]
    assert run_py(source) == expected


def test_c_binding_rejects_range_step_zero_but_not_construct() -> None:
    program = PythonFrontend().parse(
        "item: int = 0\nfor item in range(0, 4, 0):\n    print('x')"
    )
    assert isinstance(program.body.children[1], For)
    assert "range(0, 4, 0)" in realize(program, realizations=python_bindings())
    with pytest.raises(ConstructError, match="zero step"):
        realize(program, realizations=c_bindings())


def test_for_with_empty_block_python_produces_pass() -> None:
    name = Symbol("item", ValueType(ValueKind.INTEGER), "int")
    program = Program(
        Block((For(IterationEntry(Reference(name), Range((Literal(2),))), Block(())),))
    )
    source = realize(program, realizations=python_bindings())
    assert "for item in range(2):\n    pass\n" == source
