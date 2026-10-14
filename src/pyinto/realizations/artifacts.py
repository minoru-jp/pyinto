"""Target-owned artifact sessions and an optional text-composition adapter.

The Host dispatches Model information; a session owns the resulting artifact.
The text adapter is only one possible Target choice, not the Host's output type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyinto.constructs import ConstructError
from pyinto.realizations.layout import Layout, render

if TYPE_CHECKING:
    from pyinto.realizations.registry import EmitContext


class TextArtifactSession:
    """A ready-to-use session for Targets that choose Template/Slot output.

    Final rendering belongs to this Target-selected adapter, rather than to
    the Host. Targets needing a different artifact can supply their own session.
    """

    def __init__(self) -> None:
        self._layout: Layout | None = None
        self._context: EmitContext | None = None

    def accept_composition(self, layout: Layout, context: EmitContext) -> None:
        if self._layout is not None:
            raise ConstructError("Composition already submitted to artifact session")
        self._layout = layout
        self._context = context

    def finish(self) -> str:
        if self._layout is None or self._context is None:
            raise ConstructError("Artifact session has no completed composition")
        result = render(self._layout, self._context)
        return result.rstrip("\n") + "\n"
