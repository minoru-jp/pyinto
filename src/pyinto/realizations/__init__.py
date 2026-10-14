"""Validated Target Realizations and late Template/Slot composition."""

from pyinto.realizations.artifacts import TextArtifactSession
from pyinto.realizations.host import RealizationHost
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.runtime import RUNTIME_ABSENT, RuntimeSchemaError

__all__ = [
    "RUNTIME_ABSENT",
    "Composer",
    "EmitContext",
    "RealizationHost",
    "RealizationRegistry",
    "RuntimeSchemaError",
    "TextArtifactSession",
]
