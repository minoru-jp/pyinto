"""Iteration 18: fail-loud audit/guard linkage and future-shape dry runs.

Audit metadata is non-normative. These checks catch drift, *not* Target
semantic equivalence. The prototypes below never become production Constructs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

from devdocs.canonical_sources.reviews.realization_boundary import (
    FIELD_ROLES,
    SEMANTIC_ADMISSION_STATUS,
    SEMANTIC_OBLIGATIONS,
)
from pyinto.admission import AdmissionDeclaration, AdmissionRule, collect_contracts
from pyinto.constructs import Construct, ConstructError, Literal, Value
from pyinto.constructs.admission import (
    ADMISSION_RULES,
    LANGUAGE_ADMISSION,
    required_contracts,
)
from pyinto.frontend import PythonFrontend
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    pack_entries,
    pack_target,
    realizes,
    supports,
    template,
    variant,
)
from tests.test_realization_boundary_audit_iteration14 import _construct_types


def _audited_guards() -> dict[str, set[str]]:
    return {
        name: {
            field
            for field, role in (part.split("=", 1) for part in roles.split())
            if role == "guard"
        }
        for name, roles in FIELD_ROLES.items()
    }


def _covered_guards() -> dict[str, set[str]]:
    covered: dict[str, set[str]] = {name: set() for name in FIELD_ROLES}
    for rule in ADMISSION_RULES:
        for cls in rule.constructs:
            assert cls.__name__ in covered, rule.name
            assert not (covered[cls.__name__] & rule.guarded_fields), rule.name
            covered[cls.__name__].update(rule.guarded_fields)
    return covered


def test_all_audited_guard_fields_have_runtime_admission_rules() -> None:
    """A new guarded field may not silently become 'callback-only'."""
    assert _audited_guards() == _covered_guards()
    for rule in ADMISSION_RULES:
        assert rule.name and rule.constructs and rule.contracts
        for cls in rule.constructs:
            assert rule.guarded_fields <= set(cls.__dataclass_fields__), rule.name


def test_explicit_obligation_status_is_complete_and_not_misrepresented() -> None:
    assert SEMANTIC_ADMISSION_STATUS.keys() == SEMANTIC_OBLIGATIONS.keys()
    names = {
        rule.name: {cls.__name__ for cls in rule.constructs} for rule in ADMISSION_RULES
    }
    for cls, obligations in SEMANTIC_OBLIGATIONS.items():
        status = SEMANTIC_ADMISSION_STATUS[cls]
        assert set(status) == set(obligations), cls
        for obligation, disposition in status.items():
            category, separator, detail = disposition.partition(":")
            assert separator and detail, (cls, obligation)
            assert category in {"admitted", "frontend", "pending"}
            if category == "admitted":
                assert cls in names[detail], (cls, obligation)
            if category == "frontend":
                assert detail == "FRT_003", (cls, obligation)
    assert SEMANTIC_ADMISSION_STATUS["Try"]["finally_on_all_exits"].startswith(
        "pending:"
    )
    assert SEMANTIC_ADMISSION_STATUS["BooleanOperation"]["short_circuit"].startswith(
        "pending:"
    )


def test_guard_inventory_matches_all_construct_classes() -> None:
    assert set(_audited_guards()) == set(_construct_types())
    # A new field in the core dataclass must first enter FIELD_ROLES (iteration14
    # test), then be assigned a rule if marked guard (test above).


def test_admission_rules_keep_direct_call_variants_and_iteration_families() -> None:
    program = PythonFrontend().parse(
        "def f(x: int, y: int = 2) -> int:\n"
        "    return x + y\n"
        "result: int = f(y=3, x=1)\n"
    )
    call = program.body.children[-1].value
    assert required_contracts(call) == {
        "call.arguments.bound",
        "call.arguments.left_to_right",
        "call.arguments.reordered",
    }
    loop = (
        PythonFrontend()
        .parse("i: int = 0\nfor i in range(3):\n    print('ok')\n")
        .body.children[-1]
    )
    assert required_contracts(loop) == {
        "iteration.source.range",
        "loop.for.break_continue",
    }


@dataclass(frozen=True)
class _NamedIntrinsic(Construct):
    receiver: Value
    operation: str
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver"})

    def parts(self) -> dict[str, object]:
        return {"receiver": self.receiver}

    def variant(self) -> str:
        return f"str.{self.operation}"


@dataclass(frozen=True)
class _AugmentedUpdate(Construct):
    receiver: Value
    operator: str
    HOLES: ClassVar[frozenset[str]] = frozenset({"receiver"})


@dataclass(frozen=True)
class _ComparisonChain(Construct):
    values: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"values"})


def test_future_prototypes_support_open_keys_without_combinatorial_variants() -> None:
    """Named ops, augmented assignment and chains use the same rule shape."""
    policies = (
        AdmissionRule(
            "intrinsic",
            (_NamedIntrinsic,),
            frozenset({"operation"}),
            frozenset({"intrinsic.operation.*"}),
            lambda node: frozenset({f"intrinsic.operation.{node.operation}"}),
        ),
        AdmissionRule(
            "augmented_update",
            (_AugmentedUpdate,),
            frozenset({"operator"}),
            frozenset({"update.target.once", "update.binding_or_mutation.explicit"}),
            lambda _node: frozenset(
                {"update.target.once", "update.binding_or_mutation.explicit"}
            ),
        ),
        AdmissionRule(
            "comparison_chain",
            (_ComparisonChain,),
            frozenset({"values"}),
            frozenset({"comparison.short_circuit", "comparison.middle.once"}),
            lambda _node: frozenset(
                {"comparison.short_circuit", "comparison.middle.once"}
            ),
        ),
    )
    upper = _NamedIntrinsic(Literal("test"), "upper")
    lower = _NamedIntrinsic(Literal("test"), "lower")
    assert collect_contracts(upper, policies) == {"intrinsic.operation.upper"}
    assert collect_contracts(lower, policies) == {"intrinsic.operation.lower"}
    assert collect_contracts(_AugmentedUpdate(Literal(1), "+="), policies) == {
        "update.target.once",
        "update.binding_or_mutation.explicit",
    }
    assert collect_contracts(
        _ComparisonChain((Literal(0), Literal(1), Literal(2))), policies
    ) == {"comparison.short_circuit", "comparison.middle.once"}

    @realizes(_NamedIntrinsic)
    class UpperOnly:
        variant @= "str.upper"
        template @= "${receiver}"
        supports @= ("intrinsic.operation.upper",)

    registry = RealizationRegistry("prototype", (UpperOnly,))
    admissions = LANGUAGE_ADMISSION.extend(
        AdmissionDeclaration(
            cls, tuple(rule for rule in policies if cls in rule.constructs)
        )
        for cls in (_NamedIntrinsic, _AugmentedUpdate, _ComparisonChain)
    )
    assert (
        registry.recipe(upper, EmitContext(registry, admission=admissions)).template
        == "${receiver}"
    )
    with pytest.raises(ConstructError, match="No 'prototype' realization"):
        registry.recipe(lower, EmitContext(registry, admission=admissions))

    @realizes(_NamedIntrinsic)
    class NoSupport:
        variant @= "str.upper"
        template @= "${receiver}"

    unprotected = RealizationRegistry("prototype", (NoSupport,))
    with pytest.raises(ConstructError, match="intrinsic.operation.upper"):
        unprotected.recipe(upper, EmitContext(unprotected, admission=admissions))

    @realizes(_AugmentedUpdate)
    class MissingUpdateContract:
        template @= "${receiver}"
        supports @= ("update.target.once",)

    reg = RealizationRegistry("prototype", (MissingUpdateContract,))
    with pytest.raises(ConstructError, match="update.binding_or_mutation.explicit"):
        reg.recipe(
            _AugmentedUpdate(Literal(1), "+="), EmitContext(reg, admission=admissions)
        )

    @realizes(_ComparisonChain)
    class ChainWithoutShortCircuit:
        template @= "${values}"
        supports @= ("comparison.middle.once",)

    reg = RealizationRegistry("prototype", (ChainWithoutShortCircuit,))
    with pytest.raises(ConstructError, match="comparison.short_circuit"):
        reg.recipe(
            _ComparisonChain((Literal(0), Literal(1))),
            EmitContext(reg, admission=admissions),
        )


def test_future_rule_must_not_emit_unregistered_contract_family() -> None:
    wrong = AdmissionRule(
        "misdeclared",
        (_NamedIntrinsic,),
        frozenset({"operation"}),
        frozenset({"intrinsic.operation.upper"}),
        lambda _node: frozenset({"intrinsic.operation.lower"}),
    )
    with pytest.raises(ValueError, match="undeclared key"):
        collect_contracts(_NamedIntrinsic(Literal("hi"), "lower"), (wrong,))


def test_extra_policies_cannot_replace_builtin_admission() -> None:
    extra = AdmissionRule(
        "intrinsic",
        (_NamedIntrinsic,),
        frozenset(),
        frozenset({"intrinsic.operation.*"}),
        lambda node: frozenset({f"intrinsic.operation.{node.operation}"}),
    )
    reused = AdmissionRule(
        "bound_arguments",
        (_NamedIntrinsic,),
        frozenset(),
        frozenset({"intrinsic.operation.*"}),
        lambda node: frozenset({f"intrinsic.operation.{node.operation}"}),
    )
    with pytest.raises(ValueError, match="Duplicate admission rule names"):
        LANGUAGE_ADMISSION.extend((AdmissionDeclaration(_NamedIntrinsic, (reused,)),))

    @realizes(_NamedIntrinsic)
    class NamedOnly:
        variant @= "str.upper"
        supports @= ("intrinsic.operation.upper",)
        template @= "${receiver}"

    admissions = LANGUAGE_ADMISSION.extend(
        (AdmissionDeclaration(_NamedIntrinsic, (extra,)),)
    )
    registry = RealizationRegistry("test", (NamedOnly,))
    assert registry.recipe(
        _NamedIntrinsic(Literal("ok"), "upper"),
        EmitContext(registry, admission=admissions),
    )
    # Adding an unrelated admission policy never disables core call rules.
    program = PythonFrontend().parse(
        "def f(x: int) -> int:\n    return x\nresult: int = f(3)\n"
    )
    call = program.body.children[-1].value

    @realizes(type(call))
    class UnprotectedCall:
        template @= "${arg0}"

    registry = RealizationRegistry("test", (UnprotectedCall,))
    with pytest.raises(ConstructError, match="call.arguments.bound"):
        registry.recipe(call, EmitContext(registry))


def test_pack_constructor_keeps_extension_admission_rules() -> None:
    extra = AdmissionRule(
        "intrinsic",
        (_NamedIntrinsic,),
        frozenset({"operation"}),
        frozenset({"intrinsic.operation.*"}),
        lambda node: frozenset({f"intrinsic.operation.{node.operation}"}),
    )

    @realizes(_NamedIntrinsic)
    class UpperWithoutSupport:
        variant @= "str.upper"
        template @= "${receiver}"

    class PrototypePack:
        pack_target @= "prototype"
        pack_entries @= (UpperWithoutSupport,)

    registry = RealizationRegistry.from_pack(PrototypePack)
    admissions = LANGUAGE_ADMISSION.extend(
        (AdmissionDeclaration(_NamedIntrinsic, (extra,)),)
    )
    with pytest.raises(ConstructError, match="intrinsic.operation.upper"):
        registry.recipe(
            _NamedIntrinsic(Literal("hi"), "upper"),
            EmitContext(registry, admission=admissions),
        )
