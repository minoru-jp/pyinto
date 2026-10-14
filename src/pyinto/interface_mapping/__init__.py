"""Explicit, target-independent mappings from Python interface mapping calls to Constructs."""

from pyinto.interface_mapping.declarations import factory, maps, signature
from pyinto.interface_mapping.registry import (
    InterfaceClassMapping,
    InterfaceFunctionMapping,
    InterfaceMappingRegistry,
    InterfaceMethodMapping,
    InterfaceParameter,
    InterfaceVariadicParameter,
)

__all__ = [
    "InterfaceClassMapping",
    "InterfaceFunctionMapping",
    "InterfaceMappingRegistry",
    "InterfaceMethodMapping",
    "InterfaceParameter",
    "InterfaceVariadicParameter",
    "factory",
    "maps",
    "signature",
]
