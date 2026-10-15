"""General datatypes kind elements for Target authors."""

from pyinto.model.kinds._elements import KindElement

__all__ = [
    "Byte",
    "Index",
    "Narrow",
    "Size",
    "Unsigned",
    "Wide",
]

Wide = KindElement("Wide", "general")
Narrow = KindElement("Narrow", "general")
Unsigned = KindElement("Unsigned", "general")
Size = KindElement("Size", "general")
Index = KindElement("Index", "general")
Byte = KindElement("Byte", "general")
