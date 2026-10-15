"""Developer-only C spellings for a subset of the kinds vocabulary.

This reference Realizer chooses C builtin types for the words it supports and
explicitly rejects the rest. The choices are this Target's own; the Host gives
kinds no meaning.
"""

from __future__ import annotations

from functools import lru_cache

from pyinto.constructs import ConstructError, ValueType
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.model.kinds import profile
from pyinto.model.kinds.datatypes import detailed as dd
from pyinto.model.kinds.datatypes import general as dg
from pyinto.model.kinds.memory import detailed as md
from pyinto.model.kinds.memory import general as mg
from pyinto.realizations.registry import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer.pack import C_DECLARATIONS

_INT = {8: "signed char", 16: "short", 32: "int", 64: "long long"}
_UINT = {
    8: "unsigned char",
    16: "unsigned short",
    32: "unsigned int",
    64: "unsigned long long",
}
_FLOAT = {32: "float", 64: "double"}
_CODE_UNIT = {8: "char"}


def _sized(table: dict[int, str]):
    def spell(shape: object, _spell: object) -> str:
        assert isinstance(shape, ValueType) and shape.label is not None
        size = shape.label.arguments[0]
        if size not in table:
            raise ConstructError(
                f"C reference Realizer has no {shape.label.name}[{size}]"
            )
        return table[size]  # type: ignore[index]

    return spell


def _pointer(shape: object, spell) -> str:  # type: ignore[no-untyped-def]
    assert isinstance(shape, ValueType) and shape.label is not None
    return spell(shape.label.arguments[0]) + " *"


# General vocabulary. This reference Target reads ``int`` as ``long long`` (in
# the base C pack) and ``float`` as ``double``; Narrow/Wide step from there.
_INTEGER_RANKS = {0: "long long", -1: "int", -2: "short", -3: "signed char"}
_FLOAT_RANKS = {1: "long double", 0: "double", -1: "float"}


def _numeric(shape: object, _spell: object) -> str:
    assert isinstance(shape, ValueType)
    found = profile(shape)
    table = (
        _INTEGER_RANKS
        if found is not None and found.base is vt.Integer
        else _FLOAT_RANKS
    )
    if found is None or found.rank not in table:
        raise ConstructError(f"C reference Realizer has no {shape.annotation()}")
    spelled = table[found.rank]
    if found.unsigned:
        return "unsigned char" if spelled == "signed char" else "unsigned " + spelled
    return spelled


@realizes(vt.Floating)
class CKindFloatBase:
    type_name = "double"


@realizes(dg.Wide)
class CKindWide:
    type_name = _numeric


@realizes(dg.Narrow)
class CKindNarrow:
    type_name = _numeric


@realizes(dg.Unsigned)
class CKindUnsigned:
    type_name = _numeric


@realizes(dg.Size)
class CKindSize:
    requires = ("stddef.h",)
    type_name = "size_t"


@realizes(dg.Index)
class CKindIndex:
    requires = ("stddef.h",)
    type_name = "ptrdiff_t"


@realizes(dd.Int)
class CKindInt:
    type_name = _sized(_INT)


@realizes(dd.UInt)
class CKindUInt:
    type_name = _sized(_UINT)


@realizes(dd.Float)
class CKindFloat:
    type_name = _sized(_FLOAT)


@realizes(dd.CodeUnit)
class CKindCodeUnit:
    type_name = _sized(_CODE_UNIT)


@realizes(dg.Byte)
class CKindByte:
    type_name = "unsigned char"


@realizes(dd.Void)
class CKindVoid:
    type_name = "void"


@realizes(md.Pointer)
class CKindPointer:
    type_name = _pointer


def _owned(shape: object, spell) -> str:  # type: ignore[no-untyped-def]
    assert isinstance(shape, ValueType) and shape.label is not None
    inner = shape.label.arguments[0]
    assert isinstance(inner, ValueType)
    if inner.label is not None and inner.label.name == "Buffer":
        raise ConstructError("C reference Realizer has no Owned[Buffer[T]]")
    return spell(inner) + " *"


def _memory_new(node: object, context: object) -> str:
    from pyinto.realizations.registry import EmitContext

    assert isinstance(node, lang.MemoryNew) and isinstance(context, EmitContext)
    spelled = context.type_name(node.element_type)
    return (
        f"({spelled} *)memcpy(malloc(sizeof({spelled})), "
        f"&({spelled}){{${{value}}}}, sizeof({spelled}))"
    )


@realizes(mg.Owned)
class CKindOwned:
    type_name = _owned


@realizes(lang.MemoryNew)
class CMemoryNew:
    requires = ("stdlib.h", "string.h")
    render = _memory_new


@realizes(lang.MemoryRelease)
class CMemoryRelease:
    variant = "single"
    template = "free(${handle});"


@realizes(lang.MemoryBorrow)
class CMemoryBorrow:
    variant = "single"
    template = "${handle}"


@realizes(lang.AddressOf)
class CAddressOf:
    template = "(&${target})"


@realizes(lang.PointerLoad)
class CPointerLoad:
    template = "(*${pointer})"


@realizes(lang.PointerStore)
class CPointerStore:
    template = "*${pointer} = ${value};"


@realizes(lang.NoneAlias)
class CNull:
    variant = "null"
    template = "((void *)0)"


@realizes(lang.NoneAliasComparison)
class CNullComparison:
    template = "(${left} ${op} ${right})"


C_KIND_DECLARATIONS = (
    CKindFloatBase,
    CKindWide,
    CKindNarrow,
    CKindUnsigned,
    CKindSize,
    CKindIndex,
    CKindInt,
    CKindUInt,
    CKindFloat,
    CKindCodeUnit,
    CKindByte,
    CKindVoid,
    CKindPointer,
    CAddressOf,
    CPointerLoad,
    CPointerStore,
    CNull,
    CNullComparison,
    CKindOwned,
    CMemoryNew,
    CMemoryRelease,
    CMemoryBorrow,
)


class CKindTargetPack:
    target = "c"
    entries = (*C_DECLARATIONS, *C_KIND_DECLARATIONS)
    dispatch = "composition"
    session = TextArtifactSession


@lru_cache(maxsize=1)
def c_kind_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(CKindTargetPack)
