"""SDD 20: executable evidence for the Construct capability inventory.

These probes lock *observed* acceptance and explicit rejection only. They do
not extend Python semantics or require Realization for newer Model nodes.
Existing CST/FRT contracts remain authoritative.
"""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    Arithmetic,
    AugAssign,
    BooleanOperation,
    Branch,
    ClassDefinition,
    ComparisonChain,
    DictValue,
    For,
    FunctionDefinition,
    FunctionValueCall,
    Initialize,
    InstanceCreation,
    ListValue,
    MethodCall,
    MethodDispatch,
    Raise,
    Return,
    Try,
    TupleValue,
    With,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


@pytest.mark.parametrize(
    ("source", "expected_type"),
    [
        ("n: int = 1 + 2 * 3", Arithmetic),
        ("n: int = 1\nn += 2", AugAssign),
        ("flag: bool = 1 < 2 < 3", ComparisonChain),
        ("b: bool = (1 < 2) and (3 < 4)", BooleanOperation),
        ("if 1 < 2:\n    print('ok')", Branch),
        ("i: int = 0\nfor i in range(3):\n    print('ok')", For),
        ("slot: int = 0\nwith 1 as slot:\n    print('ok')", With),
        ("try:\n    raise ValueError('no')\nexcept ValueError:\n    print('ok')", Try),
        ("def f(n: int) -> int:\n    return n", FunctionDefinition),
        ("pair: tuple[int, str] = (1, 'a')", TupleValue),
        ("xs: list[int] = [1, 2]", ListValue),
        ("d: dict[str, int] = {'a': 1}", DictValue),
        (
            "class Point:\n    def __init__(self, n: int) -> None:\n        self.n: int = n\n",
            ClassDefinition,
        ),
    ],
)
def test_existing_frontend_normalization_is_still_available(
    source: str, expected_type: type[object]
) -> None:
    """The inventory does not reinterpret or remove existing capabilities."""
    program = PythonFrontend().parse(source)
    last = program.body.children[-1]
    if isinstance(last, Initialize):
        assert isinstance(last.value, expected_type)
    else:
        assert isinstance(last, expected_type)


def test_existing_return_and_exception_nodes_remain_explicit() -> None:
    program = PythonFrontend().parse(
        "def f(n: int) -> int:\n"
        "    if n < 0:\n"
        "        raise ValueError('negative')\n"
        "    return n\n"
    )
    function = program.body.children[0]
    assert isinstance(function, FunctionDefinition)
    assert isinstance(function.body.children[0], Branch)
    assert isinstance(function.body.children[0].then_body.children[0], Raise)
    assert isinstance(function.body.children[1], Return)


def test_existing_indirect_call_and_virtual_dispatch_remain_distinct() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def ident(n: int) -> int:\n"
        "    return n\n"
        "f: Callable[[int], int] = ident\n"
        "v: int = f(3)\n"
        "class Base:\n"
        "    def __init__(self) -> None:\n"
        "        self.n: int = 1\n"
        "    def read(self) -> int:\n"
        "        return self.n\n"
        "b: Base = Base()\n"
        "w: int = b.read()\n"
    )
    assert isinstance(program.body.children[2].value, FunctionValueCall)
    assert isinstance(program.body.children[-2].value, InstanceCreation)
    virtual = program.body.children[-1].value
    assert isinstance(virtual, MethodCall)
    assert virtual.dispatch is MethodDispatch.VIRTUAL


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [
        ("n: float = 1", "Annotated type"),
        ("n: int = 9 / 3", "Annotated type does not match"),
        ("n: int = 2 ** 3", "Unsupported arithmetic operator"),
        ("flag: bool = 'a' == 2", "Comparison requires matching"),
        ("assert 1 < 2", "Unsupported statement"),
        (
            "x: int = 3\nmatch x:\n    case 3:\n        pass",
            "Unsupported statement",
        ),
        (
            "from typing import Callable\nf: object = lambda n: n + 1",
            "explicit Callable",
        ),
        ("xs: list[int] = [n for n in [1, 2]]", "Unsupported expression"),
        (
            "mapping: dict[str, int] = {str(n): n for n in [1, 2]}",
            "Unsupported expression",
        ),
        ("xs: list[int] = [1, 2]\nn: int = len(7)", "Length requires"),
        (
            "def f(n: int) -> int:\n    return n\nx: int = f(m=1)",
            "Unknown keyword argument",
        ),
        (
            "x: tuple[int, int] = (1, 2)\na, b = x",
            "Unpack assignment requires declared targets",
        ),
        (
            "x: tuple[int, int] = (1, 2)\ni: int = 0\nn: int = x[i]",
            "nonnegative static integer index",
        ),
        (
            "xs: list[int] = [1]\nxs.append(2)",
            "Unregistered interface mapping object",
        ),
        (
            "if 1 < 2:\n    def f() -> int:\n        return 1",
            "Function definitions in control-flow blocks",
        ),
        ("n: int = 0\nif 1 < 2:\n    m: int = 1\nprint(m)", "Unresolved name"),
    ],
)
def test_currently_unadopted_features_are_not_silently_accepted(
    source: str, diagnostic: str
) -> None:
    with pytest.raises(UnsupportedPython, match=diagnostic):
        PythonFrontend().parse(source)
