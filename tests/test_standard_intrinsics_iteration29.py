"""Iteration 29: standard typed conversions and Unicode string operations.

The catalog describes Python behavior by contract. No Target implementation or
coercive overload selection is presumed merely because the Model accepts it.
"""

from __future__ import annotations

import pytest

from pyinto import PythonFrontend, realize
from pyinto.constructs import (
    ConstructError,
    FunctionCall,
    Initialize,
    IntrinsicCall,
    IntrinsicDefinition,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import UnsupportedPython
from pyinto.intrinsics import IntrinsicRegistry, standard_intrinsics
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import realizes

STR = ValueType(ValueKind.STRING)
INT = ValueType(ValueKind.INTEGER)
FLOAT = ValueType(ValueKind.FLOAT)
BOOL = ValueType(ValueKind.BOOLEAN)


def call(source: str, *, catalog: IntrinsicRegistry | None = None) -> IntrinsicCall:
    value = PythonFrontend(intrinsics=catalog).parse(source).body.children[-1]
    assert isinstance(value, Initialize)
    assert isinstance(value.value, IntrinsicCall)
    return value.value


@pytest.mark.parametrize(
    ("source", "operation", "input_types", "return_type", "obligation"),
    [
        ("s: str = str()", "str", (), STR, "intrinsic.stringify.empty"),
        ("s: str = str('hi')", "str", (STR,), STR, "intrinsic.stringify.identity"),
        ("s: str = str(-12)", "str", (INT,), STR, "intrinsic.stringify.int_repr"),
        ("s: str = str(1.0)", "str", (FLOAT,), STR, "intrinsic.stringify.float_repr"),
        ("s: str = str(True)", "str", (BOOL,), STR, "intrinsic.stringify.bool_repr"),
        ("i: int = int()", "int", (), INT, "intrinsic.convert.int.default_zero"),
        ("i: int = int(42)", "int", (INT,), INT, "intrinsic.convert.int.identity"),
        ("i: int = int(False)", "int", (BOOL,), INT, "intrinsic.convert.int.from_bool"),
        (
            "i: int = int(-1.5)",
            "int",
            (FLOAT,),
            INT,
            "intrinsic.convert.int.from_float",
        ),
        ("i: int = int('13')", "int", (STR,), INT, "intrinsic.convert.int.from_str"),
        (
            "f: float = float()",
            "float",
            (),
            FLOAT,
            "intrinsic.convert.float.default_zero",
        ),
        (
            "f: float = float(1.0)",
            "float",
            (FLOAT,),
            FLOAT,
            "intrinsic.convert.float.identity",
        ),
        (
            "f: float = float(True)",
            "float",
            (BOOL,),
            FLOAT,
            "intrinsic.convert.float.from_bool",
        ),
        (
            "f: float = float(12)",
            "float",
            (INT,),
            FLOAT,
            "intrinsic.convert.float.from_int",
        ),
        (
            "f: float = float('1.5')",
            "float",
            (STR,),
            FLOAT,
            "intrinsic.convert.float.from_str",
        ),
    ],
)
def test_default_conversion_signatures(
    source: str,
    operation: str,
    input_types: tuple[ValueType, ...],
    return_type: ValueType,
    obligation: str,
) -> None:
    node = call(source)
    assert node.variant() == f"intrinsic.global.{operation}"
    assert node.definition.argument_types == input_types
    assert node.value_type == return_type
    assert node.definition.obligations == frozenset({obligation})
    assert obligation in required_contracts(node)
    assert len(node.arguments) == len(input_types)


@pytest.mark.parametrize(
    ("source", "name", "obligation"),
    [
        ('s: str = "straße".upper()', "upper", "intrinsic.string.upper_unicode"),
        ('s: str = "İ".lower()', "lower", "intrinsic.string.lower_unicode"),
    ],
)
def test_unicode_methods_are_static_receiver_calls(
    source: str, name: str, obligation: str
) -> None:
    node = call(source)
    assert node.variant() == f"intrinsic.str.{name}"
    assert node.value_type == STR
    assert node.definition.obligations == frozenset({obligation})
    assert required_contracts(node) >= {
        f"intrinsic.str.{name}",
        obligation,
        "intrinsic.receiver_once",
    }
    assert not node.arguments
    assert tuple(node.parts()) == ("receiver",)


def test_standard_registry_family_keys_and_overloads_are_stable() -> None:
    catalog = standard_intrinsics()
    assert len(catalog.global_candidates("str")) == 5
    assert len(catalog.global_candidates("int")) == 5
    assert len(catalog.global_candidates("float")) == 5
    assert len(catalog.method_candidates("upper", STR)) == 1
    assert catalog.method_candidates("upper", INT) == ()
    assert len({definition.key for definition in catalog.global_candidates("str")}) == 1
    assert not catalog.has_method_name("append")
    assert catalog.global_candidates("print") == ()


def test_custom_registry_replaces_defaults_and_can_extend_explicitly() -> None:
    custom = IntrinsicRegistry((IntrinsicDefinition("twice", None, (INT,), INT),))
    assert call("n: int = twice(1)", catalog=custom).value_type == INT
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        PythonFrontend(intrinsics=custom).parse("s: str = str(1)")
    extended = standard_intrinsics().extend(custom.definitions)
    assert call("n: int = twice(1)", catalog=extended).value_type == INT
    assert call("s: str = str(1)", catalog=extended).value_type == STR
    with pytest.raises(ConstructError, match="Duplicate intrinsic signature"):
        extended.extend((standard_intrinsics().global_candidates("str")[0],))


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("s: str = str([1])", "type mismatch"),
        ("s: str = str(1, 2)", "arity mismatch"),
        ("s: str = str(object=1)", "positional arguments only"),
        ("s: str = str(*[1])", "positional arguments only"),
        ("i: int = int([1])", "type mismatch"),
        ("i: int = int('10', 2)", "arity mismatch"),
        ("f: float = float([1])", "type mismatch"),
        ("s: str = 'HI'.upper(1)", "arity mismatch"),
        ("s: str = 'HI'.upper(x=1)", "positional arguments only"),
        ("s: str = 'HI'.strip()", "Only directly imported interface mapping calls"),
        ("x: int = str(1)", "Annotated type does not match"),
    ],
)
def test_rejects_unadopted_or_mismatched_conversion_forms(
    source: str, error: str
) -> None:
    with pytest.raises(UnsupportedPython, match=error):
        PythonFrontend().parse(source)


def test_user_function_shadows_standard_intrinsic() -> None:
    model = PythonFrontend().parse(
        "def str(n: int) -> int:\n    return n\nx: int = str(12)"
    )
    declaration = model.body.children[-1]
    assert isinstance(declaration, Initialize)
    assert isinstance(declaration.value, FunctionCall)
    # Explicitly empty provider registry still rejects the standard name.
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        PythonFrontend(intrinsics=IntrinsicRegistry()).parse("x: str = str(1)")


def test_catalog_is_never_a_realization_implementation() -> None:
    @realizes(IntrinsicCall)
    class OnlyInteger:
        variant = "intrinsic.global.str"
        template = "${arg0}"
        supports = (
            "intrinsic.global.str",
            "intrinsic.stringify.int_repr",
            "intrinsic.arguments.once",
        )

    pack = RealizationRegistry("int-only", (OnlyInteger,))
    with pytest.raises(ConstructError, match="does not support contracts"):
        realize(call("s: str = str(1.0)"), realizations=pack)
    # Integer input passes admission but cannot be realized without Literal.
    with pytest.raises(ConstructError, match="No .* realization"):
        realize(call("s: str = str(1)"), realizations=pack)


def test_conversion_input_is_not_executed_at_parse_time() -> None:
    for source, obligation in (
        ("i: int = int('not an integer')", "intrinsic.convert.int.from_str"),
        ("f: float = float('NaN')", "intrinsic.convert.float.from_str"),
    ):
        node = call(source)
        assert obligation in required_contracts(node)
    # Runtime conversion errors and non-finite values belong to the operation
    # contract and eventual Realization, not Frontend value inference.


def test_nested_conversions_choose_by_inner_declared_return_type() -> None:
    value = call("s: str = str(float('1.0'))")
    assert value.definition.argument_types == (FLOAT,)
    assert len(value.arguments) == 1
    child = value.arguments[0]
    assert isinstance(child, IntrinsicCall)
    assert child.definition.key == "intrinsic.global.float"
    assert child.definition.argument_types == (STR,)
    assert "intrinsic.convert.float.from_str" in required_contracts(child)
    assert "intrinsic.stringify.float_repr" in required_contracts(value)


def test_python_str_float_repr_not_assumed_to_be_plain_numeric_format() -> None:
    string_conversion = call("s: str = str(1.0)")
    assert "intrinsic.stringify.float_repr" in required_contracts(string_conversion)
    assert "intrinsic.stringify.int_repr" not in required_contracts(string_conversion)
    assert string_conversion.arguments[0].value_type == FLOAT


def test_repeated_frontend_parse_preserves_catalog_without_mutating_it() -> None:
    frontend = PythonFrontend()
    first = frontend.parse("a: str = str(12)")
    second = frontend.parse('b: str = "hi".upper()')
    assert isinstance(first.body.children[0].value, IntrinsicCall)  # type: ignore[attr-defined]
    assert isinstance(second.body.children[0].value, IntrinsicCall)  # type: ignore[attr-defined]
