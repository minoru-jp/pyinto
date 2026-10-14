"""Target-independent augmented scalar updates with lvalue identity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from .base import Construct, Value
from .classes import FieldRead
from .types import ConstructError, ValueKind
from .values import Reference


class AugAssignMode(Enum):
    """Whether an augmented assignment rebinds or mutates its target."""

    REBIND = "rebind"
    IN_PLACE = "in_place"


@dataclass(frozen=True)
class AugAssign(Construct):
    """Read a scalar target once, evaluate rhs once, then rebind the target.

    The target's location (including a field receiver) is determined once,
    before evaluation of the rhs. Unlike ``Assign(target, Arithmetic(...))``,
    no second target evaluation can be introduced by the Model. Only scalar
    rebinding is admitted; collection in-place updates are a separate future
    semantic extension. Target implementation remains Realization-owned.
    """

    target: Reference | FieldRead
    operator: str
    value: Value
    mode: AugAssignMode = AugAssignMode.REBIND
    HOLES: ClassVar[frozenset[str]] = frozenset({"target", "op", "value"})

    def __post_init__(self) -> None:
        if not isinstance(self.target, (Reference, FieldRead)):
            raise ConstructError("AugAssign requires a named or field target")
        if self.mode is not AugAssignMode.REBIND:
            raise ConstructError("Only scalar rebinding is supported by AugAssign")
        if not isinstance(self.value, Value):
            raise ConstructError("AugAssign requires a Value operand")
        kind = self.target.kind
        operations = {
            ValueKind.INTEGER: frozenset(
                {"+", "-", "*", "//", "%", "&", "|", "^", "<<", ">>"}
            ),
            ValueKind.FLOAT: frozenset({"+", "-", "*", "/"}),
        }
        if self.operator not in operations.get(kind, ()) or self.value.kind is not kind:
            raise ConstructError("Unsupported scalar augmented assignment")

    def parts(self) -> Mapping[str, object]:
        return {"target": self.target, "op": self.operator, "value": self.value}
