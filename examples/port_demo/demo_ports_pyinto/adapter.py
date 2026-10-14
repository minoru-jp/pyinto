"""External function Port implemented through a Domain Construct and a C pack."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from demo_ports.device import is_ready

from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import Value, ValueKind
from pyinto.interface_mapping import InterfaceMappingRegistry, factory, maps, signature
from pyinto.realizations import RealizationRegistry
from pyinto.realizations.regulation import (
    pack_entries,
    pack_target,
    realizes,
    requires,
    template,
)
from tests.support.c_realizer import C_DECLARATIONS


@dataclass(frozen=True)
class DeviceIsReady(Value):
    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN


@realizes(DeviceIsReady)
class CDeviceIsReady:
    requires @= "device.h"
    template @= "device_is_ready()"


class CDemoDevicePack:
    pack_target @= "c"
    pack_entries @= (*C_DECLARATIONS, CDeviceIsReady)


@lru_cache(maxsize=1)
def c_device_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(CDemoDevicePack)


@maps(is_ready)
class DeviceMappings:
    @signature()
    class IsReady:
        factory @= lambda args: DeviceIsReady()


def interface_mapping_registry() -> InterfaceMappingRegistry:
    return InterfaceMappingRegistry.from_declarations(
        (DeviceMappings,),
        admission_declarations=(AdmissionDeclaration(DeviceIsReady),),
    )
