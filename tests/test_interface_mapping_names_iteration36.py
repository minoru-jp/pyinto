"""Stage 4c: the mapping API is named independently of model PortType identity."""

import pytest

from pyinto import PythonFrontend, convert
from pyinto.constructs import BooleanLiteral, PortType, ValueKind
from pyinto.interface_mapping import InterfaceFunctionMapping, InterfaceMappingRegistry
from pyinto.realizations.registry import RealizationRegistry


def test_stage4c_explicit_mapping_and_duplicate_rejection() -> None:
    definition = InterfaceFunctionMapping(
        "demo.external.ready", (), lambda _: BooleanLiteral(True)
    )
    mappings = InterfaceMappingRegistry((definition,))
    program = PythonFrontend(interface_mappings=mappings).parse(
        "from demo.external import ready\nready()\n"
    )
    assert program.body.children
    with pytest.raises(ValueError, match="Duplicate"):
        InterfaceMappingRegistry((definition, definition))
    with pytest.raises(TypeError, match="InterfaceMappingRegistry"):
        convert(
            "print('x')",
            realizations=RealizationRegistry("x", ()),
            interface_mappings=object(),  # type: ignore[arg-type]
        )


def test_stage4c_model_external_object_identity_is_unchanged() -> None:
    shape = PortType("demo.memory.Region", "integer", (("minimum", 1),))
    assert shape.key == "port:demo.memory.Region.integer"
    assert ValueKind.PORT_OBJECT.value == "port_object"
