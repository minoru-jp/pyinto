"""General memory kinds, interpreted by every language Target.

Shape and ownership travel as type labels, so a few operation words suffice:
``Owned[X]`` / ``Shared[X]`` (ownership of a single value or a ``Buffer``),
``Buffer[T]`` (a run-time-length sequence; unowned when written bare) and the
``Memory`` operations. Each Target chooses its spelling from the labels.
"""

from typing import NoReturn

from pyinto.kinds._words import GenericWord, Word, conversion_only

__all__ = ["Buffer", "Memory", "Owned", "Shared"]

_MODULE = __name__


class _MemoryWord(Word):
    """``Memory``: dynamic-memory operation words, for conversion only."""

    __slots__ = ()

    def new(self, element_type: object, value: object) -> NoReturn:
        conversion_only("Memory.new")

    def new_buffer(
        self, element_type: object, length: object, value: object
    ) -> NoReturn:
        conversion_only("Memory.new_buffer")

    def release(self, handle: object) -> NoReturn:
        conversion_only("Memory.release")

    def resize(self, handle: object, length: object) -> NoReturn:
        conversion_only("Memory.resize")

    def length(self, handle: object) -> NoReturn:
        conversion_only("Memory.length")

    def borrow(self, handle: object) -> NoReturn:
        conversion_only("Memory.borrow")

    def copy(self, destination: object, source: object) -> NoReturn:
        conversion_only("Memory.copy")

    def fill(self, handle: object, value: object) -> NoReturn:
        conversion_only("Memory.fill")


Owned = GenericWord(_MODULE, "Owned")
Shared = GenericWord(_MODULE, "Shared")
Buffer = GenericWord(_MODULE, "Buffer")
Memory = _MemoryWord(_MODULE, "Memory")
