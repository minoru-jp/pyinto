"""External memory Port declaration and replaceable C target representations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from pyinto.admission import AdmissionDeclaration, AdmissionRule
from pyinto.constructs import (
    Construct,
    ConstructError,
    Identifier,
    Literal,
    PortType,
    Reference,
    Symbol,
    Value,
    ValueKind,
)
from pyinto.interface_mapping import (
    InterfaceClassMapping,
    InterfaceMappingRegistry,
    InterfaceMethodMapping,
)
from pyinto.realizations import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    pack_entries,
    pack_target,
    realizes,
    render,
    requires,
    supports,
    template,
    type_name,
)
from tests.support.c_realizer import C_DECLARATIONS

PORT_SOURCE = "demo_memory_ports.memory.ManualMemoryRegion"
PORT_KEY = f"port:{PORT_SOURCE}.integer"


@dataclass(frozen=True)
class ManualMemoryRegion(Construct):
    symbol: Symbol
    minimum: int
    maximum: int
    HOLES = frozenset({"name"})

    def parts(self) -> Mapping[str, object]:
        return {"name": Identifier(self.symbol.name)}


@dataclass(frozen=True)
class MemoryAssign(Construct):
    receiver: Reference
    value: Value
    HOLES = frozenset({"receiver", "value"})

    def parts(self) -> Mapping[str, object]:
        return {"receiver": self.receiver, "value": self.value}


@dataclass(frozen=True)
class MemoryRelease(Construct):
    receiver: Reference
    HOLES = frozenset({"receiver"})

    def parts(self) -> Mapping[str, object]:
        return {"receiver": self.receiver}


@dataclass(frozen=True)
class MemoryValue(Value):
    receiver: Reference
    HOLES = frozenset({"receiver"})

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"receiver": self.receiver}


MEMORY_ADMISSIONS = (
    AdmissionDeclaration(
        ManualMemoryRegion,
        (
            AdmissionRule(
                "memory_region_bounds",
                (ManualMemoryRegion,),
                frozenset({"minimum", "maximum"}),
                frozenset({"memory.region.bounds"}),
                lambda _node: frozenset({"memory.region.bounds"}),
            ),
        ),
    ),
    AdmissionDeclaration(
        MemoryAssign,
        (
            AdmissionRule(
                "memory_assign",
                (MemoryAssign,),
                frozenset(),
                frozenset({"memory.value.assignment"}),
                lambda _node: frozenset({"memory.value.assignment"}),
            ),
        ),
    ),
    AdmissionDeclaration(
        MemoryRelease,
        (
            AdmissionRule(
                "memory_release",
                (MemoryRelease,),
                frozenset(),
                frozenset({"memory.region.release"}),
                lambda _node: frozenset({"memory.region.release"}),
            ),
        ),
    ),
    AdmissionDeclaration(MemoryValue),
)


def _construct(symbol: Symbol, constraints: Mapping[str, int]) -> ManualMemoryRegion:
    if set(constraints) != {"minimum", "maximum"}:
        raise ValueError("integer Port requires minimum and maximum")
    minimum, maximum = constraints["minimum"], constraints["maximum"]
    if minimum > maximum:
        raise ValueError("minimum must not exceed maximum")
    return ManualMemoryRegion(symbol, minimum, maximum)


def _assign(
    origin: Construct, receiver: Reference, arguments: tuple[Value, ...]
) -> MemoryAssign:
    if not isinstance(origin, ManualMemoryRegion):
        raise TypeError("Invalid memory origin")
    value = arguments[0]
    if isinstance(value, Literal) and (
        type(value.value) is not int
        or not origin.minimum <= value.value <= origin.maximum
    ):
        raise ValueError("assigned literal is outside the declared integer range")
    return MemoryAssign(receiver, value)


def _value(origin: Construct, receiver: Reference) -> MemoryValue:
    if not isinstance(origin, ManualMemoryRegion):
        raise TypeError("Invalid memory origin")
    return MemoryValue(receiver)


def _release(
    origin: Construct, receiver: Reference, arguments: tuple[Value, ...]
) -> MemoryRelease:
    if not isinstance(origin, ManualMemoryRegion) or arguments:
        raise TypeError("Invalid memory release")
    return MemoryRelease(receiver)


def interface_mapping_registry() -> InterfaceMappingRegistry:
    return InterfaceMappingRegistry(
        (
            InterfaceClassMapping(
                source=PORT_SOURCE,
                constructors={"integer": _construct},
                methods={
                    "assign": InterfaceMethodMapping((ValueKind.INTEGER,), _assign),
                    "release": InterfaceMethodMapping((), _release),
                },
                properties={"value": _value},
            ),
        ),
        admission_declarations=MEMORY_ADMISSIONS,
    )


def _integer_type(lower: int, upper: int, *, wide: bool = False) -> str:
    if lower < -(2**63) or upper > 2**64 - 1 or lower > upper:
        raise ConstructError("The C memory binding cannot represent this integer range")
    widths = (64,) if wide else (8, 16, 32, 64)
    if lower >= 0:
        for bits in widths:
            if upper <= 2**bits - 1:
                return f"uint{bits}_t"
    else:
        for bits in widths:
            if lower >= -(2 ** (bits - 1)) and upper <= 2 ** (bits - 1) - 1:
                return f"int{bits}_t"
    raise ConstructError("The C memory binding cannot represent this integer range")


def _representation(shape: object, *, wide: bool = False) -> str:
    if not isinstance(shape, PortType) or shape.key != PORT_KEY:
        raise ConstructError("Incompatible Port type binding")
    options = shape.options()
    return _integer_type(options["minimum"], options["maximum"], wide=wide) + " *"


def _compact(node: Construct, ctx: EmitContext) -> str:
    if not isinstance(node, ManualMemoryRegion) or node.symbol.port_type is None:
        raise ConstructError("Incompatible memory binding")
    storage = _representation(node.symbol.port_type).removesuffix(" *")
    return f"{storage} *${{name}} = malloc(sizeof *${{name}});"


def _wide(node: Construct, ctx: EmitContext) -> str:
    if not isinstance(node, ManualMemoryRegion) or node.symbol.port_type is None:
        raise ConstructError("Incompatible memory binding")
    storage = _representation(node.symbol.port_type, wide=True).removesuffix(" *")
    return f"{storage} *${{name}} = malloc(sizeof *${{name}});"


@realizes(ManualMemoryRegion)
class CManualMemoryRegion:
    supports @= ("memory.region.bounds",)
    requires @= "stdint.h"
    requires @= "stdlib.h"
    render @= _compact


@realizes(ManualMemoryRegion)
class CWideManualMemoryRegion:
    supports @= ("memory.region.bounds",)
    requires @= "stdint.h"
    requires @= "stdlib.h"
    render @= _wide


@realizes(PortType(PORT_SOURCE, "integer", ()))
class CMemoryPortType:
    type_name @= lambda shape, spell: _representation(shape)


@realizes(PortType(PORT_SOURCE, "integer", ()))
class CWideMemoryPortType:
    type_name @= lambda shape, spell: _representation(shape, wide=True)


@realizes(MemoryAssign)
class CMemoryAssign:
    supports @= ("memory.value.assignment",)
    template @= "*${receiver} = ${value};"


@realizes(MemoryValue)
class CMemoryValue:
    template @= "(*${receiver})"


@realizes(MemoryRelease)
class CMemoryRelease:
    supports @= ("memory.region.release",)
    template @= "free(${receiver});"


class CMemoryPack:
    pack_target @= "c"
    pack_entries @= (
        *C_DECLARATIONS,
        CManualMemoryRegion,
        CMemoryPortType,
        CMemoryAssign,
        CMemoryValue,
        CMemoryRelease,
    )


class CWideMemoryPack:
    pack_target @= "c"
    pack_entries @= (
        *C_DECLARATIONS,
        CWideManualMemoryRegion,
        CWideMemoryPortType,
        CMemoryAssign,
        CMemoryValue,
        CMemoryRelease,
    )


@lru_cache(maxsize=1)
def c_memory_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(CMemoryPack)


@lru_cache(maxsize=1)
def c_wide_memory_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(CWideMemoryPack)
