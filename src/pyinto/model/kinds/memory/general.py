"""General memory kind elements for Target authors."""

from pyinto.model.kinds._elements import KindElement

__all__ = [
    "Buffer",
    "Owned",
    "Shared",
]

Owned = KindElement("Owned", "general")
Shared = KindElement("Shared", "general")
Buffer = KindElement("Buffer", "general")
