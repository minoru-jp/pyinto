"""SDD phase 14: bounded exception control-flow Model and Frontend."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Assign,
    Block,
    ConstructError,
    ExceptHandler,
    FunctionDefinition,
    Identifier,
    Literal,
    Raise,
    Reference,
    Return,
    Try,
)
from tests.support.c_realizer import c_bindings


def _has_ast(obj: object) -> bool:
    if isinstance(obj, ast.AST):
        return True
    if isinstance(obj, (list, tuple, dict)):
        values = obj.values() if isinstance(obj, dict) else obj
        return any(_has_ast(v) for v in values)
    if is_dataclass(obj) and not isinstance(obj, type):
        return any(_has_ast(getattr(obj, field.name)) for field in fields(obj))
    return False


def test_cst_027_raise_keeps_exception_tag_and_message_as_model_parts() -> None:
    value = Literal("message")
    construct = Raise("ValueError", value)
    assert construct.exception_name == "ValueError"
    assert construct.message is value
    assert construct.parts() == {
        "exception": Identifier("ValueError"),
        "message": value,
    }
    assert construct.variant() == "with_message"
    assert construct.HOLES == frozenset({"exception", "message"})
    assert not _has_ast(construct)
    assert Raise("RuntimeError").parts() == {"exception": Identifier("RuntimeError")}
    assert Raise("RuntimeError").variant() == "default"


@pytest.mark.parametrize(
    "exception_name", ["Exception", "KeyError", "BaseException", "fake", ""]
)
def test_cst_027_raise_rejects_unknown_exception_name(exception_name: str) -> None:
    with pytest.raises(ConstructError, match="Unsupported exception class"):
        Raise(exception_name)


@pytest.mark.parametrize("message", [Literal(2), "bad", Literal(1)])
def test_cst_027_raise_requires_explicit_string_type(message: object) -> None:
    with pytest.raises(ConstructError, match="string Value"):
        Raise("TypeError", message)  # type: ignore[arg-type]


def test_cst_028_handler_preserves_order_and_tag_group() -> None:
    body = Block((Raise("ValueError"),))
    handler = ExceptHandler(("TypeError", "RuntimeError"), body)
    assert handler.parts() == {
        "types": (Identifier("TypeError"), Identifier("RuntimeError")),
        "body": body,
    }
    assert handler.HOLES == frozenset({"types", "body"})
    assert not _has_ast(handler)


@pytest.mark.parametrize(
    "names",
    [(), ("KeyError",), ("ValueError", "ValueError"), ("ValueError", "Other")],
)
def test_cst_028_handler_rejects_invalid_type_sets(names: tuple[str, ...]) -> None:
    with pytest.raises(ConstructError, match="distinct supported"):
        ExceptHandler(names, Block(()))


def test_cst_028_handler_requires_block() -> None:
    with pytest.raises(ConstructError, match="requires a Block"):
        ExceptHandler(("ValueError",), Literal("bad"))  # type: ignore[arg-type]


def test_cst_029_try_is_structural_and_keeps_all_clause_order() -> None:
    body = Block((Raise("ValueError", Literal("bad")),))
    on_value_error = ExceptHandler(("ValueError",), Block(()))
    on_other = ExceptHandler(("TypeError",), Block(()))
    else_block = Block((Raise("RuntimeError"),))
    final_block = Block((Raise("TypeError"),))
    construct = Try(body, (on_value_error, on_other), else_block, final_block)
    assert construct.variant() == "handlers_finally"
    assert construct.parts() == {
        "body": body,
        "handlers": (on_value_error, on_other),
        "otherwise": else_block,
        "final": final_block,
    }
    assert construct.HOLES == frozenset({"body", "handlers", "otherwise", "final"})
    assert construct.parts()["handlers"][0] is on_value_error
    assert not _has_ast(construct)


def test_cst_029_try_finally_only_and_try_except_only() -> None:
    block = Block(())
    final_only = Try(block, finally_body=block)
    assert final_only.variant() == "finally"
    assert final_only.parts() == {"body": block, "final": block}
    handler = ExceptHandler(("ValueError",), block)
    handled = Try(block, (handler,))
    assert handled.variant() == "handlers"
    assert handled.parts() == {"body": block, "handlers": (handler,)}


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({}, "handlers or a finally"),
        ({"else_body": Block(())}, "handlers or a finally"),
        ({"handlers": (Literal(1),)}, "ExceptHandler"),
        ({"finally_body": Literal(2)}, "finally requires a Block"),
        ({"else_body": Block(()), "finally_body": Block(())}, "else requires handlers"),
    ],
)
def test_cst_029_invalid_control_structure_rejected(
    kwargs: dict[str, object], error: str
) -> None:
    with pytest.raises(ConstructError, match=error):
        Try(Block(()), **kwargs)  # type: ignore[arg-type]


def test_frt_020_try_except_else_finally_normalization() -> None:
    source = """
x: int = 0
try:
    raise ValueError("error")
except ValueError:
    x = 1
except (TypeError, RuntimeError):
    x = 2
else:
    x = 3
finally:
    x = 4
"""
    model = PythonFrontend().parse(source)
    result = model.body.children[1]
    assert isinstance(result, Try)
    assert isinstance(result.body.children[0], Raise)
    assert result.body.children[0].message == Literal("error")
    assert [h.exception_names for h in result.handlers] == [
        ("ValueError",),
        ("TypeError", "RuntimeError"),
    ]
    assert all(isinstance(h.body.children[0], Assign) for h in result.handlers)
    assert isinstance(result.else_body, Block)
    assert isinstance(result.finally_body, Block)
    assert not _has_ast(model)
    assert PythonFrontend().parse(source) == model


def test_frt_020_try_finally_with_return_keeps_nested_control_structure() -> None:
    model = PythonFrontend().parse("""
def f(x: int) -> int:
    try:
        return x
    finally:
        raise RuntimeError("failed")
""")
    definition = model.body.children[0]
    assert isinstance(definition, FunctionDefinition)
    statement = definition.body.children[0]
    assert isinstance(statement, Try)
    assert isinstance(statement.body.children[0], Return)
    assert isinstance(statement.finally_body.children[0], Raise)
    assert statement.finally_body.children[0].exception_name == "RuntimeError"


def test_frt_020_nested_try_and_branch_with_exception_contract() -> None:
    model = PythonFrontend().parse("""
x: int = 0
try:
    try:
        raise TypeError()
    except TypeError:
        x = 1
finally:
    x = 2
""")
    outer = model.body.children[1]
    assert isinstance(outer, Try)
    inner = outer.body.children[0]
    assert isinstance(inner, Try)
    assert isinstance(inner.body.children[0], Raise)
    assert inner.body.children[0].message is None
    assert outer.handlers == ()


def test_frt_020_exception_message_can_be_string_reference() -> None:
    model = PythonFrontend().parse("""
message: str = "failed"
raise RuntimeError(message)
""")
    construct = model.body.children[1]
    assert isinstance(construct, Raise)
    assert isinstance(construct.message, Reference)
    assert construct.message.symbol is model.body.children[0].symbol


def test_frt_021_try_inside_while_retains_break_continue_without_losing_depth() -> None:
    model = PythonFrontend().parse("""
x: int = 0
while x < 9:
    try:
        x = x + 1
        break
    finally:
        x = x + 1
""")
    loop = model.body.children[1]
    assert isinstance(loop.body.children[0], Try)
    assert loop.body.children[0].body.children[-1].__class__.__name__ == "Break"


@pytest.mark.parametrize(
    "source, error",
    [
        ('raise KeyError("x")', "Unsupported exception class"),
        ("raise ValueError(5)", "string Value"),
        ('raise ValueError("a", "b")', "constructor with 0 or 1"),
        ('raise ValueError(message="a")', "constructor with 0 or 1"),
        ("raise ValueError", "constructor with 0 or 1"),
        ("raise", "constructor with 0 or 1"),
        ('raise (ValueError("a")) from RuntimeError("b")', "Exception chaining"),
        ('try:\n    raise ValueError("a")\nexcept:\n    print("x")', "named types"),
        (
            'try:\n    raise ValueError("a")\nexcept ValueError as err:\n    print("x")',
            "without as-binding",
        ),
        (
            'try:\n    raise ValueError("a")\nexcept KeyError:\n    print("x")',
            "Unsupported exception class",
        ),
        (
            'try:\n    raise ValueError("a")\nexcept (ValueError, ValueError):\n    print("x")',
            "distinct supported",
        ),
        (
            'try:\n    raise ValueError("a")\nexcept* ValueError:\n    print("x")',
            "except\\*",
        ),
    ],
)
def test_frt_021_exception_syntax_rejects_unadopted_python_semantics(
    source: str, error: str
) -> None:
    with pytest.raises(UnsupportedPython, match=error):
        PythonFrontend().parse(source)


def test_frt_021_shadowed_exception_class_rejected_by_frontend() -> None:
    source = """
ValueError: int = 4
raise ValueError("a")
"""
    with pytest.raises(UnsupportedPython, match="shadowed"):
        PythonFrontend().parse(source)


def test_frt_021_shadowed_in_nested_function_rejected_even_before_initialization() -> (
    None
):
    source = """
def f() -> None:
    raise ValueError("test")
    ValueError: int = 3
"""
    with pytest.raises(UnsupportedPython, match="shadowed"):
        PythonFrontend().parse(source)


def test_frt_021_new_local_declaration_inside_try_is_rejected() -> None:
    with pytest.raises(UnsupportedPython, match="New bindings"):
        PythonFrontend().parse("""
try:
    x: int = 2
finally:
    print("done")
""")


def test_frt_021_failed_parse_does_not_contaminate_next_parse() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython):
        frontend.parse("raise CustomError()")
    model = frontend.parse('raise TypeError("hello")')
    assert isinstance(model.body.children[0], Raise)


def test_frt_021_unknown_realization_rejects_cleanly_and_preserves_model() -> None:
    model = PythonFrontend().parse("""
try:
    raise ValueError("bad")
except ValueError:
    print("handled")
""")
    snapshot = repr(model)
    with pytest.raises(ConstructError, match="No 'c' realization for Try"):
        realize(model, realizations=c_bindings())
    assert repr(model) == snapshot


def test_frt_021_return_in_except_and_raise_in_finally_are_not_evaluated() -> None:
    model = PythonFrontend().parse("""
def f() -> int:
    try:
        raise RuntimeError("x")
    except RuntimeError:
        return 10
    finally:
        raise TypeError("y")
""")
    definition = model.body.children[0]
    assert isinstance(definition, FunctionDefinition)
    construct = definition.body.children[0]
    assert isinstance(construct, Try)
    assert isinstance(construct.handlers[0].body.children[0], Return)
    assert isinstance(construct.finally_body.children[0], Raise)
