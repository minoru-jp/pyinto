"""External function mapping implemented through a Domain Construct and a C pack."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from demo_device.device import is_ready

from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import Value, ValueKind
from pyinto.interface_mapping import InterfaceMappingRegistry, maps, signature
from pyinto.realizations import RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)
from tests.support.c_realizer import C_DECLARATIONS


@dataclass(frozen=True)
class DeviceIsReady(Value):
    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN


@realizes(DeviceIsReady)
class CDeviceIsReady:
    requires = ("device.h",)
    template = "device_is_ready()"


class CDemoDevicePack:
    target = "c"
    entries = (*C_DECLARATIONS, CDeviceIsReady)


@lru_cache(maxsize=1)
def c_device_bindings() -> RealizationRegistry:
    return RealizationRegistry.from_pack(CDemoDevicePack)


@maps(is_ready)
class DeviceMappings:
    @signature()
    class IsReady:
        factory = lambda args: DeviceIsReady()


def interface_mapping_registry() -> InterfaceMappingRegistry:
    return InterfaceMappingRegistry.from_declarations(
        (DeviceMappings,),
        admission_declarations=(AdmissionDeclaration(DeviceIsReady),),
    )
