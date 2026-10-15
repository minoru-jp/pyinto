"""Detailed datatype kinds: choices close to particular languages.

A Target may reject the words it does not support. ``Void`` / ``Nil`` /
``Null`` are ``None`` on the Python side.
"""

from pyinto.kinds._words import GenericWord, Word

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

_MODULE = __name__

Int = GenericWord(_MODULE, "Int")
UInt = GenericWord(_MODULE, "UInt")
Float = GenericWord(_MODULE, "Float")
Decimal = GenericWord(_MODULE, "Decimal")
CodeUnit = GenericWord(_MODULE, "CodeUnit")
Array = GenericWord(_MODULE, "Array")
Enum = GenericWord(_MODULE, "Enum")
Function = GenericWord(_MODULE, "Function")
Char = Word(_MODULE, "Char")

Void = None
Nil = None
Null = None
