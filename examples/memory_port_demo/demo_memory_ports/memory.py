"""Value-oriented Port for a manually released, dynamically stored cell.

This is a Python test implementation, not a model of C pointers or malloc.
The logical variant says what may be stored. The target binding owns size,
layout, allocation and representation in its own language.
"""

from __future__ import annotations


class ManualMemoryRegion:
    """A single logical integer cell with an explicit release operation.

    Note that `release()` does not run automatically on garbage collection.
    Its behavior in this Python Fake is only to invalidate this object.
    """

    def __init__(self, minimum: int, maximum: int) -> None:
        if type(minimum) is not int or type(maximum) is not int:
            raise TypeError("integer range bounds must be integers")
        if minimum > maximum:
            raise ValueError("minimum must be at most maximum")
        self.minimum = minimum
        self.maximum = maximum
        self._current: int | None = None
        self._assigned = False
        self._released = False

    @classmethod
    def integer(cls, *, minimum: int, maximum: int) -> ManualMemoryRegion:
        """Describe a logical signed/unsigned integer range, not byte size."""
        return cls(minimum, maximum)

    def assign(self, value: int) -> None:
        self._ensure_live()
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise ValueError("assigned value is outside the declared integer range")
        self._current = value
        self._assigned = True

    @property
    def value(self) -> int:
        self._ensure_live()
        if not self._assigned:
            raise RuntimeError("memory value has not been assigned")
        assert self._current is not None
        return self._current

    def release(self) -> None:
        self._ensure_live()
        self._released = True
        self._current = None
        self._assigned = False

    def _ensure_live(self) -> None:
        if self._released:
            raise RuntimeError("memory region already released")
