"""Developer-only class mapping fixture: an external counter object.

It exercises the Interface Mapping class route (constructor, methods, a
property, explicit cleanup, aliases) with a C reference realization. The
counter domain is arbitrary; nothing here models memory management.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from pyinto.admission import AdmissionDeclaration, AdmissionRule
from pyinto.constructs import (
    Construct,
    Identifier,
    MappedType,
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
from pyinto.realizations.registry import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import C_DECLARATIONS

SOURCE = "fixture_counter.Counter"
IMPORT = "from fixture_counter import Counter\n"


@dataclass(frozen=True)
class CounterOpen(Construct):
    symbol: Symbol
    HOLES = frozenset({"name"})

    def parts(self) -> Mapping[str, object]:
        return {"name": Identifier(self.symbol.name)}


@dataclass(frozen=True)
class CounterAdd(Construct):
    receiver: Reference
    value: Value
    HOLES = frozenset({"receiver", "value"})

    def parts(self) -> Mapping[str, object]:
        return {"receiver": self.receiver, "value": self.value}


@dataclass(frozen=True)
class CounterValue(Value):
    receiver: Reference
    HOLES = frozenset({"receiver"})

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"receiver": self.receiver}


@dataclass(frozen=True)
class CounterClose(Construct):
    receiver: Reference
    HOLES = frozenset({"receiver"})

    def parts(self) -> Mapping[str, object]:
        return {"receiver": self.receiver}


def _rule(name: str, construct: type[Construct], contract: str) -> AdmissionRule:
    return AdmissionRule(
        name,
        (construct,),
        frozenset(),
        frozenset({contract}),
        lambda _: frozenset({contract}),
    )


COUNTER_ADMISSIONS = (
    AdmissionDeclaration(
        CounterOpen, (_rule("counter_open", CounterOpen, "counter.open"),)
    ),
    AdmissionDeclaration(
        CounterAdd, (_rule("counter_add", CounterAdd, "counter.add"),)
    ),
    AdmissionDeclaration(
        CounterClose, (_rule("counter_close", CounterClose, "counter.close"),)
    ),
    AdmissionDeclaration(CounterValue),
)


def _open(symbol: Symbol) -> CounterOpen:
    return CounterOpen(symbol)


def _add(
    origin: Construct, receiver: Reference, arguments: tuple[Value, ...]
) -> CounterAdd:
    if not isinstance(origin, CounterOpen):
        raise TypeError("Invalid counter origin")
    return CounterAdd(receiver, arguments[0])


def _value(origin: Construct, receiver: Reference) -> CounterValue:
    if not isinstance(origin, CounterOpen):
        raise TypeError("Invalid counter origin")
    return CounterValue(receiver)


def _close(
    origin: Construct, receiver: Reference, arguments: tuple[Value, ...]
) -> CounterClose:
    if not isinstance(origin, CounterOpen) or arguments:
        raise TypeError("Invalid counter close")
    return CounterClose(receiver)


def interface_mapping_registry() -> InterfaceMappingRegistry:
    return InterfaceMappingRegistry(
        (
            InterfaceClassMapping(
                source=SOURCE,
                constructors={"open": _open},
                methods={
                    "add": InterfaceMethodMapping((ValueKind.INTEGER,), _add),
                    "close": InterfaceMethodMapping((), _close),
                },
                properties={"value": _value},
            ),
        ),
        admission_declarations=COUNTER_ADMISSIONS,
    )


@realizes(CounterOpen)
class CCounterOpen:
    supports = ("counter.open",)
    template = "long long ${name} = 0LL;"


@realizes(MappedType(SOURCE, "open"))
class CCounterType:
    type_name = "long long"


@realizes(CounterAdd)
class CCounterAdd:
    supports = ("counter.add",)
    template = "${receiver} += ${value};"


@realizes(CounterValue)
class CCounterValue:
    template = "${receiver}"


@realizes(CounterClose)
class CCounterClose:
    supports = ("counter.close",)
    template = "${receiver} = -1LL;"


class CCounterPack:
    target = "c"
    entries = (
        *C_DECLARATIONS,
        CCounterOpen,
        CCounterType,
        CCounterAdd,
        CCounterValue,
        CCounterClose,
    )
    dispatch = "composition"
    session = TextArtifactSession


@lru_cache(maxsize=1)
def c_counter_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(CCounterPack)
