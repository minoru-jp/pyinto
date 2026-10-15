"""General datatype kinds: relative size, sign and roles, and Target support."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyinto import PythonFrontend, UnsupportedPython, convert, realize
from pyinto.constructs import ConstructError, Initialize, ValueKind, ValueType
from pyinto.constructs.admission import required_contracts
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.model.kinds import GENERAL_ELEMENTS, missing_general, profile
from pyinto.model.kinds.datatypes import general as dg
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer.kinds import c_kind_bindings
from tests.test_construct_pipeline import run_c

IMPORT = (
    "from pyinto.kinds.datatypes.general import "
    "Byte, Index, Narrow, Size, Unsigned, Wide\n"
)


def declared(source: str) -> ValueType:
    node = PythonFrontend().parse(IMPORT + source).body.children[-1]
    assert isinstance(node, Initialize) and isinstance(node.symbol.type, ValueType)
    return node.symbol.type


@pytest.mark.parametrize(
    "annotation, value, base, rank, unsigned",
    [
        ("int", "1", ValueKind.INTEGER, 0, False),
        ("Wide[int]", "1", ValueKind.INTEGER, 1, False),
        ("Wide[Wide[int]]", "1", ValueKind.INTEGER, 2, False),
        ("Narrow[int]", "1", ValueKind.INTEGER, -1, False),
        ("Narrow[Narrow[Narrow[int]]]", "1", ValueKind.INTEGER, -3, False),
        ("Unsigned[int]", "1", ValueKind.INTEGER, 0, True),
        ("Unsigned[Wide[int]]", "1", ValueKind.INTEGER, 1, True),
        ("Unsigned[Narrow[Narrow[int]]]", "1", ValueKind.INTEGER, -2, True),
        ("float", "1.5", ValueKind.FLOAT, 0, False),
        ("Wide[float]", "1.5", ValueKind.FLOAT, 1, False),
        ("Narrow[float]", "1.5", ValueKind.FLOAT, -1, False),
    ],
)
def test_refinements_keep_python_kind_and_read_as_profile(
    annotation: str, value: str, base: ValueKind, rank: int, unsigned: bool
) -> None:
    shape = declared(f"x: {annotation} = {value}\n")
    assert shape.kind is base
    found = profile(shape)
    assert found is not None
    assert (found.base, found.rank, found.unsigned) == (base, rank, unsigned)
    if annotation not in {"int", "float"}:
        assert shape.annotation() == annotation


@pytest.mark.parametrize("word", ["Size", "Index", "Byte"])
def test_roles_are_integers_without_a_numeric_profile(word: str) -> None:
    shape = declared(f"x: {word} = 1\n")
    assert shape.kind is ValueKind.INTEGER
    assert shape.label is not None and shape.label.name == word
    assert profile(shape) is None


@pytest.mark.parametrize(
    "annotation, match",
    [
        ("Wide[Unsigned[int]]", "outermost"),
        ("Narrow[Unsigned[int]]", "outermost"),
        ("Wide[Narrow[int]]", "cannot be mixed"),
        ("Narrow[Wide[float]]", "cannot be mixed"),
        ("Unsigned[float]", "only to integers"),
        ("Unsigned[Narrow[float]]", "only to integers"),
        ("Unsigned[Unsigned[int]]", "Unsigned applies only to int"),
        ("Unsigned[Size]", "Unsigned applies only to int"),
        ("Wide[Size]", "Wide applies only to int, float or Wide"),
        ("Wide[str]", "only to int or float"),
        ("Wide[int, int]", "exactly one type"),
        ("Wide", "requires arguments"),
        ("Size[8]", "takes no arguments"),
    ],
)
def test_one_spelling_per_meaning(annotation: str, match: str) -> None:
    value = "'a'" if "str" in annotation else "1"
    with pytest.raises(UnsupportedPython, match=match):
        declared(f"x: {annotation} = {value}\n")


def test_labels_do_not_decide_compatibility() -> None:
    program = PythonFrontend().parse(
        IMPORT + "a: Wide[int] = 1\nb: Narrow[int] = 2\nc: Size = 3\n"
        "a = b\nb = c\nc = a + 1\n"
    )
    assert len(program.body.children) == 6


def test_general_kinds_waive_python_semantic_obligations() -> None:
    program = PythonFrontend().parse(IMPORT + "x: Narrow[int] = 1\ny: int = x & 3\n")
    assert required_contracts(program.body.children[-1].value) == frozenset()


# --- Type spelling, requirements and coverage -------------------------------


def _spellings() -> tuple[type, ...]:
    @realizes(dg.Size)
    class SpellSize:
        type_name = "usize"

    @realizes(dg.Wide)
    class SpellWide:
        type_name = lambda shape, spell: f"wide{profile(shape).rank}"

    return (SpellSize, SpellWide)


def test_type_spelling_reads_the_general_word() -> None:
    registry = RealizationRegistry("demo", _spellings())
    assert registry.type_name(declared("x: Size = 1\n")) == "usize"
    assert registry.type_name(declared("x: Wide[Wide[int]] = 1\n")) == "wide2"
    with pytest.raises(ConstructError, match="kind:Narrow"):
        registry.type_name(declared("x: Narrow[int] = 1\n"))


def test_type_spelling_requirements_reach_the_artifact() -> None:
    code = convert(IMPORT + "n: Size = 3\n", realizations=c_kind_bindings())
    assert code.startswith("#include <stddef.h>\nint main(void) {")
    assert "size_t n = 3LL;" in code
    assert c_kind_bindings().type_requirements(declared("n: Index = 1\n")) == {
        "stddef.h"
    }


def test_requirements_from_each_used_spelling() -> None:
    from tests.support.c_realizer.pack import CBlock, CInitialize, CIntegerLiteral

    @realizes(dg.Size)
    class SpellSize:
        requires = ("sizes.h",)
        type_name = "size_t"

    @realizes(lang.Program)
    class Program:
        template = "${requirements}\n${body}"

    @realizes(vt.Integer)
    class Integer:
        type_name = "long"

    @realizes(dg.Narrow)
    class SpellNarrow:
        requires = ("narrow.h",)
        type_name = lambda shape, spell: "short"

    registry = RealizationRegistry(
        "c",
        (
            Program,
            CBlock,
            CInitialize,
            CIntegerLiteral,
            SpellSize,
            Integer,
            SpellNarrow,
        ),
    )
    program = PythonFrontend().parse(IMPORT + "a: Size = 1\nb: Narrow[int] = 2\n")
    code = realize(program, realizations=registry)
    assert code.startswith("narrow.h\nsizes.h\n")


def test_requirements_of_an_unregistered_spelling_are_an_error() -> None:
    registry = RealizationRegistry("demo", _spellings())
    with pytest.raises(ConstructError, match="kind:Index"):
        registry.type_requirements(declared("x: Index = 1\n"))


def test_missing_general_reports_what_a_target_lacks() -> None:
    missing = missing_general(c_kind_bindings())
    assert missing == (
        "None",
        "list",
        "dict",
        "tuple",
        "Callable",
        "class",
        "Buffer",
        "Shared",
        "MemoryNewBuffer",
        "MemoryResize",
        "MemoryLength",
        "MemoryCopy",
        "MemoryFill",
    )
    assert {"Wide", "Narrow", "Unsigned", "Size", "Index", "Byte", "Owned"} <= {
        element.name for element in GENERAL_ELEMENTS
    }


def test_missing_general_is_empty_for_a_complete_target() -> None:
    entries: list[type] = []
    for kind in (
        vt.Integer,
        vt.Floating,
        vt.String,
        vt.Boolean,
        vt.NoneValue,
        vt.List,
        vt.Dictionary,
        vt.Tuple,
        vt.Function,
        vt.Instance,
        *GENERAL_ELEMENTS,
    ):

        @realizes(kind)
        class Spell:
            type_name = "t"

        entries.append(Spell)
    for construct in (
        lang.MemoryNew,
        lang.MemoryNewBuffer,
        lang.MemoryRelease,
        lang.MemoryResize,
        lang.MemoryLength,
        lang.MemoryBorrow,
        lang.MemoryCopy,
        lang.MemoryFill,
    ):

        @realizes(construct)
        class Realize:
            variant = "*"
            template = "x"

        entries.append(Realize)
    assert missing_general(RealizationRegistry("complete", tuple(entries))) == ()


# --- C reference Realizer ------------------------------------------------------


def test_c_reference_realizer_interprets_general_words(tmp_path: Path) -> None:
    source = (
        IMPORT
        + "a: int = 1\nb: Narrow[int] = 2\nc: Narrow[Narrow[int]] = 3\n"
        + "d: Unsigned[Narrow[Narrow[Narrow[int]]]] = 4\ne: Size = 5\n"
        + "f: Index = 6\ng: Byte = 7\nh: Unsigned[int] = 8\n"
        + "".join(
            "    " * depth + f"if {name} == {value}:\n"
            for depth, (name, value) in enumerate(
                zip("abcdefgh", (1, 2, 3, 4, 5, 6, 7, 8), strict=True)
            )
        )
        + "    " * 8
        + "print('general')\n"
    )
    code = convert(source, realizations=c_kind_bindings())
    for line in (
        "long long a = 1LL;",
        "int b = 2LL;",
        "short c = 3LL;",
        "unsigned char d = 4LL;",
        "size_t e = 5LL;",
        "ptrdiff_t f = 6LL;",
        "unsigned char g = 7LL;",
        "unsigned long long h = 8LL;",
    ):
        assert line in code
    result = run_c(code, tmp_path)
    assert result.returncode == 0 and result.stdout == b"general\n"


@pytest.mark.parametrize(
    "annotation, value, spelled",
    [
        ("float", "1.5", "double"),
        ("Narrow[float]", "1.5", "float"),
        ("Wide[float]", "1.5", "long double"),
    ],
)
def test_c_reference_realizer_float_steps(
    annotation: str, value: str, spelled: str
) -> None:
    assert c_kind_bindings().type_name(declared(f"x: {annotation} = {value}\n")) == (
        spelled
    )


def test_c_reference_realizer_rejects_steps_it_cannot_represent() -> None:
    with pytest.raises(ConstructError, match="no Wide\\[int\\]"):
        c_kind_bindings().type_name(declared("x: Wide[int] = 1\n"))
    with pytest.raises(ConstructError, match="no Narrow"):
        c_kind_bindings().type_name(
            declared("x: Narrow[Narrow[Narrow[Narrow[int]]]] = 1\n")
        )
