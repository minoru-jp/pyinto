"""Virtual-type vocabulary: carried to Targets as labels, never interpreted."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

import pyinto.kinds.datatypes.detailed as source_datatypes
import pyinto.kinds.memory.detailed as source_memory
from pyinto import PythonFrontend, UnsupportedPython, convert
from pyinto.constructs import (
    AddressOf,
    ClassDefinition,
    ConstructError,
    Initialize,
    KindLabel,
    MappedType,
    NoneAlias,
    NoneAliasComparison,
    PointerLoad,
    PointerStore,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import required_contracts
from pyinto.interfaces import language as lang
from pyinto.model.kinds import ELEMENTS, KindElement
from pyinto.model.kinds.datatypes import detailed as dd
from pyinto.model.kinds.memory import detailed as md
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import C_DECLARATIONS
from tests.support.c_realizer.kinds import c_kind_bindings
from tests.test_construct_pipeline import run_c

IMPORT = (
    "from pyinto.kinds.datatypes.general import Byte\n"
    "from pyinto.kinds.datatypes.detailed import "
    "Array, Char, CodeUnit, Decimal, Enum, Float, Function, Int, Nil, Null, UInt, Void\n"
    "from pyinto.kinds.memory.detailed import Pointer, Ref\n"
    "from pyinto.kinds.declarations.detailed import Implements, Interface, MixIn\n"
)


def parse(source: str):
    return PythonFrontend().parse(IMPORT + source)


def declared(source: str) -> ValueType:
    """The declared type of the last module-level initialization."""
    node = parse(source).body.children[-1]
    assert isinstance(node, Initialize)
    assert isinstance(node.symbol.type, ValueType)
    return node.symbol.type


# --- Source-side vocabulary module -----------------------------------------


def test_source_vocabulary_runs_as_plain_python() -> None:
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - trusted test source
        IMPORT
        + "x: Int[32] = 5\n"
        + "a: Array[UInt[8], 4] = [1, 2, 3, 4]\n"
        + "f: Function[[Int[32]], Void] = print\n"
        + "@Interface\nclass Readable:\n    pass\n"
        + "@Implements(Readable)\nclass File(Readable):\n    pass\n",
        namespace,
    )
    assert namespace["x"] == 5
    assert namespace["a"] == [1, 2, 3, 4]
    assert isinstance(namespace["File"], type)
    assert source_datatypes.Void is None
    assert source_datatypes.Nil is None
    assert source_datatypes.Null is None
    assert repr(source_datatypes.Int[32]) == "pyinto.kinds.datatypes.detailed.Int[32]"


@pytest.mark.parametrize("operation", ["address", "load"])
def test_pointer_operations_are_conversion_only(operation: str) -> None:
    with pytest.raises(RuntimeError, match="conversion only"):
        getattr(source_memory.Pointer, operation)(0)
    with pytest.raises(RuntimeError, match="conversion only"):
        source_memory.Pointer.store(0, 0)


def test_source_and_target_vocabularies_match() -> None:
    from pyinto.frontend.kinds import CLASS_LABELS, MODULES

    words = set().union(*MODULES.values()) - CLASS_LABELS - {"Memory"}
    assert words == {element.name for element in ELEMENTS}
    for module, names in MODULES.items():
        source = __import__(module, fromlist=["__all__"])
        assert set(source.__all__) == names, module


# --- Python-side shapes and labels -----------------------------------------


@pytest.mark.parametrize(
    "annotation, kind, label",
    [
        ("Int[32]", ValueKind.INTEGER, "Int[32]"),
        ("UInt[8]", ValueKind.INTEGER, "UInt[8]"),
        ("Float[16]", ValueKind.FLOAT, "Float[16]"),
        ("Decimal[128]", ValueKind.FLOAT, "Decimal[128]"),
        ("CodeUnit[16]", ValueKind.INTEGER, "CodeUnit[16]"),
        ("Byte", ValueKind.INTEGER, "Byte"),
        ("Char", ValueKind.STRING, "Char"),
        ("Int[512]", ValueKind.INTEGER, "Int[512]"),
        ("Int[7]", ValueKind.INTEGER, "Int[7]"),
        ("Pointer[Int[32]]", ValueKind.INTEGER, "Pointer[Int[32]]"),
        ("Pointer[Void]", ValueKind.INTEGER, "Pointer[Void]"),
        ("Enum[UInt[8]]", ValueKind.INTEGER, "Enum[UInt[8]]"),
    ],
)
def test_word_has_python_kind_and_uninterpreted_label(
    annotation: str, kind: ValueKind, label: str
) -> None:
    value = {
        ValueKind.INTEGER: "0",
        ValueKind.FLOAT: "0.5",
        ValueKind.STRING: "'a'",
    }[kind]
    shape = declared(f"x: {annotation} = {value}\n")
    assert shape.kind is kind
    assert shape.annotation() == label


def test_array_is_a_python_list_with_length_label() -> None:
    shape = declared("a: Array[Int[16], 3] = [1, 2, 3]\n")
    assert shape.kind is ValueKind.LIST
    assert shape.list_type is not None
    assert shape.list_type.element_type.annotation() == "Int[16]"
    assert shape.label == KindLabel("Array", (shape.list_type.element_type, 3))


def test_ref_behaves_as_its_target() -> None:
    shape = declared("x: Int[32] = 1\nr: Ref[Int[32]] = x\n")
    assert shape.kind is ValueKind.INTEGER
    assert shape.annotation() == "Ref[Int[32]]"


def test_function_word_keeps_callable_shape() -> None:
    program = parse(
        "def f(x: int) -> None:\n    return None\ng: Function[[int], Void] = f\n"
    )
    shape = program.body.children[-1].symbol.type
    assert shape.kind is ValueKind.FUNCTION
    assert shape.callable_type is not None
    assert shape.annotation() == "Function[[int], Void]"


@pytest.mark.parametrize("word", ["Void", "Nil", "Null"])
def test_none_alias_words_as_annotation_and_value(word: str) -> None:
    program = parse(f"p: Pointer[Void] = {word}\n")
    node = program.body.children[-1]
    assert isinstance(node.value, NoneAlias)
    assert node.value.variant() == word.lower()
    assert parse(f"def f() -> {word}:\n    return None\n")


def test_labels_do_not_decide_compatibility() -> None:
    program = parse(
        "a: Int[32] = 1\nb: Int[64] = 2\nc: int = 3\na = b\na = c\nc = a\na = a + 1\n"
    )
    assert len(program.body.children) == 7
    assert ValueType(ValueKind.INTEGER, label=KindLabel("Int", (8,))) == (
        ValueType(ValueKind.INTEGER)
    )


def test_none_alias_only_inhabits_labeled_declarations() -> None:
    assert parse("p: Pointer[Int[32]] = Null\nx: Int[8] = Nil\n")
    with pytest.raises(UnsupportedPython):
        parse("x: int = Null\n")
    with pytest.raises(UnsupportedPython):
        parse("p: Pointer[Int[32]] = None\n")


# --- Pointer operations and comparisons ------------------------------------


def test_pointer_operations_build_model_nodes() -> None:
    program = parse(
        "x: Int[32] = 1\n"
        "p: Pointer[Int[32]] = Pointer.address(x)\n"
        "y: Int[32] = Pointer.load(p)\n"
        "Pointer.store(p, 5)\n"
        "Pointer.store(p, Pointer.load(p) + 1)\n"
    )
    _, address, load, store, _ = program.body.children
    assert isinstance(address.value, AddressOf)
    assert address.value.value_type.annotation() == "Pointer[Int[32]]"
    assert isinstance(load.value, PointerLoad)
    assert load.value.value_type.annotation() == "Int[32]"
    assert isinstance(store, PointerStore)


def test_none_alias_comparison() -> None:
    program = parse("p: Pointer[Int[32]] = Null\nif p != Null:\n    print('x')\n")
    condition = program.body.children[-1].condition
    assert isinstance(condition, NoneAliasComparison)
    assert condition.operator == "!="


@pytest.mark.parametrize(
    "source, match",
    [
        ("x: int = 1\np: int = Pointer.load(x)\n", "Pointer\\[T\\]"),
        ("p: int = Pointer.address(1)\n", "variable name"),
        ("x: Int[32] = 1\np: int = Pointer.store(x, 1)\n", "statement"),
        ("x: Int[32] = 1\nPointer.store(x, 1)\n", "Pointer\\[T\\]"),
        ("x: Int[32] = 1\np: int = Pointer.address(x, x)\n", "1 argument"),
        ("x: Int[32] = 1\np: int = Pointer.move(x)\n", "Unknown Pointer operation"),
        ("x: Int[32] = 1\nif x == Null:\n    pass\n", None),
        ("p: Pointer[Int[32]] = Null\nif p < Null:\n    pass\n", "== and !="),
        ("x: int = 1\nif x == Null:\n    pass\n", "kind-labeled"),
    ],
)
def test_pointer_and_comparison_rejections(source: str, match: str | None) -> None:
    if match is None:  # a labeled operand may be compared with a None alias
        assert parse(source)
        return
    with pytest.raises(UnsupportedPython, match=match):
        parse(source)


# --- Ref bindings ----------------------------------------------------------


def test_ref_binds_only_to_variables() -> None:
    assert parse("x: Int[32] = 1\nr: Ref[Int[32]] = x\nr = 5\n")
    with pytest.raises(UnsupportedPython):
        parse("r: Ref[Int[32]] = 5\n")
    program = parse(
        "def bump(r: Ref[Int[32]]) -> None:\n    r = r + 1\nx: Int[32] = 1\nbump(x)\n"
    )
    assert program
    with pytest.raises(UnsupportedPython):
        parse("def bump(r: Ref[Int[32]]) -> None:\n    r = r + 1\nbump(1)\n")


# --- Annotation and import rejections -------------------------------------


@pytest.mark.parametrize(
    "source, match",
    [
        ("x: Int = 1\n", "requires arguments"),
        ("x: Int[0] = 1\n", "positive integer"),
        ("x: Int[True] = 1\n", "positive integer"),
        ("x: Int[32, 8] = 1\n", "exactly one size"),
        ("x: Byte[8] = 1\n", "takes no arguments"),
        ("x: Array[int] = [1]\n", "element type and a length"),
        ("x: Pointer[Int[32], Int[8]] = 1\n", "exactly one type"),
        ("x: Function[int, int] = 1\n", "parameter list"),
        ("x: Interface = 1\n", "class decorator"),
        ("x: int = Int\n", "not a value"),
    ],
)
def test_annotation_rejections(source: str, match: str) -> None:
    with pytest.raises(UnsupportedPython, match=match):
        parse(source)


@pytest.mark.parametrize(
    "source, match",
    [
        ("import pyinto.kinds.datatypes.detailed\n", "from pyinto.kinds"),
        ("from pyinto.kinds import datatypes\n", "Import kinds from one of"),
        ("from pyinto.kinds.datatypes import detailed\n", "Import kinds from one of"),
        ("from pyinto.kinds.datatypes.detailed import Opaque\n", "not in"),
        (
            "from pyinto.kinds.datatypes.general import Int\n",
            "import it from pyinto.kinds.datatypes.detailed",
        ),
        ("from pyinto.kinds.datatypes.detailed import Int as int\n", "Reserved"),
        (
            (
                "from pyinto.kinds.datatypes.detailed import Int\n"
                "from pyinto.kinds.datatypes.detailed import Int\n"
            ),
            "Duplicate",
        ),
    ],
)
def test_import_rejections(source: str, match: str) -> None:
    with pytest.raises(UnsupportedPython, match=match):
        PythonFrontend().parse(source)


def test_import_alias_is_honored() -> None:
    program = PythonFrontend().parse(
        "from pyinto.kinds.datatypes.detailed import Int as I32\nx: I32[32] = 1\n"
    )
    assert program.body.children[0].symbol.type.annotation() == "Int[32]"


# --- Class decorators ------------------------------------------------------

CLASSES = (
    "@Interface\nclass Readable:\n    def __init__(self) -> None:\n        pass\n"
    "@MixIn\nclass Logging:\n    def __init__(self) -> None:\n        pass\n"
)


def test_class_decorators_are_recorded_in_source_order() -> None:
    program = parse(
        CLASSES
        + "@MixIn\n@Implements(Readable, Logging)\nclass File(Readable):\n"
        + "    def __init__(self) -> None:\n        super().__init__()\n"
    )
    readable, logging, file = program.body.children
    assert isinstance(file, ClassDefinition)
    assert [label.name for label in readable.labels] == ["Interface"]
    assert [label.name for label in logging.labels] == ["MixIn"]
    assert [label.annotation() for label in file.labels] == [
        "MixIn",
        "Implements[Readable, Logging]",
    ]


def test_class_decorator_combines_with_registered_decorator() -> None:
    program = PythonFrontend().parse(
        "from dataclasses import dataclass\n"
        "from pyinto.kinds.declarations.detailed import Interface\n"
        "@Interface\n@dataclass\nclass Point:\n    x: int\n"
    )
    assert [label.name for label in program.body.children[0].labels] == ["Interface"]


@pytest.mark.parametrize(
    "decorators, match",
    [
        ("@Implements(Missing)\n", "declared earlier"),
        ("@Implements()\n", "one or more"),
        ("@Implements\n", "requires class arguments"),
        ("@Interface()\n", "takes no arguments"),
        ("@Interface\n@Interface\n", "Duplicate"),
        ("@Int\n", "not a class decorator"),
    ],
)
def test_class_decorator_rejections(decorators: str, match: str) -> None:
    with pytest.raises(UnsupportedPython, match=match):
        parse(decorators + "class A:\n    def __init__(self) -> None:\n        pass\n")


# --- Admission ---------------------------------------------------------------


def test_python_semantics_are_not_required_for_kind_operands() -> None:
    plain = PythonFrontend().parse("x: int = 1\ny: int = x & 3\n")
    labeled = parse("x: UInt[8] = 1\ny: int = x & 3\n")
    assert "integer.bitwise.unbounded" in required_contracts(
        plain.body.children[-1].value
    )
    assert required_contracts(labeled.body.children[-1].value) == frozenset()


# --- Realization -------------------------------------------------------------


def _registry(*entries: type) -> RealizationRegistry:
    return RealizationRegistry("demo", entries)


def test_type_spelling_uses_the_kind_word() -> None:
    @realizes(dd.Int)
    class SpellInt:
        type_name = lambda shape, spell: f"i{shape.label.arguments[0]}"

    @realizes(md.Pointer)
    class SpellPointer:
        type_name = lambda shape, spell: spell(shape.label.arguments[0]) + "*"

    @realizes(vt_integer())
    class SpellInteger:
        type_name = "bigint"

    registry = _registry(SpellInt, SpellPointer, SpellInteger)
    shape = declared("p: Pointer[Int[32]] = Null\n")
    # A nested label equal to its parent under ValueType equality is not cyclic.
    assert registry.type_name(shape) == "i32*"
    assert registry.type_name(ValueType(ValueKind.INTEGER)) == "bigint"
    with pytest.raises(ConstructError, match="kind:UInt"):
        registry.type_name(declared("x: UInt[8] = 1\n"))


def vt_integer():
    from pyinto.model import value_types as vt

    return vt.Integer


def test_realizes_accepts_only_published_kind_elements() -> None:
    @realizes(KindElement("Opaque", "detailed"))
    class Bogus:
        type_name = "x"

    with pytest.raises(ValueError, match="realizes requires"):
        _registry(Bogus)


def test_none_alias_variants_are_finite() -> None:
    assert lang.NoneAlias.variant_domain() == {"void", "nil", "null"}


def test_new_constructs_carry_no_admission_obligations() -> None:
    x = Symbol(
        "x", ValueType(ValueKind.INTEGER, label=KindLabel("Int", (8,))), "Int[8]"
    )
    node = AddressOf(Reference(x))
    assert required_contracts(node) == frozenset()
    assert required_contracts(PointerLoad(node)) == frozenset()


# --- C reference Realizer ----------------------------------------------------

C_PROGRAM = (
    "x: Int[32] = 41\n"
    "p: Pointer[Int[32]] = Pointer.address(x)\n"
    "Pointer.store(p, 42)\n"
    "q: Pointer[Int[32]] = Null\n"
    "if q == Null:\n    print('null')\n"
    "if Pointer.load(p) == 42:\n    print('stored')\n"
    "b: Byte = 200\n"
    "if b == 200:\n    print('byte')\n"
)


def test_c_reference_realizer_compiles_and_runs(tmp_path: Path) -> None:
    code = convert(IMPORT + C_PROGRAM, realizations=c_kind_bindings())
    assert "int x = 41LL;" in code
    assert "int * p = (&x);" in code
    assert "*p = 42LL;" in code
    assert "int * q = ((void *)0);" in code
    assert "unsigned char b = 200LL;" in code
    result = run_c(code, tmp_path)
    assert result.returncode == 0
    assert result.stdout == b"null\nstored\nbyte\n"


def test_c_reference_realizer_rejects_unsupported_words() -> None:
    with pytest.raises(ConstructError, match="no Int\\[128\\]"):
        convert(IMPORT + "x: Int[128] = 1\n", realizations=c_kind_bindings())
    with pytest.raises(ConstructError, match="kind:Array"):
        c_kind_bindings().type_name(declared("a: Array[Int[32], 2] = [1, 2]\n"))
    with pytest.raises(ConstructError):
        convert(IMPORT + "p: Pointer[Int[32]] = Nil\n", realizations=c_kind_bindings())


def test_plain_c_target_rejects_kinds() -> None:
    from tests.support.c_realizer import c_bindings

    assert len(C_DECLARATIONS) == 22
    with pytest.raises(ConstructError, match="kind:Int"):
        convert(IMPORT + "x: Int[32] = 1\n", realizations=c_bindings())


# --- Mapped type shape ------------------------------------------------------


def test_mapped_type_holds_only_source_and_variant() -> None:
    assert [item.name for item in fields(MappedType)] == ["source", "variant"]


def test_public_example_generates_compilable_c(tmp_path: Path) -> None:
    from examples.kinds_demo import SOURCE

    code = convert(SOURCE, realizations=c_kind_bindings())
    result = run_c(code, tmp_path)
    assert result.stdout == (
        b"no spare\nstored through pointer\nowned value\ngeneral kinds\n"
    )
