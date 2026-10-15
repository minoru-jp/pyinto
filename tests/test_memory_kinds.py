"""Dynamic-memory vocabulary: shape and ownership as labels, few operation words."""

from __future__ import annotations

from pathlib import Path

import pytest

import pyinto.kinds.memory.general as source_memory
from pyinto import PythonFrontend, UnsupportedPython, convert
from pyinto.constructs import (
    ConstructError,
    Initialize,
    MemoryBorrow,
    MemoryCopy,
    MemoryFill,
    MemoryLength,
    MemoryNew,
    MemoryNewBuffer,
    MemoryRelease,
    MemoryResize,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import required_contracts
from pyinto.interfaces import language as lang
from pyinto.model.kinds.datatypes import detailed as dd
from pyinto.model.kinds.datatypes import general as dg
from pyinto.model.kinds.memory import general as mg
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer.kinds import c_kind_bindings
from tests.test_construct_pipeline import run_c

IMPORT = (
    "from pyinto.kinds.datatypes.general import Byte\n"
    "from pyinto.kinds.datatypes.detailed import Int\n"
    "from pyinto.kinds.memory.general import Buffer, Memory, Owned, Shared\n"
    "from pyinto.kinds.memory.detailed import Pointer\n"
)
SETUP = (
    "b: Owned[Int[32]] = Memory.new(Int[32], 7)\n"
    "buf: Owned[Buffer[Byte]] = Memory.new_buffer(Byte, 64, 0)\n"
)


def parse(source: str):
    return PythonFrontend().parse(IMPORT + source)


def last(source: str):
    return parse(source).body.children[-1]


# --- Source-side words --------------------------------------------------------


@pytest.mark.parametrize(
    "operation, arguments",
    [
        ("new", (0, 0)),
        ("new_buffer", (0, 0, 0)),
        ("release", (0,)),
        ("resize", (0, 0)),
        ("length", (0,)),
        ("borrow", (0,)),
        ("copy", (0, 0)),
        ("fill", (0, 0)),
    ],
)
def test_memory_operations_are_conversion_only(
    operation: str, arguments: tuple[int, ...]
) -> None:
    with pytest.raises(RuntimeError, match="conversion only"):
        getattr(source_memory.Memory, operation)(*arguments)


def test_memory_is_not_a_type() -> None:
    with pytest.raises(UnsupportedPython, match="not a type"):
        parse("x: Memory = 1\n")


# --- Shapes and labels --------------------------------------------------------


def test_owned_and_shared_keep_their_target_shape() -> None:
    owned = last("b: Owned[Int[32]] = Memory.new(Int[32], 7)\n").symbol.type
    shared = last("s: Shared[Int[32]] = Memory.new(Int[32], 7)\n").symbol.type
    assert owned.kind is shared.kind is ValueKind.INTEGER
    assert owned.annotation() == "Owned[Int[32]]"
    assert shared.annotation() == "Shared[Int[32]]"


def test_buffer_is_a_list_and_composes_with_ownership() -> None:
    shape = last(SETUP).symbol.type
    assert shape.kind is ValueKind.LIST
    assert shape.annotation() == "Owned[Buffer[Byte]]"
    element = last(SETUP + "x: Byte = buf[0]\n")
    assert element.symbol.type.annotation() == "Byte"
    assert last(SETUP + "n: int = len(buf)\n")


# --- Operations ---------------------------------------------------------------


def test_new_and_new_buffer_produce_owned_values() -> None:
    single, buffer = parse(SETUP).body.children
    assert isinstance(single.value, MemoryNew)
    assert single.value.value_type.annotation() == "Owned[Int[32]]"
    assert isinstance(buffer.value, MemoryNewBuffer)
    assert buffer.value.value_type.annotation() == "Owned[Buffer[Byte]]"


def test_shared_declaration_reads_ownership_from_the_declaration() -> None:
    node = last("s: Shared[Int[32]] = Memory.new(Int[32], 7)\n")
    assert isinstance(node, Initialize) and isinstance(node.value, MemoryNew)
    assert node.symbol.type.label.name == "Shared"


def test_borrow_yields_pointer_or_unowned_buffer() -> None:
    single = last(SETUP + "p: Pointer[Int[32]] = Memory.borrow(b)\n").value
    buffer = last(SETUP + "v: Buffer[Byte] = Memory.borrow(buf)\n").value
    assert isinstance(single, MemoryBorrow) and single.variant() == "single"
    assert single.value_type.annotation() == "Pointer[Int[32]]"
    assert isinstance(buffer, MemoryBorrow) and buffer.variant() == "buffer"
    assert buffer.value_type.annotation() == "Buffer[Byte]"


def test_release_variant_comes_from_the_handle_type() -> None:
    program = parse(SETUP + "Memory.release(b)\nMemory.release(buf)\n")
    single, buffer = program.body.children[-2:]
    assert isinstance(single, MemoryRelease) and single.variant() == "single"
    assert isinstance(buffer, MemoryRelease) and buffer.variant() == "buffer"
    assert lang.MemoryRelease.variant_domain() == {"single", "buffer"}


def test_buffer_operations() -> None:
    program = parse(
        SETUP
        + "v: Buffer[Byte] = Memory.borrow(buf)\n"
        + "n: int = Memory.length(buf)\n"
        + "Memory.fill(buf, 1)\n"
        + "Memory.copy(v, buf)\n"
        + "Memory.resize(buf, 128)\n"
    )
    _, _, _, length, fill, copy, resize = program.body.children
    assert isinstance(length.value, MemoryLength)
    assert isinstance(fill, MemoryFill)
    assert isinstance(copy, MemoryCopy)
    assert isinstance(resize, MemoryResize)


@pytest.mark.parametrize(
    "source, match",
    [
        ("x: int = 1\nMemory.release(x)\n", "Owned or Shared"),
        ("b: Owned[Int[32]] = Memory.new(Int[32], 'a')\n", "does not match"),
        ("b: Owned[Int[32]] = Memory.new(7, 7)\n", None),
        ("x: int = Memory.release(1)\n", "statement"),
        (SETUP + "Memory.resize(b, 3)\n", "owned Buffer"),
        (SETUP + "Memory.resize(buf, 'a')\n", "integer length"),
        (SETUP + "Memory.fill(b, 1)\n", "requires a Buffer"),
        (SETUP + "Memory.fill(buf, 'a')\n", "element type"),
        (SETUP + "n: int = Memory.length(b)\n", "requires a Buffer"),
        (SETUP + "Memory.copy(buf, b)\n", "two Buffer"),
        (SETUP + "Memory.free(b)\n", "Unknown Memory operation"),
        (SETUP + "Memory.release(b, 1)\n", "1 argument"),
        (SETUP + "Memory.release(handle=b)\n", "positional"),
        ("x: int = 1\np: Pointer[int] = Memory.borrow(x)\n", "Owned or Shared"),
    ],
)
def test_memory_rejections(source: str, match: str | None) -> None:
    with pytest.raises(UnsupportedPython, match=match):
        parse(source)


def test_memory_operations_carry_no_admission_obligations() -> None:
    program = parse(SETUP + "Memory.release(b)\n")
    for node in program.body.children:
        assert required_contracts(node) == frozenset()


# --- Realization --------------------------------------------------------------


def test_type_spelling_reads_shape_and_ownership_labels() -> None:
    @realizes(mg.Owned)
    class SpellOwned:
        type_name = lambda shape, spell: f"Box<{spell(shape.label.arguments[0])}>"

    @realizes(mg.Buffer)
    class SpellBuffer:
        type_name = lambda shape, spell: f"Vec<{spell(shape.label.arguments[0])}>"

    @realizes(dd.Int)
    class SpellInt:
        type_name = lambda shape, spell: f"i{shape.label.arguments[0]}"

    @realizes(dg.Byte)
    class SpellByte:
        type_name = "u8"

    registry = RealizationRegistry(
        "rustish", (SpellOwned, SpellBuffer, SpellInt, SpellByte)
    )
    program = parse(SETUP)
    single, buffer = (node.symbol.type for node in program.body.children)
    assert registry.type_name(single) == "Box<i32>"
    assert registry.type_name(buffer) == "Box<Vec<u8>>"
    with pytest.raises(ConstructError, match="kind:Shared"):
        registry.type_name(
            last("s: Shared[Int[32]] = Memory.new(Int[32], 7)\n").symbol.type
        )


def test_c_reference_realizer_single_owned_value(tmp_path: Path) -> None:
    code = convert(
        IMPORT
        + "b: Owned[Int[32]] = Memory.new(Int[32], 7)\n"
        + "p: Pointer[Int[32]] = Memory.borrow(b)\n"
        + "if Pointer.load(p) == 7:\n    print('seven')\n"
        + "Memory.release(b)\n",
        realizations=c_kind_bindings(),
    )
    assert "#include <stdlib.h>" in code and "#include <string.h>" in code
    assert "int * b = (int *)memcpy(malloc(sizeof(int)), &(int){7LL}" in code
    assert "free(b);" in code
    result = run_c(code, tmp_path)
    assert result.returncode == 0 and result.stdout == b"seven\n"


@pytest.mark.parametrize(
    "source, match",
    [
        (SETUP, "MemoryNewBuffer"),
        ("s: Shared[Int[32]] = Memory.new(Int[32], 7)\n", "kind:Shared"),
    ],
)
def test_c_reference_realizer_rejects_unsupported_memory_words(
    source: str, match: str
) -> None:
    with pytest.raises(ConstructError, match=match):
        convert(IMPORT + source, realizations=c_kind_bindings())


def test_plain_value_type_equality_ignores_memory_labels() -> None:
    shape = last("b: Owned[Int[32]] = Memory.new(Int[32], 7)\n").symbol.type
    assert shape == ValueType(ValueKind.INTEGER)
