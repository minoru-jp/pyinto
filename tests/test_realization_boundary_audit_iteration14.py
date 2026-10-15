"""Iteration 14: drift-resistant inventory, not an admission implementation."""

from __future__ import annotations

from dataclasses import dataclass, fields
from importlib import import_module
from pkgutil import iter_modules
from typing import ClassVar

import pytest

from devdocs.canonical_sources.reviews.realization_boundary import (
    FIELD_ROLES,
    SEMANTIC_OBLIGATIONS,
)
from pyinto import constructs
from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import Construct, ConstructError, Literal, Value, ValueKind
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes


def _construct_types() -> dict[str, type[Construct]]:
    result: dict[str, type[Construct]] = {}
    for item in iter_modules(constructs.__path__):
        module = import_module(f"pyinto.constructs.{item.name}")
        for name, member in vars(module).items():
            if (
                isinstance(member, type)
                and issubclass(member, Construct)
                and member not in {Construct, Value}
                and member.__module__ == module.__name__
            ):
                assert name not in result, name
                result[name] = member
    return result


def test_all_construct_dataclass_fields_have_explicit_audit_roles() -> None:
    """Adding a Construct or changing its fields requires audit reconsideration."""
    classes = _construct_types()
    assert set(FIELD_ROLES) == set(classes)
    for name, cls in classes.items():
        declared = [entry.name for entry in fields(cls)]
        pairs = [piece.split("=", 1) for piece in FIELD_ROLES[name].split()]
        assert all(len(item) == 2 for item in pairs), name
        assert all(
            role in {"part", "select", "render", "context", "guard"}
            for _, role in pairs
        ), name
        assert len({field for field, _ in pairs}) == len(pairs), name
        assert {field for field, _ in pairs} == set(declared), name


def test_priority_semantic_obligations_cover_nonfield_behaviors() -> None:
    """Field completeness alone is not sufficient to assert semantic coverage."""
    assert set(SEMANTIC_OBLIGATIONS) <= set(FIELD_ROLES)
    for name, obligations in SEMANTIC_OBLIGATIONS.items():
        assert obligations and len(obligations) == len(set(obligations)), name
    assert {"dispatch", "lookup_start", "evaluation_order", "omitted_arguments"} <= {
        item.split("=")[0]
        for item in FIELD_ROLES["MethodCall"].split()
        if item.endswith("=guard")
    }
    for name in (
        "FunctionCall",
        "InstanceCreation",
        "MethodCall",
        "ClassMethodCall",
        "ClassReceiverCreation",
    ):
        assert {"evaluation_order", "omitted_arguments"} <= {
            item.split("=")[0]
            for item in FIELD_ROLES[name].split()
            if item.endswith("=guard")
        }
    assert "supported_iterable_kind" in SEMANTIC_OBLIGATIONS["IterationEntry"]
    assert "short_circuit" in SEMANTIC_OBLIGATIONS["BooleanOperation"]


@dataclass(frozen=True)
class _PrototypeNamedOperation(Construct):
    """Design spike only: a future intrinsic's *open* operation-key space."""

    receiver: Value
    operation_name: str
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver"})

    def variant(self) -> str:
        receiver_type = (
            "str"
            if self.receiver.kind is ValueKind.STRING
            else self.receiver.kind.value
        )
        return f"{receiver_type}.{self.operation_name}"

    def parts(self) -> dict[str, object]:
        return {"receiver": self.receiver}


@realizes(_PrototypeNamedOperation)
class _StringUpperPrototype:
    variant = "str.upper"
    template = "${receiver}"


def test_prototype_open_named_operation_can_be_resolved_without_enum() -> None:
    """Existing string variants can key a prototype; no intrinsic is added."""
    registry = RealizationRegistry("probe", (_StringUpperPrototype,))
    context = EmitContext(
        registry,
        admission=LANGUAGE_ADMISSION.extend(
            (AdmissionDeclaration(_PrototypeNamedOperation),)
        ),
    )
    supported = _PrototypeNamedOperation(Literal("hi"), "upper")
    assert registry.recipe(supported, context).template == "${receiver}"
    unsupported = _PrototypeNamedOperation(Literal("hi"), "lower")
    with pytest.raises(ConstructError, match="No 'probe' realization"):
        registry.recipe(unsupported, context)
