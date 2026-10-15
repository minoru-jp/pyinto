"""The realization subject identifying one kind word."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KindElement:
    """``@realizes`` subject for one ``pyinto.kinds`` type word."""

    name: str
    tier: str

    @property
    def key(self) -> str:
        return f"kind:{self.name}"
