"""Target-neutral Realizer dispatch and final artifact submission."""

from __future__ import annotations

from collections.abc import Iterator

from pyinto.admission import AdmissionRegistry
from pyinto.constructs import Construct, ConstructError
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.runtime import (
    RUNTIME_ABSENT,
    execute_runtime,
    validate_runtime_schema,
)


def _children(value: object) -> Iterator[Construct]:
    """Read only published Model parts; never walk arbitrary object attributes."""
    if isinstance(value, Construct):
        yield value
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _children(item)


class RealizationHost:
    """Dispatch one Model through a Target's declared mode, then request artifact.

    Sessions are instantiated once per request and are entirely Target-owned.
    Composition preserves the existing Template/Slot call chain; structural
    dispatch visits every Construct occurrence in depth-first preorder.
    Projection Targets may explicitly traverse unmatched Construct variants
    without invoking a visitor; admission inventory checks still apply.
    """

    def __init__(
        self,
        registry: RealizationRegistry,
        *,
        admission: AdmissionRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.admission = admission if admission is not None else LANGUAGE_ADMISSION
        self.admission.require_baseline(LANGUAGE_ADMISSION)

    def check_runtime(self, present: bool) -> None:
        """Validate the selected Target's purpose against the Source before dispatch.

        A conversion Target converts the Source and has no use for an
        execution hook; an inspection Target reads it without executing.
        """
        if self.registry.purpose == "conversion" and present:
            raise ValueError(
                "Conversion Target rejects __pyinto_runtime__ in the source"
            )
        if self.registry.runtime == "required" and not present:
            raise ValueError("Target requires __pyinto_runtime__ in the source")

    def run(self, root: Construct, *, runtime_source: str | None = None) -> object:
        self.check_runtime(runtime_source is not None)
        # Validate the full Model before allowing any Target factory side effects.
        self.admission.check_tree(root)
        session = self.registry.session_factory()
        finish = getattr(session, "finish", None)
        if not callable(finish):
            raise TypeError("Target artifact session must implement finish()")
        if self.registry.dispatch == "composition":
            receive = getattr(session, "accept_composition", None)
            if not callable(receive):
                raise TypeError(
                    "Composition artifact session must implement accept_composition()"
                )
            composer = Composer(
                self.registry, admission=self.admission, session=session
            )
            layout = composer.layout(root)
            # The Host submits a Layout, not a source string or final artifact.
            receive(layout, composer.context)
        else:
            context = EmitContext(
                self.registry, admission=self.admission, root=root, session=session
            )
            self._walk(root, context)
        # Only execution Targets execute the source. Optional absence is
        # signalled explicitly, so a hook returning None remains unambiguous.
        if self.registry.purpose == "execution":
            result = (
                execute_runtime(runtime_source)
                if runtime_source is not None
                else RUNTIME_ABSENT
            )
            # Runtime absence is not a value to validate. A hook returning
            # None, however, is a present value and must be checked.
            if (
                result is not RUNTIME_ABSENT
                and self.registry.runtime_schema is not None
            ):
                validate_runtime_schema(result, self.registry.runtime_schema)
            return finish(result)
        return finish()

    def _walk(self, node: Construct, ctx: EmitContext) -> None:
        previous_path = ctx.path
        ctx.path = (*previous_path, node)
        try:
            if ctx.registry.unhandled != "traverse" or ctx.registry.has_recipe(node):
                recipe = ctx.registry.recipe(node, ctx)
                recipe.visit(node, ctx)
            # Explicit projection policy: skip only the callback, not children.
            for part in node.parts().values():
                for child in _children(part):
                    if any(parent is child for parent in ctx.path):
                        raise ConstructError(
                            "Cyclic Construct parts in structural dispatch"
                        )
                    self._walk(child, ctx)
        finally:
            ctx.path = previous_path
