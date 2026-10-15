"""Explicit typing, AST normalization and independent C/Python execution."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest
from shikumi_contrace import binds, upholds

from pyinto import ConstructError, PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Assign,
    Block,
    Branch,
    Call,
    Comparison,
    Initialize,
    Literal,
    Program,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
    While,
)
from pyinto.contracts.boundaries.pipeline import CompositionBoundary, FrontendBoundary
from pyinto.contracts.construct_contract import ConstructContract, FrontendContract
from pyinto.realizations import Composer
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings

CC = shutil.which("gcc") or shutil.which("clang")


def run_c(source: str, tmp_path: Path) -> subprocess.CompletedProcess[bytes]:
    if CC is None:
        pytest.skip("No C compiler installed")
    file = tmp_path / "main.c"
    binary = tmp_path / "main"
    file.write_text(source, encoding="utf-8")
    build = subprocess.run(
        [
            CC,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            str(file),
            "-o",
            str(binary),
        ],
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr.decode(errors="replace")
    return subprocess.run([str(binary)], capture_output=True, check=False)


def contains_ast(obj: object) -> bool:
    if isinstance(obj, ast.AST):
        return True
    if isinstance(obj, (list, tuple)):
        return any(contains_ast(item) for item in obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return any(contains_ast(getattr(obj, f.name)) for f in fields(obj))
    return False


@binds[FrontendBoundary](PythonFrontend)
class TestFrontend:
    @upholds(FrontendContract.parse.TypedNames)
    @pytest.mark.parametrize(
        "code", ["n = 1", "n: int = 1\nm = n", "n: int", "n: int = 1\nn: int = 2"]
    )
    def test_annotation_required(self, code: str) -> None:
        with pytest.raises(
            UnsupportedPython, match="annotation|requires|already declared"
        ):
            PythonFrontend().parse(code)

    @upholds(FrontendContract.parse.TargetNeutral)
    def test_normalizes_nested_structure_without_ast(self) -> None:
        program = PythonFrontend().parse(
            'n: int = 1\nif n > 0:\n    print("yes")\nelse:\n    print("no")'
        )
        initial, branch = program.body.children
        assert isinstance(initial, Initialize)
        assert isinstance(branch, Branch)
        assert isinstance(branch.condition, Comparison)
        assert isinstance(branch.condition.left, Reference)
        assert branch.condition.left.symbol is initial.symbol
        assert isinstance(branch.then_body.children[0], Call)
        assert not contains_ast(program)

    @upholds(FrontendContract.parse.TypedNames)
    def test_reassignment_preserves_explicit_type(self) -> None:
        p = PythonFrontend().parse("n: int = 1\nn = 3")
        assert isinstance(p.body.children[0], Initialize)
        assert isinstance(p.body.children[1], Assign)

    @upholds(FrontendContract.parse.RejectsUnknown)
    @pytest.mark.parametrize(
        "source, message",
        [
            ("n: int = 'wrong'", "Annotated type"),
            ("n: int = 1\nn = 'wrong'", "cannot change"),
            ("n: int = 1\nif n > 0:\n    k: int = 5\nprint(k)", "Unresolved name"),
            ("n: int = 1\nif n:\n    print('x')", "If requires"),
            ("n: int = 1\nwhile n:\n    print('x')", "While requires"),
            ("n: int = 1\nwhile n > 0:\n    k: int = 5\nprint(k)", "Unresolved name"),
            ("n: int = 1\nwhile n > 0:\n    k = 5", "annotation"),
            (
                "n: int = 1\nif 0 < n is 3:\n    print('x')",
                "Unsupported chained comparison operator",
            ),
            ("n: int = 1\nif n is 1:\n    print('x')", "Unsupported comparison"),
            ("n: float = 1", "Annotated type"),
            ("n: int = missing", "Unresolved name"),
            ("n: int = 1.5", "Annotated type"),
            ("n: int = True", "Annotated type"),
            ("x: int = 1\ny: str = x", "Annotated type"),
            (
                "from math import sqrt\nn: int = 1",
                "Unregistered interface mapping import",
            ),
        ],
    )
    def test_rejects_unmodelled_python(self, source: str, message: str) -> None:
        with pytest.raises(UnsupportedPython, match=message) as error:
            PythonFrontend().parse(source)
        assert "line " in str(error.value)

    @upholds(FrontendContract.parse.WhileStructure)
    def test_while_entry_is_structural_and_else_is_a_block(self) -> None:
        program = PythonFrontend().parse(
            'n: int = 0\nwhile n < 3:\n    n = 3\nelse:\n    print("done")'
        )
        initial, loop = program.body.children
        assert isinstance(initial, Initialize)
        assert isinstance(loop, While)
        assert isinstance(loop.condition, Comparison)
        assert isinstance(loop.condition.left, Reference)
        assert loop.condition.left.symbol is initial.symbol
        assert isinstance(loop.body, Block)
        assert isinstance(loop.body.children[0], Assign)
        assert isinstance(loop.else_body, Block)
        assert isinstance(loop.else_body.children[0], Call)
        assert loop.variant() == "with_else"
        assert loop.parts()["condition"] is loop.condition
        assert loop.parts()["body"] is loop.body
        assert loop.parts()["otherwise"] is loop.else_body
        assert not contains_ast(program)


@binds[CompositionBoundary](Composer)
class TestProgram:
    @upholds(ConstructContract.source.Compiles)
    @pytest.mark.parametrize(
        "code, expected",
        [
            ('n: int = 1\nif n > 0:\n    print("yes")', b"yes\n"),
            ('n: int = 0\nif n > 0:\n    print("wrong")', b""),
            (
                'n: int = 0\nif n > 0:\n    print("wrong")\nelse:\n    print("ok")',
                b"ok\n",
            ),
            (
                'n: int = 2\nif n > 0:\n    if n == 2:\n        print("nested")',
                b"nested\n",
            ),
            ('n: int = 4\nn = -1\nif n < 0:\n    print("negative")', b"negative\n"),
            ('print("héllo")', "héllo\n".encode()),
            (
                (
                    'n: int = 0\nwhile n < 2:\n    print("tick")\n'
                    "    if n == 0:\n        n = 1\n    else:\n        n = 2"
                ),
                b"tick\ntick\n",
            ),
            ('n: int = 2\nwhile n < 2:\n    print("never")', b""),
            (
                (
                    'n: int = 2\nwhile n < 2:\n    print("never")\n'
                    'else:\n    print("complete")'
                ),
                b"complete\n",
            ),
            (
                (
                    'n: int = 0\nwhile n < 2:\n    print("once")\n    n = 2\n'
                    'else:\n    print("done")'
                ),
                b"once\ndone\n",
            ),
            (
                (
                    "n: int = 0\nwhile n < 1:\n"
                    '    if n == 0:\n        print("inside")\n    n = 1'
                ),
                b"inside\n",
            ),
        ],
    )
    def test_c_compiles(self, code: str, expected: bytes, tmp_path: Path) -> None:
        result = run_c(
            realize(PythonFrontend().parse(code), realizations=c_bindings()), tmp_path
        )
        assert result.returncode == 0
        assert result.stdout == expected

    @upholds(ConstructContract.TargetIsolation)
    @pytest.mark.parametrize(
        "code, expected",
        [
            ('n: int = 1\nif n > 0:\n    print("ok")', b"ok\n"),
            (
                'n: int = 0\nif n > 0:\n    print("wrong")\nelse:\n    print("else")',
                b"else\n",
            ),
            (
                (
                    'n: int = 0\nwhile n < 2:\n    print("tick")\n'
                    "    if n == 0:\n        n = 1\n    else:\n        n = 2\n"
                    'else:\n    print("done")'
                ),
                b"tick\ntick\ndone\n",
            ),
        ],
    )
    def test_python_binding_executes(self, code: str, expected: bytes) -> None:
        program = PythonFrontend().parse(code)
        produced = realize(program, realizations=python_bindings())
        result = subprocess.run(
            [sys.executable, "-c", produced], capture_output=True, check=False
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected

    @upholds(ConstructContract.PureStructure)
    def test_normalized_nodes_have_no_emit_or_expression(self) -> None:
        nodes = Program(
            Block(
                (
                    Initialize(
                        Symbol("x", ValueType(ValueKind.INTEGER), "int"), Literal(3)
                    ),
                )
            )
        )
        assert not hasattr(nodes, "emit")
        assert not hasattr(Literal(2), "expression")
        assert nodes.body.children[0].parts()["value"] == Literal(3)

    @upholds(ConstructContract.source.Compiles)
    def test_manual_construct_tree_compiles(self, tmp_path: Path) -> None:
        symbol = Symbol("x", ValueType(ValueKind.INTEGER), "int")
        program = Program(
            Block(
                (
                    Initialize(symbol, Literal(2)),
                    Branch(
                        Comparison(Reference(symbol), "==", Literal(2)),
                        Block((Call(Symbol("print", None), (Literal("manual"),)),)),
                    ),
                )
            )
        )
        assert (
            run_c(realize(program, realizations=c_bindings()), tmp_path).stdout
            == b"manual\n"
        )

    @upholds(ConstructContract.WhileRealization)
    def test_nested_while_is_composed_without_custom_composer_logic(
        self, tmp_path: Path
    ) -> None:
        source = (
            "outer: int = 0\ninner: int = 0\n"
            "while outer < 1:\n    inner = 0\n"
            '    while inner < 1:\n        print("inner")\n        inner = 1\n'
            '    outer = 1\nelse:\n    print("outer done")'
        )
        program = PythonFrontend().parse(source)
        c_source = realize(program, realizations=c_bindings())
        assert "for (; (outer < 1LL);" in c_source
        assert "while ((inner < 1LL))" in c_source
        assert run_c(c_source, tmp_path).stdout == b"inner\nouter done\n"
        py_source = realize(program, realizations=python_bindings())
        result = subprocess.run(
            [sys.executable, "-c", py_source], capture_output=True, check=False
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == b"inner\nouter done\n"


def test_invalid_c_names_rejected_by_target_only() -> None:
    program = PythonFrontend().parse("int: int = 5")
    with pytest.raises(ConstructError, match="not portable to C"):
        realize(program, realizations=c_bindings())


def test_literal_target_limits_are_checked_at_rendering() -> None:
    with pytest.raises(ConstructError, match="64-bit"):
        realize(PythonFrontend().parse(f"n: int = {2**63}"), realizations=c_bindings())
    with pytest.raises(ConstructError, match="NUL"):
        realize(PythonFrontend().parse('print("\\x00")'), realizations=c_bindings())


def test_any_and_object_do_not_force_inference() -> None:
    for annotation in ("Any", "object"):
        program = PythonFrontend().parse(
            ("from typing import Any\n" if annotation == "Any" else "")
            + f"x: {annotation} = 1"
        )
        assert realize(program, realizations=python_bindings()) == "x = 1\n"
        with pytest.raises(ConstructError, match="type representation"):
            realize(program, realizations=c_bindings())


def test_symbols_must_always_have_explicit_types() -> None:
    with pytest.raises(ValueError, match="explicit type annotation"):
        Symbol("x", ValueType(ValueKind.INTEGER))
    assert Symbol("print", None).annotation is None
