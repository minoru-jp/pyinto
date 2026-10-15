"""Detailed datatypes kind elements for Target authors."""

from pyinto.model.kinds._elements import KindElement

__all__ = [
    "Array",
    "Char",
    "CodeUnit",
    "Decimal",
    "Enum",
    "Float",
    "Function",
    "Int",
    "Nil",
    "Null",
    "UInt",
    "Void",
]

Int = KindElement("Int", "detailed")
UInt = KindElement("UInt", "detailed")
Float = KindElement("Float", "detailed")
Decimal = KindElement("Decimal", "detailed")
CodeUnit = KindElement("CodeUnit", "detailed")
Array = KindElement("Array", "detailed")
Enum = KindElement("Enum", "detailed")
Function = KindElement("Function", "detailed")
Char = KindElement("Char", "detailed")
Void = KindElement("Void", "detailed")
Nil = KindElement("Nil", "detailed")
Null = KindElement("Null", "detailed")
