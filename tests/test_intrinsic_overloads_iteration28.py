"""Iteration 28: family keys, static overloads and signature-local variables."""

from __future__ import annotations

import pytest

from pyinto import realize
from pyinto.constructs import (
    ConstructError,
    ExpressionStatement,
    Initialize,
    IntrinsicCall,
    IntrinsicDefinition,
    IntrinsicListType,
    IntrinsicTypeVar,
    ListType,
    Literal,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.intrinsics import IntrinsicRegistry, standard_intrinsics
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import realizes, supports, template, variant

INT = ValueType(ValueKind.INTEGER)
FLOAT = ValueType(ValueKind.FLOAT)
STR = ValueType(ValueKind.STRING)
NONE = ValueType(ValueKind.NONE)
T = IntrinsicTypeVar("T")
TO_INT = IntrinsicDefinition(
    "stringify", None, (INT,), STR, frozenset({"intrinsic.stringify.int_repr"})
)
TO_FLOAT = IntrinsicDefinition(
    "stringify", None, (FLOAT,), STR, frozenset({"intrinsic.stringify.float_repr"})
)
APPEND = IntrinsicDefinition(
    "append",
    IntrinsicListType(T),
    (T,),
    NONE,
    frozenset({"intrinsic.effects.list_mutation", "intrinsic.aliases.shared"}),
)


def _call(source: str, registry: IntrinsicRegistry) -> IntrinsicCall:
    last = PythonFrontend(intrinsics=registry).parse(source).body.children[-1]
    assert isinstance(last, (Initialize, ExpressionStatement))
    assert isinstance(last.value, IntrinsicCall)
    return last.value


def test_overloaded_global_names_keep_one_key_and_distinct_obligations() -> None:
    registry = IntrinsicRegistry((TO_INT, TO_FLOAT))
    assert [s.key for s in registry.definitions] == [
        "intrinsic.global.stringify",
        "intrinsic.global.stringify",
    ]
    assert registry.global_call("stringify") is None
    assert registry.has_global_name("stringify")
    integer_call = _call("x: str = stringify(12)", registry)
    float_call = _call("x: str = stringify(1.25)", registry)
    assert integer_call.definition is TO_INT
    assert float_call.definition is TO_FLOAT
    assert (
        integer_call.variant() == float_call.variant() == "intrinsic.global.stringify"
    )
    assert "intrinsic.stringify.int_repr" in required_contracts(integer_call)
    assert "intrinsic.stringify.float_repr" not in required_contracts(integer_call)
    assert "intrinsic.stringify.float_repr" in required_contracts(float_call)
    assert "intrinsic.stringify.int_repr" not in required_contracts(float_call)


def test_type_parameter_binds_exact_list_element_and_concretizes_model() -> None:
    registry = IntrinsicRegistry((APPEND,))
    assert APPEND.key == "intrinsic.list.append"
    assert registry.has_method_name("append")
    for element, literal, annotation in ((INT, "1", "int"), (STR, "'a'", "str")):
        call = _call(f"xs: list[{annotation}] = []\nxs.append({literal})", registry)
        # The frontend deliberately does not infer an element type from an empty list.
        assert call.definition.key == APPEND.key
        assert call.definition.receiver_type == ValueType(
            ValueKind.LIST, list_type=ListType(element)
        )
        assert call.definition.argument_types == (element,)
        assert call.definition.return_type == NONE
        assert isinstance(call.definition.receiver_type, ValueType)
        assert all(isinstance(arg, ValueType) for arg in call.definition.argument_types)
        assert required_contracts(call) >= {
            "intrinsic.list.append",
            "intrinsic.effects.list_mutation",
            "intrinsic.aliases.shared",
            "intrinsic.receiver_once",
            "intrinsic.receiver_before_arguments",
            "intrinsic.arguments.once",
        }


def test_wrong_generic_element_is_rejected_without_coercion() -> None:
    with pytest.raises(UnsupportedPython, match="type mismatch"):
        _call("xs: list[int] = [1]\nxs.append('wrong')", IntrinsicRegistry((APPEND,)))


def test_concrete_list_overloads_work_without_variable_binding() -> None:
    a = IntrinsicDefinition(
        "put", ValueType(ValueKind.LIST, list_type=ListType(INT)), (INT,), NONE
    )
    b = IntrinsicDefinition(
        "put", ValueType(ValueKind.LIST, list_type=ListType(STR)), (STR,), NONE
    )
    registry = IntrinsicRegistry((a, b))
    assert registry.method("put", a.receiver_type) is a
    assert registry.method("put", b.receiver_type) is b
    assert _call("xs: list[int] = [1]\nxs.put(2)", registry).definition is a
    assert _call("xs: list[str] = ['a']\nxs.put('b')", registry).definition is b


def test_overloaded_arity_and_mismatched_types_are_rejected() -> None:
    registry = IntrinsicRegistry((TO_INT, TO_FLOAT))
    with pytest.raises(UnsupportedPython, match="arity"):
        _call("x: str = stringify()", registry)
    with pytest.raises(UnsupportedPython, match="type mismatch"):
        _call('x: str = stringify("hello")', registry)
    with pytest.raises(UnsupportedPython, match="positional"):
        _call("x: str = stringify(value=1)", registry)


def test_multiple_applicable_signatures_fail_instead_of_priority_guessing() -> None:
    # The generic signature and concrete one overlap: do not rank by specificity.
    concrete = IntrinsicDefinition(
        "append", ValueType(ValueKind.LIST, list_type=ListType(INT)), (INT,), NONE
    )
    registry = IntrinsicRegistry((APPEND, concrete))
    with pytest.raises(UnsupportedPython, match="Ambiguous intrinsic signatures"):
        _call("xs: list[int] = [1]\nxs.append(2)", registry)
    assert (
        _call("xs: list[str] = ['a']\nxs.append('b')", registry).definition.key
        == APPEND.key
    )


def test_ambiguous_global_overloads_can_be_accepted_in_registry_but_not_called() -> (
    None
):
    generic = IntrinsicDefinition("identity", None, (T,), T)
    concrete = IntrinsicDefinition("identity", None, (INT,), INT)
    registry = IntrinsicRegistry((generic, concrete))
    with pytest.raises(UnsupportedPython, match="Ambiguous"):
        _call("x: int = identity(1)", registry)
    assert _call('x: str = identity("hi")', registry).value_type == STR


def test_bad_patterns_and_unbound_result_are_rejected() -> None:
    with pytest.raises(ConstructError, match="type variable"):
        IntrinsicTypeVar("not a name")
    with pytest.raises(ConstructError, match="list pattern"):
        IntrinsicListType("int")  # type: ignore[arg-type]
    with pytest.raises(ConstructError, match="unbound"):
        IntrinsicDefinition("create", None, (), T)
    with pytest.raises(ConstructError, match="receiver"):
        IntrinsicDefinition("illegal", T, (), STR)
    with pytest.raises(ConstructError, match="arguments"):
        IntrinsicDefinition("illegal", None, (IntrinsicListType(NONE),), STR)


def test_provider_extend_is_immutable_and_identical_signatures_cannot_override() -> (
    None
):
    catalog = IntrinsicRegistry((TO_INT,))
    expanded = catalog.extend((TO_FLOAT,))
    assert len(catalog.definitions) == 1
    assert len(expanded.definitions) == 2
    with pytest.raises(ConstructError, match="Duplicate intrinsic signature"):
        expanded.extend((TO_INT,))
    with pytest.raises(ValueError, match="Duplicate intrinsic signature"):
        IntrinsicRegistry((TO_INT, IntrinsicDefinition("stringify", None, (INT,), INT)))


def test_generic_definition_is_concretized_on_direct_model_construction() -> None:
    from pyinto.constructs import ListValue

    receiver = ListValue((Literal(1),), INT)
    call = IntrinsicCall(APPEND, receiver, (Literal(3),))
    assert call.definition.receiver_type == receiver.value_type
    assert call.definition.argument_types == (INT,)
    assert call.definition.return_type == NONE
    assert call.definition is not APPEND
    assert call.variant() == "intrinsic.list.append"
    with pytest.raises(ConstructError, match="receiver presence"):
        IntrinsicCall(APPEND, None, (Literal(1),))


def test_actual_str_name_can_have_distinct_typed_overloads() -> None:
    registry = IntrinsicRegistry(
        (
            IntrinsicDefinition("str", None, (INT,), STR),
            IntrinsicDefinition("str", None, (FLOAT,), STR),
        )
    )
    one = _call("x: str = str(2)", registry)
    two = _call("x: str = str(2.5)", registry)
    assert one.variant() == two.variant() == "intrinsic.global.str"
    assert one.definition.argument_types == (INT,)
    assert two.definition.argument_types == (FLOAT,)
    # Iteration 29 adopts common conversions in the *default* provider table.
    assert _call("x: str = str(2)", standard_intrinsics()).value_type == STR


def test_repeat_type_variable_must_match_with_no_widening() -> None:
    pair = IntrinsicDefinition("pair", None, (T, T), T)
    registry = IntrinsicRegistry((pair,))
    assert _call("x: int = pair(1, 2)", registry).definition.argument_types == (
        INT,
        INT,
    )
    with pytest.raises(UnsupportedPython, match="type mismatch"):
        _call("x: int = pair(1, 2.5)", registry)


def test_per_signature_supports_is_checked_before_rendering() -> None:
    @realizes(IntrinsicCall)
    class OnlyInt:
        variant @= "intrinsic.global.stringify"
        template @= "${arg0}"
        supports @= (
            "intrinsic.global.stringify",
            "intrinsic.stringify.int_repr",
            "intrinsic.arguments.once",
        )

    pack = RealizationRegistry("int-string-only", (OnlyInt,))
    registry = IntrinsicRegistry((TO_INT, TO_FLOAT))
    with pytest.raises(ConstructError, match="does not support contracts"):
        realize(_call("x: str = stringify(1.5)", registry), realizations=pack)
    # The compatible signature passes admission; the missing Literal recipe is
    # an independent realization limitation (no Target expansion in iteration 28).
    with pytest.raises(ConstructError, match="No .* realization"):
        realize(_call("x: str = stringify(2)", registry), realizations=pack)


def test_port_instance_method_has_priority_over_same_named_intrinsic() -> None:
    from demo_memory_ports_pyinto import MemoryAssign, interface_mapping_registry

    registry = IntrinsicRegistry(
        (IntrinsicDefinition("assign", IntrinsicListType(T), (T,), NONE),)
    )
    source = (
        "from demo_memory_ports.memory import ManualMemoryRegion\n"
        "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\n"
        "a.assign(42)\n"
    )
    model = PythonFrontend(interface_mapping_registry(), intrinsics=registry).parse(
        source
    )
    assert isinstance(model.body.children[-1], MemoryAssign)
