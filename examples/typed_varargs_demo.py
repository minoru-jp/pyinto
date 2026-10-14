"""Executable Python source demonstrating the bounded iteration 46 subset.

pyinto accepts these typed top-level declarations in its Source Adapter,
while a Target still needs its own function and runtime tuple Realizations.
"""


def total(first: int, *rest: int) -> int:
    value: int = first
    for item in rest:
        value += item
    return value


answer: int = total(1, 2, 3)
assert answer == 6
