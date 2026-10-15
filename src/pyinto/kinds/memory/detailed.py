"""Detailed memory kinds: low-level references a Target may reject."""

from typing import NoReturn

from pyinto.kinds._words import GenericWord, conversion_only

__all__ = ["Pointer", "Ref"]

_MODULE = __name__


class _PointerWord(GenericWord):
    """``Pointer[T]`` plus the address/load/store operation words."""

    __slots__ = ()

    def address(self, variable: object) -> NoReturn:
        conversion_only("Pointer.address")

    def load(self, pointer: object) -> NoReturn:
        conversion_only("Pointer.load")

    def store(self, pointer: object, value: object) -> NoReturn:
        conversion_only("Pointer.store")


Pointer = _PointerWord(_MODULE, "Pointer")
Ref = GenericWord(_MODULE, "Ref")
