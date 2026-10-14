"""Public conversion entrances; Constructs are independent of Realization."""

from __future__ import annotations

from pyinto.admission import AdmissionRegistry
from pyinto.constructs import Construct
from pyinto.frontend import PythonFrontend
from pyinto.interface_mapping.registry import InterfaceMappingRegistry
from pyinto.intrinsics import IntrinsicRegistry
from pyinto.realizations.host import RealizationHost
from pyinto.realizations.registry import RealizationRegistry


def realize(
    program: Construct,
    *,
    realizations: RealizationRegistry,
    admission: AdmissionRegistry | None = None,
) -> object:
    """Realize an existing Model with an explicitly selected Target Pack.

    Construct trees are never modified. No target is selected implicitly.
    """
    if not isinstance(program, Construct):
        raise TypeError("A Construct is required")
    if not isinstance(realizations, RealizationRegistry):
        raise TypeError("A validated RealizationRegistry is required")
    if admission is not None and not isinstance(admission, AdmissionRegistry):
        raise TypeError("An AdmissionRegistry is required")
    return RealizationHost(realizations, admission=admission).run(program)


def convert(
    source: str,
    *,
    realizations: RealizationRegistry,
    interface_mappings: InterfaceMappingRegistry | None = None,
    intrinsics: IntrinsicRegistry | None = None,
    admission: AdmissionRegistry | None = None,
) -> object:
    """Normalize Python text, then request the selected Target's artifact."""
    if not isinstance(source, str):
        raise TypeError("Python source must be a string")
    if not isinstance(realizations, RealizationRegistry):
        raise TypeError("A validated RealizationRegistry is required")
    if interface_mappings is not None and not isinstance(
        interface_mappings, InterfaceMappingRegistry
    ):
        raise TypeError(
            "An InterfaceMappingRegistry is required for interface_mappings"
        )
    if intrinsics is not None and not isinstance(intrinsics, IntrinsicRegistry):
        raise TypeError("An IntrinsicRegistry is required")
    return realize(
        PythonFrontend(
            interface_mappings=interface_mappings, intrinsics=intrinsics
        ).parse(source),
        realizations=realizations,
        admission=admission
        if admission is not None
        else (interface_mappings.admission if interface_mappings is not None else None),
    )
