"""Explicit pyinto adapter for demo_device, deliberately outside pyinto core."""

from demo_device_pyinto.adapter import (
    DeviceIsReady,
    c_device_bindings,
    interface_mapping_registry,
)

__all__ = ["DeviceIsReady", "c_device_bindings", "interface_mapping_registry"]
