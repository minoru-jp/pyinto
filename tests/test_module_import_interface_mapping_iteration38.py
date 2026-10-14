"""Absolute module imports resolve explicit mappings regardless of library origin."""

from __future__ import annotations

from pathlib import Path

import pytest
from demo_ports_pyinto import c_device_bindings, interface_mapping_registry

from pyinto import PythonFrontend, UnsupportedPython, convert
from pyinto.constructs import Literal, ValueKind
from pyinto.interface_mapping import InterfaceFunctionMapping, InterfaceMappingRegistry


@pytest.mark.parametrize(
    "source",
    [
        "import demo_ports.device\ndemo_ports.device.is_ready()",
        "import demo_ports.device as dev\ndev.is_ready()",
        "from demo_ports import device\ndevice.is_ready()",
        "from demo_ports import device as dev\ndev.is_ready()",
        "import demo_ports.device as dev\nif dev.is_ready():\n    print('ready')",
        "import demo_ports.device as dev\nready: bool = dev.is_ready()",
    ],
)
def test_module_function_call_uses_existing_mapping(source: str) -> None:
    output = convert(
        source,
        realizations=c_device_bindings(),
        interface_mappings=interface_mapping_registry(),
    )
    assert "device_is_ready()" in output


def test_all_import_spellings_produce_equal_model() -> None:
    sources = (
        "from demo_ports.device import is_ready\nready: bool = is_ready()",
        "from demo_ports.device import is_ready as ready_fn\nready: bool = ready_fn()",
        "import demo_ports.device\nready: bool = demo_ports.device.is_ready()",
        "import demo_ports.device as lib\nready: bool = lib.is_ready()",
        "from demo_ports import device as lib\nready: bool = lib.is_ready()",
    )
    parser = PythonFrontend(interface_mapping_registry())
    programs = [parser.parse(source) for source in sources]
    assert all(program.parts() == programs[0].parts() for program in programs)


def test_mapping_resolution_is_library_agnostic_and_does_not_import() -> None:
    # The module is intentionally nonexistent. Only the declared mapping is used.
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.alpha.identity", (ValueKind.INTEGER,), lambda args: args[0]
            ),
            InterfaceFunctionMapping(
                "vendor.beta.identity", (ValueKind.INTEGER,), lambda args: args[0]
            ),
        )
    )
    parser = PythonFrontend(registry)
    sources = (
        "import vendor.alpha\nimport vendor.beta\na: int = vendor.alpha.identity(3)",
        "import vendor.alpha as a\nx: int = a.identity(3)",
        "from vendor import alpha as a\nx: int = a.identity(3)",
        "from vendor.alpha import identity as f\nx: int = f(3)",
    )
    for source in sources:
        result = parser.parse(source)
        assert "3" in repr(result.parts())


def test_nested_module_function_lookups() -> None:
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.pkg.submodule.action", (ValueKind.INTEGER,), lambda a: a[0]
            ),
        )
    )
    parser = PythonFrontend(registry)
    for source in (
        "import vendor.pkg.submodule\nx: int = vendor.pkg.submodule.action(8)",
        "import vendor.pkg.submodule as sub\nx: int = sub.action(8)",
        "from vendor.pkg import submodule as sub\nx: int = sub.action(8)",
    ):
        assert "8" in repr(parser.parse(source).parts())


@pytest.mark.parametrize(
    "source, message",
    [
        (
            "import absent.module\nabsent.module.fn()",
            "Unregistered interface mapping module",
        ),
        (
            "import demo_ports.device as d\nd.unknown()",
            "Unregistered interface mapping call",
        ),
        (
            "import demo_ports.device as d\nd.extra.is_ready()",
            "not explicitly imported",
        ),
        ("from demo_ports import unknown", "Unregistered interface mapping import"),
        ("from demo_ports import *", "Unregistered interface mapping import"),
        ("import demo_ports.device as print", "Duplicate or reserved import alias"),
        ("import demo_ports.device as d\nd: int = 1", "Cannot shadow"),
        (
            "import demo_ports.device as d\ndef d() -> int:\n    return 1",
            "Duplicate or reserved function name",
        ),
        (
            "import demo_ports.device as d\nclass d:\n    pass",
            "Duplicate or reserved class name",
        ),
        (
            "import demo_ports.device as d\ndef f(d: int) -> int:\n    return d",
            "Reserved",
        ),
        (
            "import demo_ports.device as d\nfor d in range(2):\n    print('x')",
            "reserved",
        ),
        ("import demo_ports.device as d\nd = 1", ""),
        (
            "import demo_ports.device\nfrom demo_ports.device import is_ready as demo_ports",
            "Duplicate or reserved import alias",
        ),
        (
            "import demo_ports.device as d\nfrom typing import Any as d",
            "Conflicting type import",
        ),
        (
            "import demo_ports.device as d\nfrom demo_ports.device import is_ready as d",
            "Duplicate or reserved import alias",
        ),
        (
            "from demo_ports.device import is_ready as d\nimport demo_ports.device as d",
            "Duplicate or reserved import alias",
        ),
        ("import demo_ports.device as d\nd.is_ready(1)", "argument count"),
        ("import demo_ports.device as d\nd.is_ready(value=1)", "Only the reserved"),
        ("import demo_ports.device as d\nresult: int = d.is_ready()", "type"),
        ("import demo_ports.device as d\nx: int = 1\nx: int = d.is_ready()", ""),
        ("x: int = 1\nimport demo_ports.device as d", "Unsupported statement"),
        (
            "def f() -> int:\n    import demo_ports.device\n    return 1",
            "Unsupported statement",
        ),
        ("from . import device", "Only explicit absolute"),
        (
            "from demo_ports.device import is_ready\nis_ready.other()",
            "Unregistered interface mapping object",
        ),
    ],
)
def test_rejects_unregistered_or_shadowed_calls(source: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend(interface_mapping_registry()).parse(source)


def test_per_parse_reset_after_success_and_failure() -> None:
    parser = PythonFrontend(interface_mapping_registry())
    parser.parse("import demo_ports.device as d\nd.is_ready()")
    with pytest.raises(UnsupportedPython):
        parser.parse("d.is_ready()")
    with pytest.raises(UnsupportedPython):
        parser.parse("import demo_ports.device as d\nd.missing()")
    with pytest.raises(UnsupportedPython):
        parser.parse("d.is_ready()")


def test_module_name_is_not_implicitly_callable_or_value() -> None:
    parser = PythonFrontend(interface_mapping_registry())
    for source in (
        "import demo_ports.device as d\nd()",
        "import demo_ports.device as d\nn: int = d",
        "import demo_ports.device as d\nn: int = d.is_ready",
    ):
        with pytest.raises(UnsupportedPython):
            parser.parse(source)


def test_import_works_as_static_syntax_not_python_execution() -> None:
    import sys

    # No actual module exists. Parsing relies solely on the explicit registry.
    assert "unavailable" not in sys.modules
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "unavailable.vendor.identity",
                (ValueKind.INTEGER,),
                lambda args: args[0],
            ),
        )
    )
    program = PythonFrontend(registry).parse(
        "import unavailable.vendor as vendor\nn: int = vendor.identity(9)"
    )
    assert program is not None
    assert "unavailable" not in sys.modules


def test_duplicate_root_imports_remain_legal() -> None:
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping("vendor.alpha.identity", (), lambda _: Literal(1)),
            InterfaceFunctionMapping("vendor.beta.identity", (), lambda _: Literal(2)),
        )
    )
    source = (
        "import vendor.alpha\n"
        "import vendor.beta\n"
        "x: int = vendor.alpha.identity()\n"
        "y: int = vendor.beta.identity()\n"
    )
    assert PythonFrontend(registry).parse(source)


def test_standard_library_module_uses_identical_resolution_path() -> None:
    # Stub factory tests import resolution, NOT a sqrt Realization or its semantics.
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "math.sqrt", (ValueKind.FLOAT,), lambda arguments: arguments[0]
            ),
        )
    )
    frontend = PythonFrontend(registry)
    direct = frontend.parse("from math import sqrt\nx: float = sqrt(9.0)")
    qualified = frontend.parse("import math as m\nx: float = m.sqrt(9.0)")
    assert direct.parts() == qualified.parts()


def test_native_c_generation_for_module_import(tmp_path: Path) -> None:
    """A real sample library and its C implementation use ordinary import syntax."""
    import shutil
    import subprocess

    cc = shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        pytest.skip("No C compiler")
    source = "import demo_ports.device as dev\nif dev.is_ready():\n    print('ready')"
    emitted = convert(
        source,
        realizations=c_device_bindings(),
        interface_mappings=interface_mapping_registry(),
    )
    root = Path(__file__).resolve().parents[1] / "examples" / "port_demo"
    c_file = tmp_path / "generated.c"
    c_file.write_text(emitted, encoding="utf-8")
    binary = tmp_path / "app"
    compile_result = subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-I",
            str(root / "c_device"),
            str(c_file),
            str(root / "c_device" / "device.c"),
            "-o",
            str(binary),
        ],
        capture_output=True,
        check=False,
    )
    assert compile_result.returncode == 0, compile_result.stderr.decode()
    run = subprocess.run([str(binary)], capture_output=True, check=False)
    assert run.returncode == 0 and run.stdout == b""


def test_sibling_module_needs_its_own_import() -> None:
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping("vendor.alpha.identity", (), lambda _: Literal(1)),
            InterfaceFunctionMapping("vendor.beta.identity", (), lambda _: Literal(2)),
        )
    )
    parser = PythonFrontend(registry)
    with pytest.raises(UnsupportedPython, match="not explicitly imported"):
        parser.parse("import vendor.alpha\nx: int = vendor.beta.identity()")
    assert parser.parse(
        "import vendor.alpha\nimport vendor.beta\nx: int = vendor.beta.identity()"
    )
