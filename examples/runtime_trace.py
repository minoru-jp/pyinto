"""Public example: one restricted Python mini-language, two artifact Targets.

Run from a checkout: PYTHONPATH=src python examples/runtime_trace.py
Only trusted Python source may be used with runtime-enabled Targets.
"""

from __future__ import annotations

from pyinto import convert
from pyinto.interfaces import language as lang
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)

# The static Model preserves the loop and branch. A native Python execution
# records actual values, without making any Realizer interpret Python loops.
SOURCE = """
total: int = 0
history: list[int] = [0, 0, 0, 0, 0]

for i in range(5):
    if i % 2 == 0:
        total += i
    history[i] = total


def __pyinto_runtime__():
    return {"history": history, "total": total}
"""


def record_control(node, context) -> None:
    context.session.controls.append(type(node).__name__)


@realizes(lang.For)
class ForOutline:
    variant = "*"
    visit = record_control


@realizes(lang.Branch)
class BranchOutline:
    variant = "*"
    visit = record_control


class OutlineSession:
    def __init__(self) -> None:
        self.controls: list[str] = []

    def finish(self) -> dict[str, object]:
        return {"control": self.controls}


def trace_schema(value: object) -> bool:
    """Require a complete trace; do not interpret Python's control flow here."""
    return (
        isinstance(value, dict)
        and isinstance(value.get("total"), int)
        and isinstance(value.get("history"), list)
        and all(isinstance(item, int) for item in value["history"])
        and len(value["history"]) == 5
    )


class TraceSession(OutlineSession):
    def finish(self, runtime: object) -> dict[str, object]:
        # The Host has already applied the Target's declared schema.
        return {"control": self.controls, "runtime": runtime}


class OutlinePack:
    target = "outline"
    dispatch = "structural"
    semantics = "projection"
    unhandled = "traverse"
    runtime = "ignored"
    entries = (ForOutline, BranchOutline)
    session = OutlineSession


class TracePack:
    target = "trace"
    dispatch = "structural"
    semantics = "projection"
    unhandled = "traverse"
    runtime = "required"
    runtime_schema = trace_schema
    entries = (ForOutline, BranchOutline)
    session = TraceSession


if __name__ == "__main__":
    print(convert(SOURCE, realizations=RealizationRegistry.from_pack(OutlinePack)))
    print(convert(SOURCE, realizations=RealizationRegistry.from_pack(TracePack)))
