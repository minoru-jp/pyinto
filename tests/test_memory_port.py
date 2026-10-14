"""Instance Ports: explicit layout contracts, alias typing and cleanup calls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from demo_memory_ports.memory import ManualMemoryRegion as PythonMemory
from demo_memory_ports_pyinto import (
    ManualMemoryRegion,
    MemoryAssign,
    MemoryRelease,
    MemoryValue,
    c_memory_bindings,
    c_wide_memory_bindings,
    interface_mapping_registry,
)
from shikumi_contrace import binds, upholds

from pyinto import ConstructError, PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import Assign, Branch, Comparison, Initialize, Reference, While
from pyinto.contracts.memory_port_contract import MemoryPortContract
from pyinto.contracts.ports.pipeline import FrontendPort
from tests.test_construct_pipeline import run_c

IMPORT = "from demo_memory_ports.memory import ManualMemoryRegion\n"
ROOT = Path(__file__).resolve().parents[1] / "examples" / "memory_port_demo"


def realize_port(program, *, realizations):
    return realize(
        program,
        realizations=realizations,
        admission=interface_mapping_registry().admission,
    )


def memory_source(
    *, release: bool = True, alias: bool = False, max_value: int = 255
) -> str:
    source = IMPORT + (
        f"a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum={max_value})\n"
    )
    if alias:
        source += "b: ManualMemoryRegion = a\nb.assign(42)\n"
    else:
        source += "a.assign(42)\n"
    source += "if a.value == 42:\n    print('ok')\n"
    if release:
        source += "a.release()\n"
    return source


def parse(source: str):
    return PythonFrontend(interface_mapping_registry()).parse(source)


@binds[FrontendPort](PythonFrontend)
class TestMemoryPort:
    @upholds(MemoryPortContract.parse.PythonPort)
    def test_python_port_runs_without_pyinto(self) -> None:
        fake = PythonMemory.integer(minimum=0, maximum=255)
        with pytest.raises(RuntimeError, match="not been assigned"):
            _ = fake.value
        fake.assign(42)
        assert fake.value == 42
        fake.assign(200)
        assert fake.value == 200
        with pytest.raises(ValueError, match="outside"):
            fake.assign(300)
        fake.release()
        with pytest.raises(RuntimeError, match="released"):
            fake.assign(42)
        run = subprocess.run(
            [sys.executable, str(ROOT / "application.py")],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        assert run.returncode == 0 and run.stdout == b"ok\n"

    @upholds(MemoryPortContract.parse.ExplicitOperations)
    def test_construct_tree_preserves_registered_method_positions(self) -> None:
        p = parse(memory_source())
        creation, assign, condition, release = p.body.children
        assert isinstance(creation, ManualMemoryRegion)
        assert isinstance(assign, MemoryAssign)
        assert isinstance(condition, Branch)
        assert isinstance(condition.condition.left, MemoryValue)
        assert isinstance(release, MemoryRelease)
        assert release.receiver.symbol is creation.symbol

    @upholds(MemoryPortContract.parse.NoImplicitCleanup)
    @pytest.mark.parametrize("release", [True, False])
    def test_release_only_when_explicit(self, release: bool) -> None:
        produced = realize_port(
            parse(memory_source(release=release)), realizations=c_memory_bindings()
        )
        assert ("free(a);" in produced) is release
        assert "malloc" in produced

    @upholds(MemoryPortContract.parse.AliasRepresentation)
    def test_alias_inherits_source_port_shape(self, tmp_path: Path) -> None:
        p = parse(memory_source(alias=True))
        assert isinstance(p.body.children[1], Initialize)
        alias = p.body.children[1]
        assert isinstance(alias.value, Reference)
        assert alias.symbol.port_type == alias.value.symbol.port_type
        generated = realize_port(p, realizations=c_memory_bindings())
        assert "uint8_t *a = malloc" in generated
        assert "uint8_t * b = a;" in generated
        assert "*b = 42LL;" in generated
        assert run_c(generated, tmp_path).stdout == b"ok\n"

    @upholds(MemoryPortContract.parse.AliasRepresentation)
    def test_rebinding_same_port_shape(self, tmp_path: Path) -> None:
        p = parse(
            IMPORT
            + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\n"
            + "b: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\n"
            + "b = a\nb.assign(42)\nif a.value == 42:\n    print('yes')\n"
            + "b.release()\na.release()\n"
        )
        assert isinstance(p.body.children[2], Assign)
        # This is deliberately an unsafe runtime double-free: do not execute.
        text = realize_port(p, realizations=c_memory_bindings())
        assert "b = a;" in text
        assert text.count("free(") == 2

    @upholds(MemoryPortContract.parse.ExplicitOperations)
    @pytest.mark.parametrize(
        "maximum, expected",
        [
            (127, "uint8_t"),
            (255, "uint8_t"),
            (256, "uint16_t"),
            (65536, "uint32_t"),
            (2**32, "uint64_t"),
        ],
    )
    def test_binding_chooses_storage_from_declared_constraints(
        self, maximum: int, expected: str
    ) -> None:
        p = parse(memory_source(max_value=maximum))
        text = realize_port(p, realizations=c_memory_bindings())
        assert f"{expected} *a = malloc" in text

    @upholds(MemoryPortContract.parse.ExplicitOperations)
    def test_alternate_target_pack_changes_both_constructor_and_alias_types(
        self,
    ) -> None:
        p = parse(memory_source(alias=True))
        assert "uint8_t *a" in realize_port(p, realizations=c_memory_bindings())
        wide = realize_port(p, realizations=c_wide_memory_bindings())
        assert "uint64_t *a" in wide
        assert "uint64_t * b = a;" in wide

    @upholds(MemoryPortContract.parse.StrictBoundary)
    @pytest.mark.parametrize(
        "source, match",
        [
            (
                IMPORT + "a = ManualMemoryRegion.integer(minimum=0, maximum=255)",
                "annotation",
            ),
            (
                IMPORT + "a: int = ManualMemoryRegion.integer(minimum=0, maximum=255)",
                "directly imported interface mapping calls",
            ),
            (IMPORT + "a: ManualMemoryRegion = unknown()", "registered constructor"),
            (
                IMPORT
                + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=5, maximum=3)",
                "minimum",
            ),
            (
                IMPORT
                + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\na.assign(256)",
                "outside",
            ),
            (
                IMPORT
                + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\na.unknown()",
                "Unregistered interface mapping object method",
            ),
            (
                IMPORT
                + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\na.release(1)",
                "argument count",
            ),
            (
                IMPORT
                + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\nb: int = a",
                "Annotated type",
            ),
            (
                IMPORT
                + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\nb: ManualMemoryRegion = a\nb = 1",
                "Variable type",
            ),
            (
                IMPORT
                + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\nb: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=65535)\na = b",
                "interface mapping rebinding",
            ),
        ],
    )
    def test_reject_unsupported_port_semantics(self, source: str, match: str) -> None:
        with pytest.raises(UnsupportedPython, match=match):
            parse(source)

    @upholds(MemoryPortContract.parse.StrictBoundary)
    def test_unsupported_target_range_rejected(self) -> None:
        p = parse(
            IMPORT
            + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=18446744073709551616)"
        )
        with pytest.raises(ConstructError, match="cannot represent"):
            realize_port(p, realizations=c_memory_bindings())

    @upholds(MemoryPortContract.parse.NoImplicitCleanup)
    def test_constructors_and_explicit_ops_compile(self, tmp_path: Path) -> None:
        code = realize_port(parse(memory_source()), realizations=c_memory_bindings())
        result = run_c(code, tmp_path)
        assert result.returncode == 0 and result.stdout == b"ok\n"

    @upholds(MemoryPortContract.parse.ExplicitOperations)
    def test_while_entry_can_use_external_port_value(self, tmp_path: Path) -> None:
        source = (
            IMPORT
            + "a: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)\n"
            + 'a.assign(42)\nwhile a.value < 43:\n    print("tick")\n'
            + "    a.assign(43)\na.release()\n"
        )
        program = parse(source)
        loop = program.body.children[2]
        assert isinstance(loop, While)
        assert isinstance(loop.condition, Comparison)
        code = realize_port(program, realizations=c_memory_bindings())
        assert "while (((*a) < 43LL))" in code
        result = run_c(code, tmp_path)
        assert result.returncode == 0 and result.stdout == b"tick\n"
