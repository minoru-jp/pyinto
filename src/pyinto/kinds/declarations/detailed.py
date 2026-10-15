"""Detailed declaration kinds. Each decorator returns the class unchanged."""

from collections.abc import Callable
from typing import TypeVar

__all__ = ["Implements", "Interface", "MixIn"]

C = TypeVar("C", bound=type)


def Interface(cls: C) -> C:
    """Mark a class with the ``Interface`` word."""
    return cls


def MixIn(cls: C) -> C:
    """Mark a class with the ``MixIn`` word."""
    return cls


def Implements(*classes: type) -> Callable[[C], C]:
    """Mark a class with ``Implements(...)``."""

    def apply(cls: C) -> C:
        return cls

    return apply
