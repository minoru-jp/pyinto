"""Validated Target Realizations and late Template/Slot composition."""

from pyinto.realizations.artifacts import TextArtifactSession
from pyinto.realizations.host import RealizationHost
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry

__all__ = [
    "Composer",
    "EmitContext",
    "RealizationHost",
    "RealizationRegistry",
    "TextArtifactSession",
]
