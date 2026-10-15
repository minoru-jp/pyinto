"""Detailed memory kind elements for Target authors."""

from pyinto.model.kinds._elements import KindElement

__all__ = [
    "Pointer",
    "Ref",
]

Pointer = KindElement("Pointer", "detailed")
Ref = KindElement("Ref", "detailed")
