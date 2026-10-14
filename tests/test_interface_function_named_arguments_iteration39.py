"""External Interface function calls obey explicit Python parameter binding."""

from __future__ import annotations

import pytest

from pyinto import PythonFrontend, UnsupportedPython, convert
from pyinto.constructs import (
    Arithmetic,
    BooleanLiteral,
    FloatingLiteral,
    Literal,
    NoneLiteral,
    ValueKind,
)
from pyinto.interface_mapping import (
    InterfaceFunctionMapping,
    InterfaceMappingRegistry,
    InterfaceParameter,
)
from tests.support.c_realizer import c_bindings


def geometry_mapping() -> InterfaceMappingRegistry:
    return InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                source="vendor.geometry.area",
                parameters=(
                    InterfaceParameter("width", ValueKind.INTEGER),
                    InterfaceParameter("height", ValueKind.INTEGER, Literal(7)),
                ),
                factory=lambda args: args[0],
            ),
        )
    )


@pytest.mark.parametrize(
    "source",
    [
        "from vendor.geometry import area\nresult: int = area(6, 7)",
        "from vendor.geometry import area as a\nresult: int = a(width=6, height=7)",
        "import vendor.geometry\nresult: int = vendor.geometry.area(6, height=7)",
        "import vendor.geometry as g\nresult: int = g.area(height=7, width=6)",
    ],
)
def test_parameter_styles_normalize_to_same_model(source: str) -> None:
    expected = PythonFrontend(geometry_mapping()).parse(
        "from vendor.geometry import area\nresult: int = area(6, 7)"
    )
    assert PythonFrontend(geometry_mapping()).parse(source).parts() == expected.parts()
    generated = convert(
        source, interface_mappings=geometry_mapping(), realizations=c_bindings()
    )
    assert "6" in generated


def test_omitted_default_has_same_model_as_explicit_argument() -> None:
    frontend = PythonFrontend(geometry_mapping())
    a = frontend.parse("from vendor.geometry import area\nr: int = area(6)")
    b = frontend.parse(
        "from vendor.geometry import area\nr: int = area(width=6, height=7)"
    )
    assert a.parts() == b.parts()


def test_factory_receives_canonical_declaration_order_and_defaults() -> None:
    captured: list[tuple[object, ...]] = []

    def build(arguments):
        captured.append(arguments)
        return arguments[0]

    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.geometry.area",
                factory=build,
                parameters=(
                    InterfaceParameter("width", ValueKind.INTEGER),
                    InterfaceParameter("height", ValueKind.INTEGER, Literal(7)),
                ),
            ),
        )
    )
    frontend = PythonFrontend(registry)
    frontend.parse("import vendor.geometry as g\nr: int = g.area(height=4, width=6)")
    frontend.parse("import vendor.geometry as g\nr: int = g.area(6)")
    assert captured == [(Literal(6), Literal(4)), (Literal(6), Literal(7))]


def test_force_is_erased_with_keywords_and_defaults() -> None:
    normalizer = PythonFrontend(geometry_mapping())
    left = normalizer.parse(
        "import vendor.geometry as g\nr: int = g.area(width=6, _force=True)"
    )
    right = normalizer.parse("import vendor.geometry as g\nr: int = g.area(6)")
    assert left.parts() == right.parts()


@pytest.mark.parametrize(
    "call, message",
    [
        ("area()", "Missing required"),
        ("area(height=7)", "Missing required"),
        ("area(1, 2, 3)", "argument count"),
        ("area(1, width=2)", "Duplicate"),
        ("area(width=1, width=2)", "Duplicate"),
        ("area(depth=2, width=1)", "Unknown"),
        ("area(width='bad')", "kind mismatch"),
        ("area(*[1, 2])", "Expanded"),
        ("area(**{'width': 1})", "Expanded"),
        ("area(1, _force=not_defined)", "_force must be a literal"),
        ("area(1, _force=True, _force=False)", "Duplicate reserved"),
    ],
)
def test_rejects_unsupported_or_invalid_bindings(call: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend(geometry_mapping()).parse(
            "from vendor.geometry import area\nr: int = " + call
        )


def test_reordering_side_effectful_arguments_is_rejected() -> None:
    source = (
        "from vendor.geometry import area\n"
        "def side_effect() -> int:\n"
        "    print('called')\n"
        "    return 7\n"
        "r: int = area(height=side_effect(), width=6)"
    )
    with pytest.raises(UnsupportedPython, match="Reordered.*effects"):
        PythonFrontend(geometry_mapping()).parse(source)


def test_source_order_side_effectful_arguments_still_supported() -> None:
    source = (
        "from vendor.geometry import area\n"
        "def value() -> int:\n"
        "    return 7\n"
        "r: int = area(width=value(), height=7)"
    )
    assert PythonFrontend(geometry_mapping()).parse(source)


@pytest.mark.parametrize(
    "parameters, positional, message",
    [
        (
            (
                InterfaceParameter("x", ValueKind.INTEGER),
                InterfaceParameter("x", ValueKind.INTEGER),
            ),
            (),
            "duplicate",
        ),
        ((InterfaceParameter("for", ValueKind.INTEGER),), (), "Invalid"),
        ((InterfaceParameter("_force", ValueKind.INTEGER),), (), "Invalid"),
        (
            (
                InterfaceParameter("x", ValueKind.INTEGER, Literal(1)),
                InterfaceParameter("y", ValueKind.INTEGER),
            ),
            (),
            "follow a default",
        ),
        (
            (InterfaceParameter("x", ValueKind.INTEGER, Literal("bad")),),
            (),
            "immutable literal",
        ),
        (
            (
                InterfaceParameter(
                    "x", ValueKind.INTEGER, Arithmetic(Literal(1), "+", Literal(2))
                ),
            ),
            (),
            "immutable literal",
        ),
        (
            (InterfaceParameter("x", ValueKind.INTEGER),),
            (ValueKind.INTEGER,),
            "cannot mix",
        ),
    ],
)
def test_registry_rejects_invalid_signatures(parameters, positional, message):
    with pytest.raises(ValueError, match=message):
        InterfaceMappingRegistry(
            (
                InterfaceFunctionMapping(
                    "vendor.fn",
                    positional,
                    lambda args: Literal(1),
                    parameters=parameters,
                ),
            )
        )


def test_boolean_none_and_float_literal_defaults_validate() -> None:
    for kind, value in (
        (ValueKind.BOOLEAN, BooleanLiteral(True)),
        (ValueKind.NONE, NoneLiteral()),
        (ValueKind.FLOAT, FloatingLiteral(2.5)),
    ):
        assert (
            InterfaceMappingRegistry(
                (
                    InterfaceFunctionMapping(
                        "vendor.fn",
                        factory=lambda args: args[0],
                        parameters=(InterfaceParameter("value", kind, value),),
                    ),
                )
            ).get("vendor.fn")
            is not None
        )


def test_old_positional_only_mapping_keeps_rejecting_keywords() -> None:
    mapping = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.identity",
                (ValueKind.INTEGER,),
                lambda values: values[0],
            ),
        )
    )
    with pytest.raises(UnsupportedPython, match="Only the reserved _force"):
        PythonFrontend(mapping).parse(
            "from vendor import identity\nr: int = identity(1, value=1)"
        )
