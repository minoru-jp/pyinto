"""Iteration 27: Target-neutral typed intrinsic providers, without inference."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError

import pytest

from pyinto import convert, realize
from pyinto.constructs import (
    ConstructError,
    Initialize,
    IntrinsicCall,
    IntrinsicDefinition,
    ListType,
    Literal,
    MethodCall,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION, required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.intrinsics import IntrinsicRegistry
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings

_STR = ValueType(ValueKind.STRING)
_INT = ValueType(ValueKind.INTEGER)
_BOOL = ValueType(ValueKind.BOOLEAN)
_UPPER = IntrinsicDefinition("upper", _STR, (), _STR)
_JOIN = IntrinsicDefinition(
    "typed_join", None, (_STR, _STR), _STR, frozenset({"intrinsic.effects.new_string"})
)
_SUCC = IntrinsicDefinition("success", None, (_STR,), _BOOL)
_REGISTRY = IntrinsicRegistry((_UPPER, _JOIN, _SUCC))


def _value(source: str, registry: IntrinsicRegistry = _REGISTRY) -> IntrinsicCall:
    item = PythonFrontend(intrinsics=registry).parse(source).body.children[-1]
    assert isinstance(item, Initialize)
    assert isinstance(item.value, IntrinsicCall)
    return item.value


def test_statistically_resolved_method_and_call_have_typed_model_parts() -> None:
    value = _value('s: str = "hi"\nx: str = s.upper()')
    assert value.definition is _UPPER
    assert value.variant() == "intrinsic.str.upper"
    assert value.value_type == _STR
    assert value.receiver is not None and value.receiver.value_type == _STR
    assert tuple(value.parts()) == ("receiver",)
    assert required_contracts(value) == {
        "intrinsic.str.upper",
        "intrinsic.receiver_once",
    }
    with pytest.raises(FrozenInstanceError):
        value.receiver = Literal("oops")  # type: ignore[misc]
    literal = _value('x: str = "Hi".upper()')
    assert literal.receiver == Literal("Hi")


def test_global_operation_has_explicit_semantics_and_evaluation_order() -> None:
    call = _value('x: str = typed_join("a", "b")')
    assert call.definition is _JOIN
    assert call.receiver is None
    assert call.parts() == {"arg0": Literal("a"), "arg1": Literal("b")}
    assert call.accepts_part_name("arg0")
    assert not call.accepts_part_name("arg00")
    assert call.variant() == "intrinsic.global.typed_join"
    assert required_contracts(call) == {
        "intrinsic.global.typed_join",
        "intrinsic.effects.new_string",
        "intrinsic.arguments.once",
        "call.arguments.left_to_right",
    }
    nested = _value('x: str = typed_join("x", "y".upper())')
    assert isinstance(nested.arguments[1], IntrinsicCall)
    assert nested.arguments[1].definition is _UPPER


def test_source_receiver_that_is_a_call_is_normalized_once(monkeypatch) -> None:
    from pyinto.frontend.expressions import ExpressionNormalizer

    original = ExpressionNormalizer._value
    visited: list[ast.AST] = []

    def counted(self, node: ast.expr, expected=None):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "make"
        ):
            visited.append(node)
        return original(self, node, expected)

    monkeypatch.setattr(ExpressionNormalizer, "_value", counted)
    value = _value('def make() -> str:\n    return "hi"\nx: str = make().upper()')
    assert value.definition is _UPPER
    assert len(visited) == 1


def test_receiver_precedes_arguments_and_is_not_duplicated() -> None:
    operation = IntrinsicDefinition("surround", _STR, (_STR, _STR), _STR)
    call = IntrinsicCall(operation, Literal("mid"), (Literal("<"), Literal(">")))
    assert tuple(call.parts()) == ("receiver", "arg0", "arg1")
    assert required_contracts(call) == {
        "intrinsic.str.surround",
        "intrinsic.receiver_once",
        "intrinsic.receiver_before_arguments",
        "intrinsic.arguments.once",
        "call.arguments.left_to_right",
    }


def test_structural_return_type_is_declared_not_inferred() -> None:
    declared_list = ValueType(ValueKind.LIST, list_type=ListType(_INT))
    definition = IntrinsicDefinition("singleton", None, (_INT,), declared_list)
    value = _value("xs: list[int] = singleton(10)", IntrinsicRegistry((definition,)))
    assert value.value_type is declared_list
    assert value.list_type == ListType(_INT)
    with pytest.raises(UnsupportedPython, match="Annotated type does not match"):
        PythonFrontend(intrinsics=IntrinsicRegistry((definition,))).parse(
            "bad: list[str] = singleton(10)"
        )


def test_declared_class_method_takes_priority_over_intrinsic_name() -> None:
    model = PythonFrontend(intrinsics=_REGISTRY).parse(
        "class Echo:\n"
        "    def __init__(self) -> None:\n"
        "        pass\n"
        "    def upper(self) -> str:\n"
        "        return 'OK'\n"
        "item: Echo = Echo()\n"
        "out: str = item.upper()\n"
    )
    value = model.body.children[-1]
    assert isinstance(value, Initialize)
    assert isinstance(value.value, MethodCall)


def test_exact_static_signature_validation_has_no_implicit_conversions() -> None:
    with pytest.raises(ConstructError, match="receiver presence"):
        IntrinsicCall(_UPPER, None, ())
    with pytest.raises(ConstructError, match="receiver type"):
        IntrinsicCall(_UPPER, Literal(2), ())
    with pytest.raises(ConstructError, match="arity"):
        IntrinsicCall(_JOIN, None, (Literal("a"),))
    with pytest.raises(ConstructError, match="argument type"):
        IntrinsicCall(_JOIN, None, (Literal("a"), Literal(4)))
    with pytest.raises(ConstructError, match="receiver presence"):
        IntrinsicCall(_JOIN, Literal("a"), (Literal("b"), Literal("c")))


@pytest.mark.parametrize(
    ("definition", "message"),
    [
        (lambda: IntrinsicDefinition("bad.name", None, (), _INT), "identifier"),
        (lambda: IntrinsicDefinition("nope", None, (_INT, _STR), "int"), "return"),  # type: ignore[arg-type]
        (
            lambda: IntrinsicDefinition("nope", ValueType(ValueKind.ANY), (), _INT),
            "receiver",
        ),
        (
            lambda: IntrinsicDefinition(
                "nope", None, (ValueType(ValueKind.NONE),), _INT
            ),
            "arguments",
        ),
        (
            lambda: IntrinsicDefinition(
                "nope", None, (), _INT, frozenset({"other.anything"})
            ),
            "obligations",
        ),
        (
            lambda: IntrinsicDefinition(
                "nope", None, (), _INT, frozenset({"intrinsic.foo.*"})
            ),
            "obligations",
        ),
    ],
)
def test_definition_must_declare_static_supported_shapes(
    definition, message: str
) -> None:
    with pytest.raises(ConstructError, match=message):
        definition()


def test_registry_is_immutable_unique_and_provider_owned() -> None:
    assert _REGISTRY.global_call("typed_join") is _JOIN
    assert _REGISTRY.method("upper", _STR) is _UPPER
    assert _REGISTRY.method("upper", _INT) is None
    assert _REGISTRY.has_method_name("upper")
    assert not _REGISTRY.has_method_name("unknown")
    with pytest.raises(ValueError, match="Duplicate"):
        IntrinsicRegistry((_UPPER, _UPPER))
    for special in ("range", "super"):
        with pytest.raises(ValueError, match="special syntax"):
            IntrinsicRegistry((IntrinsicDefinition(special, None, (), _INT),))
    with pytest.raises(ConstructError, match="Duplicate"):
        _REGISTRY.extend((_UPPER,))
    extended = _REGISTRY.extend((IntrinsicDefinition("next", None, (), _INT),))
    assert extended.global_call("next") is not None
    assert _REGISTRY.global_call("next") is None
    # Multiple concrete signatures now intentionally share one operation key.
    declarations = tuple(
        IntrinsicDefinition(
            "put",
            ValueType(ValueKind.LIST, list_type=ListType(element)),
            (element,),
            ValueType(ValueKind.NONE),
        )
        for element in (_STR, _INT)
    )
    assert all(d.key == "intrinsic.list.put" for d in declarations)
    overloads = IntrinsicRegistry(declarations)
    assert len(overloads.definitions) == 2
    with pytest.raises(ValueError, match="Duplicate intrinsic signature"):
        IntrinsicRegistry((*declarations, declarations[0]))


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ('x: str = "hi".upper(4)', "arity"),
        ('x: str = "hi".upper(new=1)', "positional"),
        ('x: str = typed_join("hi")', "arity"),
        ('x: str = typed_join("hi", 9)', "type mismatch"),
        ('x: str = typed_join(left="hi", right="world")', "positional"),
        ('x: str = typed_join(*["a", "b"])', "positional"),
        ("n: int = 2\nx: str = n.upper()", "No exact typed intrinsic"),
        ('x: str = "hi".lower()', "Only directly imported interface mapping calls"),
    ],
)
def test_reject_unregistered_or_wrongly_typed_calls(source: str, reason: str) -> None:
    with pytest.raises(UnsupportedPython, match=reason):
        PythonFrontend(intrinsics=_REGISTRY).parse(source)


def test_unshadowed_resolution_respects_user_functions_and_existing_builtins() -> None:
    # Same name as a declared function is handled by the normal call path.
    value = (
        PythonFrontend(intrinsics=_REGISTRY)
        .parse(
            "def typed_join(a: str, b: str) -> str:\n"
            "    return a + b\n"
            'x: str = typed_join("a", "b")'
        )
        .body.children[-1]
    )
    assert isinstance(value, Initialize)
    assert not isinstance(value.value, IntrinsicCall)
    assert not isinstance(
        PythonFrontend(intrinsics=_REGISTRY)
        .parse('n: int = len("hi")')
        .body.children[-1]
        .value,
        IntrinsicCall,
    )
    # The default registry added upper in iteration 29; custom catalogs still
    # have to opt in explicitly to every operation they wish to expose.
    with pytest.raises(UnsupportedPython):
        PythonFrontend(intrinsics=IntrinsicRegistry()).parse('x: str = "hello".upper()')


def test_realization_requires_explicit_pack_recipe_and_supports_all_keys() -> None:
    @realizes(IntrinsicCall)
    class Unsupported:
        variant = "intrinsic.global.typed_join"
        template = "${arg0} + ${arg1}"
        supports = ("intrinsic.global.typed_join",)

    @realizes(IntrinsicCall)
    class Accepted:
        variant = "intrinsic.global.typed_join"
        template = "${arg0} + ${arg1}"
        supports = (
            "intrinsic.global.typed_join",
            "intrinsic.effects.new_string",
            "intrinsic.arguments.once",
            "call.arguments.left_to_right",
        )

    model = _value('x: str = typed_join("a", "b")')
    with pytest.raises(ConstructError, match="does not support contracts"):
        realize(model, realizations=RealizationRegistry("unready", (Unsupported,)))

    # The Intrinsic's own binding can work independent of Program layout.
    @realizes(Literal)
    class TextLiteral:
        variant = "string"
        render = lambda node, ctx: repr(node.value)

    ready = RealizationRegistry("demo", (Accepted, TextLiteral))
    assert realize(model, realizations=ready) == "'a' + 'b'\n"
    assert ready.recipe(model, EmitContext(ready)).supports == {
        "intrinsic.global.typed_join",
        "intrinsic.effects.new_string",
        "intrinsic.arguments.once",
        "call.arguments.left_to_right",
    }
    for target in (c_bindings(), python_bindings()):
        with pytest.raises(ConstructError, match="No .* realization"):
            realize(model, realizations=target)


def test_simple_template_cannot_drop_duplicate_or_reorder_expression_slots() -> None:
    @realizes(IntrinsicCall)
    class Drop:
        variant = "intrinsic.global.typed_join"
        template = "${arg0}"
        supports = (
            "intrinsic.global.typed_join",
            "intrinsic.effects.new_string",
            "intrinsic.arguments.once",
            "call.arguments.left_to_right",
        )

    @realizes(IntrinsicCall)
    class WrongOrder:
        variant = "intrinsic.global.typed_join"
        template = "${arg1} + ${arg0}"
        supports = (
            "intrinsic.global.typed_join",
            "intrinsic.effects.new_string",
            "intrinsic.arguments.once",
            "call.arguments.left_to_right",
        )

    value = _value('x: str = typed_join("a", "b")')
    for recipe in (Drop, WrongOrder):
        with pytest.raises(ConstructError, match="Direct expression layout"):
            realize(value, realizations=RealizationRegistry("unsafe", (recipe,)))


def test_program_api_accepts_intrinsic_catalog_separately_from_target_pack() -> None:
    with pytest.raises(ConstructError, match="No .* realization"):
        convert(
            'x: str = typed_join("a", "b")',
            realizations=python_bindings(),
            intrinsics=_REGISTRY,
        )
    with pytest.raises(TypeError, match="IntrinsicRegistry"):
        convert("x: int = 3", realizations=python_bindings(), intrinsics="wrong")  # type: ignore[arg-type]
    assert LANGUAGE_ADMISSION.required_contracts(_value('x: str = "hi".upper()')) == {
        "intrinsic.str.upper",
        "intrinsic.receiver_once",
    }
