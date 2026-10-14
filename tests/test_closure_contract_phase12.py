"""Phase 12: verify lexical capture provenance without creating Closure nodes."""

from __future__ import annotations

from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.analysis import lexical_captures
from pyinto.constructs import (
    Arithmetic,
    Assign,
    Block,
    FunctionCall,
    FunctionDefinition,
    FunctionValueCall,
    Literal,
    Reference,
    ValueKind,
)
from tests.support.c_realizer import c_bindings


def parse(source: str) -> tuple[object, ...]:
    return PythonFrontend().parse(source).body.children


def test_cst_023_capture_of_parameter_preserves_declaration_identity() -> None:
    (factory,) = parse(
        "from typing import Callable\n"
        "def factory(n: int) -> Callable[[], int]:\n"
        "    def get() -> int:\n        return n\n"
        "    return get\n"
    )
    get, returned = factory.body.children
    param = factory.signature.parameters[0]
    assert isinstance(get, FunctionDefinition)
    assert lexical_captures(factory) == ()
    captures = lexical_captures(get)
    assert len(captures) == 1 and captures[0] is param
    assert get.body.children[0].value.symbol is captures[0]
    assert returned.value.symbol is get.signature.value_symbol
    assert lexical_captures(get)[0] is captures[0]


def test_cst_023_captures_are_first_use_order_unique_and_read_only() -> None:
    (outer,) = parse(
        "from typing import Callable\n"
        "def outer(a: int, b: int) -> Callable[[], int]:\n"
        "    def inner() -> int:\n"
        "        return b + a + b\n"
        "    return inner\n"
    )
    inner = outer.body.children[0]
    body_before = inner.body
    refs_before = inner.body.children[0].value
    assert isinstance(refs_before, Arithmetic)
    captures = lexical_captures(inner)
    assert captures == (outer.signature.parameters[1], outer.signature.parameters[0])
    assert captures[0] is outer.signature.parameters[1]
    assert captures[1] is outer.signature.parameters[0]
    assert inner.body is body_before
    assert inner.body.children[0].value is refs_before


def test_cst_023_each_nested_body_has_own_capture_set() -> None:
    (outer,) = parse(
        "from typing import Callable\n"
        "def outer(n: int) -> Callable[[], Callable[[], int]]:\n"
        "    def middle() -> Callable[[], int]:\n"
        "        def inner() -> int:\n"
        "            return n\n"
        "        return inner\n"
        "    return middle\n"
    )
    middle = outer.body.children[0]
    inner = middle.body.children[0]
    assert lexical_captures(outer) == ()
    assert lexical_captures(middle) == ()  # Descendant's capture is NOT direct.
    assert lexical_captures(inner) == (outer.signature.parameters[0],)
    assert inner.signature.scope == ("outer", "middle")
    assert inner.body.children[0].value.symbol.scope == ("outer",)
    # A Target may need transitive environment retention; no runtime frame is
    # constructed or inferred by this *direct* capture projection.


def test_cst_023_direct_call_to_outer_nested_sibling_is_a_dependency() -> None:
    (outer,) = parse(
        "def outer(n: int) -> int:\n"
        "    def sibling(x: int) -> int:\n        return x + n\n"
        "    def caller() -> int:\n        return sibling(3)\n"
        "    return caller()\n"
    )
    sibling, caller, returned = outer.body.children
    call = caller.body.children[0].value
    assert isinstance(call, FunctionCall)
    assert call.signature is sibling.signature
    assert lexical_captures(caller) == (sibling.signature.value_symbol,)
    assert lexical_captures(sibling) == (outer.signature.parameters[0],)
    assert lexical_captures(outer) == ()
    assert returned.value.signature is caller.signature


def test_cst_023_function_value_reference_to_sibling_is_a_dependency() -> None:
    (outer,) = parse(
        "from typing import Callable\n"
        "def outer(n: int) -> Callable[[], int]:\n"
        "    def sibling() -> int:\n        return n\n"
        "    def chooser() -> Callable[[], int]:\n        return sibling\n"
        "    return chooser()\n"
    )
    sibling, chooser, _ = outer.body.children
    returned = chooser.body.children[0]
    assert returned.value.symbol is sibling.signature.value_symbol
    assert lexical_captures(chooser) == (sibling.signature.value_symbol,)
    assert lexical_captures(sibling) == (outer.signature.parameters[0],)


def test_cst_023_function_typed_outer_parameter_captured_by_indirect_call() -> None:
    (outer,) = parse(
        "from typing import Callable\n"
        "def outer(fn: Callable[[int], int], x: int) -> int:\n"
        "    def inner() -> int:\n        return fn(x)\n"
        "    return inner()\n"
    )
    inner = outer.body.children[0]
    returned = inner.body.children[0]
    assert isinstance(returned.value, FunctionValueCall)
    assert isinstance(returned.value.callee, Reference)
    assert lexical_captures(inner) == outer.signature.parameters
    assert lexical_captures(inner)[0].kind is ValueKind.FUNCTION


def test_cst_023_local_symbol_and_own_recursion_not_captured() -> None:
    (outer,) = parse(
        "def outer(n: int) -> int:\n"
        "    def rec(x: int) -> int:\n"
        "        local: int = x\n"
        "        return rec(local)\n"
        "    return rec(n)\n"
    )
    rec = outer.body.children[0]
    call = rec.body.children[1].value
    assert isinstance(call, FunctionCall)
    assert call.signature is rec.signature
    assert lexical_captures(rec) == ()


def test_cst_023_module_level_symbol_and_function_not_captured() -> None:
    outside, helper, outer = parse(
        "outside: int = 3\n"
        "def helper(x: int) -> int:\n    return x\n"
        "def outer(n: int) -> int:\n"
        "    def inner() -> int:\n        return helper(outside) + n\n"
        "    return inner()\n"
    )
    inner = outer.body.children[0]
    result = lexical_captures(inner)
    assert result == (outer.signature.parameters[0],)
    assert outside.symbol.scope == ()
    assert helper.signature.scope == ()


def test_cst_023_mutated_outer_binding_preserves_capture_identity() -> None:
    (outer,) = parse(
        "from typing import Callable\n"
        "def outer(n: int) -> Callable[[], int]:\n"
        "    def get() -> int:\n        return n\n"
        "    n = n + 1\n"
        "    return get\n"
    )
    get, write, _ = outer.body.children
    assert isinstance(write, Assign)
    assert lexical_captures(get)[0] is write.target.symbol
    assert lexical_captures(get)[0] is outer.signature.parameters[0]
    # Value/reference semantics are part of the closure contract; *storage*
    # and timing are not encoded as a precomputed literal.


def test_frt_017_independent_factory_invocations_keep_distinct_call_sites() -> None:
    factory, a, b, first, second = parse(
        "from typing import Callable\n"
        "def factory(n: int) -> Callable[[], int]:\n"
        "    def get() -> int:\n        return n\n"
        "    return get\n"
        "a: Callable[[], int] = factory(1)\n"
        "b: Callable[[], int] = factory(2)\n"
        "first: int = a()\n"
        "second: int = b()\n"
    )
    get = factory.body.children[0]
    assert lexical_captures(get) == (factory.signature.parameters[0],)
    assert a.value.signature is b.value.signature is factory.signature
    assert a.value is not b.value
    assert a.value.arguments == (Literal(1),)
    assert b.value.arguments == (Literal(2),)
    assert isinstance(first.value, FunctionValueCall)
    assert isinstance(second.value, FunctionValueCall)
    assert first.value.callee.symbol is a.symbol
    assert second.value.callee.symbol is b.symbol
    assert first.value.callee.symbol is not second.value.callee.symbol
    # This is *static provenance*, not proof of two runtime environments.


def test_frt_017_closure_value_can_pass_through_typed_parameter() -> None:
    accept, factory, created, result = parse(
        "from typing import Callable\n"
        "def accept(fn: Callable[[], int]) -> int:\n    return fn()\n"
        "def factory(n: int) -> Callable[[], int]:\n"
        "    def inner() -> int:\n        return n\n"
        "    return inner\n"
        "created: Callable[[], int] = factory(5)\n"
        "result: int = accept(created)\n"
    )
    inner = factory.body.children[0]
    assert isinstance(result.value, FunctionCall)
    assert isinstance(result.value.arguments[0], Reference)
    assert result.value.arguments[0].symbol is created.symbol
    assert lexical_captures(inner) == (factory.signature.parameters[0],)
    assert lexical_captures(accept) == ()


def test_frt_017_shadowed_lexical_bindings_remain_distinct() -> None:
    (outer,) = parse(
        "def outer(n: int) -> int:\n"
        "    def middle(n: int) -> int:\n"
        "        def inner() -> int:\n            return n\n"
        "        return inner()\n"
        "    return middle(n)\n"
    )
    middle = outer.body.children[0]
    inner = middle.body.children[0]
    assert middle.signature.parameters[0].name == outer.signature.parameters[0].name
    assert middle.signature.parameters[0].scope == ("outer", "middle")
    assert outer.signature.parameters[0].scope == ("outer",)
    assert lexical_captures(inner) == (middle.signature.parameters[0],)
    assert lexical_captures(inner)[0] is not outer.signature.parameters[0]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            (
                "from typing import Callable\n"
                "def outer(n: int) -> Callable[[], int]:\n"
                "    def inner() -> int:\n        return n\n"
                "    nonlocal n\n    return inner\n"
            ),
            "Unsupported statement",
        ),
        (
            (
                "from typing import Callable\n"
                "def outer(n: int) -> Callable[[], int]:\n"
                "    def inner() -> int:\n"
                "        nonlocal n\n        return n\n"
                "    return inner\n"
            ),
            "Unsupported statement",
        ),
        (
            (
                "def outer(n: int) -> int:\n"
                "    def inner() -> int:\n        return n\n"
                "    inner.wrapped = 1\n"
                "    return 0\n"
            ),
            "Only simple name assignments",
        ),
        (
            (
                "def outer(n: int) -> int:\n"
                "    def inner() -> int:\n"
                "        return later\n"
                "    later: int = n\n"
                "    return inner()\n"
            ),
            "Unresolved name",
        ),
    ],
)
def test_frt_017_does_not_guess_unsupported_closure_semantics(
    source: str, message: str
) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend().parse(source)


def test_frt_017_target_realization_still_rejects_unregistered_functions() -> None:
    root = PythonFrontend().parse(
        "from typing import Callable\n"
        "def outer(n: int) -> Callable[[], int]:\n"
        "    def inner() -> int:\n        return n\n"
        "    return inner\n"
    )
    with pytest.raises(
        Exception, match="(?i)no|unregistered|missing|binding|realization"
    ):
        realize(root, realizations=c_bindings())


def test_cst_023_manual_and_repeated_analysis_have_no_side_effects() -> None:
    (outer,) = parse(
        "def outer(x: int) -> int:\n"
        "    def inner() -> int:\n        return x\n"
        "    return inner()\n"
    )
    inner = outer.body.children[0]
    shape = repr(outer)
    first = lexical_captures(inner)
    second = lexical_captures(inner)
    assert first == second
    assert first[0] is second[0]
    assert repr(outer) == shape
    assert all(is_dataclass(s) for s in first)
    assert all(any(f.name == "scope" for f in fields(s)) for s in first)
    assert isinstance(inner.body, Block)
    with pytest.raises(TypeError, match="FunctionDefinition"):
        lexical_captures(outer.body)  # type: ignore[arg-type]


def test_cst_023_captures_distinguish_same_named_functions_by_owner() -> None:
    outer1, outer2 = parse(
        "def outer1(n: int) -> int:\n"
        "    def helper() -> int:\n        return n\n"
        "    return helper()\n"
        "def outer2(n: int) -> int:\n"
        "    def helper() -> int:\n        return n\n"
        "    return helper()\n"
    )
    h1 = outer1.body.children[0]
    h2 = outer2.body.children[0]
    assert h1.signature.name == h2.signature.name
    assert h1.signature.scope != h2.signature.scope
    assert lexical_captures(h1)[0] is outer1.signature.parameters[0]
    assert lexical_captures(h2)[0] is outer2.signature.parameters[0]
    assert lexical_captures(h1)[0] is not lexical_captures(h2)[0]
