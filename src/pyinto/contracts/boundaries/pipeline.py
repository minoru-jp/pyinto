"""Small structural interface_mappings for the first Contract experiment."""

from __future__ import annotations

from typing import Protocol


class FrontendBoundary(Protocol):
    """Build a normalized program from a Python source string."""

    def parse(self, source: str) -> object: ...


class CompositionBoundary(Protocol):
    """Realize a normalized Construct using explicit Target rules."""

    def source(self, root: object) -> str: ...
