"""Kinds vocabulary in source, spelled by a Target as concrete C types.

Run from a checkout: PYTHONPATH=src:. python examples/kinds_demo.py

The source imports words from ``pyinto.kinds``. pyinto carries them to
the Target as labels; the development C reference Realizer chooses C types for
the words it supports. What those types do at run time is the C code's own.
"""

from __future__ import annotations

from pyinto import convert
from tests.support.c_realizer.kinds import c_kind_bindings

SOURCE = """
from pyinto.kinds.datatypes.general import Byte, Narrow, Size
from pyinto.kinds.datatypes.detailed import Int, Null
from pyinto.kinds.memory.general import Memory, Owned
from pyinto.kinds.memory.detailed import Pointer

counter: Int[32] = 41
cursor: Pointer[Int[32]] = Pointer.address(counter)
Pointer.store(cursor, 42)

spare: Pointer[Int[32]] = Null
if spare == Null:
    print("no spare")

flags: Byte = 3
if Pointer.load(cursor) == 42:
    if flags == 3:
        print("stored through pointer")

boxed: Owned[Int[32]] = Memory.new(Int[32], 7)
view: Pointer[Int[32]] = Memory.borrow(boxed)
if Pointer.load(view) == 7:
    print("owned value")
Memory.release(boxed)

small: Narrow[int] = 3
count: Size = 2
if small == 3:
    if count == 2:
        print("general kinds")
"""


def main() -> None:
    print(convert(SOURCE, realizations=c_kind_bindings()), end="")


if __name__ == "__main__":
    main()
