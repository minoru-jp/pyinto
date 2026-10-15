"""General datatype kinds, interpreted by every language Target.

Python's built-in types (``int``, ``float``, ``str``, ``bool``, ``None``,
collections, classes, ``Callable``) are the base general vocabulary and need no
import. These words refine them without fixing any size:

- ``Wide[X]`` / ``Narrow[X]``: larger / smaller than ``int`` or ``float``;
  nesting counts steps (``Wide[Wide[int]]``).
- ``Unsigned[X]``: an integer without sign; always the outermost word.
- ``Size`` / ``Index`` / ``Byte``: integer roles (sizes, indexes, octets).
"""

from pyinto.kinds._words import GenericWord, Word

__all__ = ["Byte", "Index", "Narrow", "Size", "Unsigned", "Wide"]

_MODULE = __name__

Wide = GenericWord(_MODULE, "Wide")
Narrow = GenericWord(_MODULE, "Narrow")
Unsigned = GenericWord(_MODULE, "Unsigned")
Size = Word(_MODULE, "Size")
Index = Word(_MODULE, "Index")
Byte = Word(_MODULE, "Byte")
