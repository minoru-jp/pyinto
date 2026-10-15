"""Function mapping and native device code live outside pyinto Core."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from demo_device.device import is_ready
from demo_device_pyinto import c_device_bindings, interface_mapping_registry
from shikumi_contrace import binds, upholds

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.contracts.boundaries.pipeline import FrontendBoundary
from pyinto.contracts.function_mapping_contract import FunctionMappingContract
from pyinto.interface_mapping import InterfaceFunctionMapping, InterfaceMappingRegistry

ROOT = Path(__file__).resolve().parents[1] / "examples" / "mapping_demo"
IMPORT = "from demo_device.device import is_ready\n"


def realize_mapping(program, *, realizations):
    return realize(
        program,
        realizations=realizations,
        admission=interface_mapping_registry().admission,
    )


@binds[FrontendBoundary](PythonFrontend)
class TestFunctionMapping:
    @upholds(FunctionMappingContract.parse.PythonExecution)
    def test_mapped_python_library_is_independent(self) -> None:
        assert is_ready(_force=True)
        assert not is_ready(_force=False)
        run = subprocess.run(
            [sys.executable, str(ROOT / "application.py")],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        assert run.returncode == 0 and run.stdout == b"ready\n"

    @upholds(FunctionMappingContract.parse.ExplicitMapping)
    def test_explicit_import_maps_to_external_value(self) -> None:
        p = PythonFrontend(interface_mapping_registry()).parse(
            IMPORT + 'if is_ready():\n    print("yes")'
        )
        assert "device_is_ready()" in realize_mapping(
            p, realizations=c_device_bindings()
        )

    @upholds(FunctionMappingContract.parse.ForceErasure)
    @pytest.mark.parametrize("force", ["True", "False", "None", "42", "'abc'"])
    def test_force_literal_never_reaches_target(self, force: str) -> None:
        p = PythonFrontend(interface_mapping_registry()).parse(
            IMPORT + f'if is_ready(_force={force}):\n    print("ok")'
        )
        emitted = realize_mapping(p, realizations=c_device_bindings())
        assert "_force" not in emitted and "device_is_ready()" in emitted

    @upholds(FunctionMappingContract.parse.StrictBoundary)
    @pytest.mark.parametrize(
        "code, msg",
        [
            (
                IMPORT + "if is_ready(_force=unknown):\n    print('ok')",
                "_force must be a literal",
            ),
            (
                IMPORT + "if is_ready(random=True):\n    print('ok')",
                "Only the reserved _force",
            ),
            (
                IMPORT + "if unregistered():\n    print('ok')",
                "Unregistered interface mapping call",
            ),
            ("from nowhere import foo\nfoo()", "Unregistered interface mapping import"),
        ],
    )
    def test_rejects_unknown(self, code: str, msg: str) -> None:
        with pytest.raises(UnsupportedPython, match=msg):
            PythonFrontend(interface_mapping_registry()).parse(code)

    @upholds(FunctionMappingContract.parse.NativeBinding)
    def test_native_device_compile_and_run(self, tmp_path: Path) -> None:
        cc = shutil.which("gcc") or shutil.which("clang")
        if cc is None:
            pytest.skip("No C compiler")
        p = PythonFrontend(interface_mapping_registry()).parse(
            IMPORT + 'if is_ready():\n    print("ready")'
        )
        c_file = tmp_path / "program.c"
        c_file.write_text(
            realize_mapping(p, realizations=c_device_bindings()), encoding="utf-8"
        )
        result = subprocess.run(
            [
                cc,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                "-I",
                str(ROOT / "c_device"),
                str(c_file),
                str(ROOT / "c_device" / "device.c"),
                "-o",
                str(tmp_path / "device"),
            ],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        run = subprocess.run(
            [str(tmp_path / "device")], capture_output=True, check=False
        )
        assert run.returncode == 0 and run.stdout == b""


def test_interface_mapping_registry_rejects_duplicates() -> None:
    source = "demo_device.device.is_ready"
    with pytest.raises(ValueError, match="Duplicate"):
        InterfaceMappingRegistry(
            (
                InterfaceFunctionMapping(source, (), lambda _: None),
                InterfaceFunctionMapping(source, (), lambda _: None),
            )
        )
