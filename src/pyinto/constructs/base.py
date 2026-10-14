"""Target-independent base definitions for the pyinto Construct Model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from .types import (
    CallableType,
    DictType,
    InstanceType,
    ListType,
    TupleType,
    ValueKind,
    ValueType,
)


class Construct:
    """One normalized operation or structure and its named child positions."""

    # Historical name: these are *possible Model part names*, not mandatory
    # output holes. Keep the declaration compatible with external Constructs.
    HOLES: ClassVar[frozenset[str]] = frozenset()
    # A finite variant domain, or None for externally extensible domains.
    # Any subclass overriding variant() must declare its domain explicitly;
    # absent such a declaration, validation conservatively treats it as open.
    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"default"})

    @classmethod
    def variant_domain(cls) -> frozenset[str] | None:
        """Return known valid variant names, or None for an open domain."""
        if "variant" in cls.__dict__ and "VARIANTS" not in cls.__dict__:
            return None
        return cls.VARIANTS

    @classmethod
    def accepts_part_name(cls, name: str) -> bool:
        """Whether a name can denote one of this Construct's structural parts.

        Static Template validation checks possible names here. Actual presence
        is determined only from the particular instance's ``parts()``.
        """
        return name in cls.HOLES

    def parts(self) -> Mapping[str, object]:
        return {}

    def variant(self) -> str:
        return "default"


class Value(Construct):
    """A target-independent expression with a single structural value type.

    Scalar Values can supply just ``kind``; structural Values override
    ``value_type`` once. The shape accessors are derived projections rather
    than independent sources of type information.
    """

    @property
    def kind(self) -> ValueKind:
        return self.value_type.kind

    @property
    def value_type(self) -> ValueType:
        # Only scalar expressions that explicitly supply a ``kind`` use this
        # fallback. A new structural Value must define ``value_type``.
        if type(self).kind is Value.kind:
            raise NotImplementedError("Value subclass must define its value type")
        return ValueType(self.kind)

    @property
    def callable_type(self) -> CallableType | None:
        return (
            None
            if self.kind is ValueKind.PORT_OBJECT
            else self.value_type.callable_type
        )

    @property
    def tuple_type(self) -> TupleType | None:
        return (
            None if self.kind is ValueKind.PORT_OBJECT else self.value_type.tuple_type
        )

    @property
    def list_type(self) -> ListType | None:
        return None if self.kind is ValueKind.PORT_OBJECT else self.value_type.list_type

    @property
    def dict_type(self) -> DictType | None:
        return None if self.kind is ValueKind.PORT_OBJECT else self.value_type.dict_type

    @property
    def instance_type(self) -> InstanceType | None:
        return (
            None
            if self.kind is ValueKind.PORT_OBJECT
            else self.value_type.instance_type
        )
