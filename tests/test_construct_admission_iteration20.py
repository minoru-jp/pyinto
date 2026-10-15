"""Iteration 20: domain owners provide admission rules, never Target recipes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

from pyinto import ConstructError, convert, realize
from pyinto.admission import AdmissionDeclaration, AdmissionRegistry, AdmissionRule
from pyinto.constructs import Block, Construct, Literal, Program
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.interface_mapping import InterfaceFunctionMapping, InterfaceMappingRegistry
from pyinto.realizations import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.test_realization_boundary_audit_iteration14 import _construct_types


@dataclass(frozen=True)
class _Outside(Construct):
    mode: str = "strict"
    HOLES: ClassVar[frozenset[str]] = frozenset()


OUTSIDE_RULE = AdmissionRule(
    "outside_semantics",
    (_Outside,),
    frozenset({"mode"}),
    frozenset({"outside.mode.*"}),
    lambda node: frozenset({f"outside.mode.{node.mode}"}),
)


@realizes(_Outside)
class _Unsupported:
    template = "external()"
    requires = ("danger.h",)


@realizes(_Outside)
class _Supported:
    template = "external()"
    supports = ("outside.mode.strict",)


def _provided() -> AdmissionRegistry:
    return LANGUAGE_ADMISSION.extend((AdmissionDeclaration(_Outside, (OUTSIDE_RULE,)),))


def test_language_declarations_maintained_independently_of_audit_metadata() -> None:
    assert {d.construct for d in LANGUAGE_ADMISSION.declarations} == set(
        _construct_types().values()
    )
    assert len(LANGUAGE_ADMISSION.declarations) == len(_construct_types())
    assert LANGUAGE_ADMISSION.required_contracts(Literal(3)) == frozenset()


def test_unknown_domain_construct_rejected_before_callback_or_headers() -> None:
    registry = RealizationRegistry("demo", (_Supported,))
    context = EmitContext(registry)
    with pytest.raises(ConstructError, match="Unregistered Construct admission"):
        registry.recipe(_Outside(), context)
    assert context.headers == set()

    with pytest.raises(ConstructError, match="Unregistered Construct admission"):
        realize(
            Program(Block((_Outside(),))),
            realizations=RealizationRegistry("demo", (_Supported,)),
        )


def test_contract_belongs_to_provider_and_target_cannot_silently_skip_it() -> None:
    data = _provided()
    no_support = RealizationRegistry("demo", (_Unsupported,))
    context = EmitContext(no_support, admission=data)
    with pytest.raises(ConstructError, match="outside.mode.strict"):
        no_support.recipe(_Outside(), context)
    assert context.headers == set()
    supported = RealizationRegistry("demo", (_Supported,))
    assert realize(_Outside(), realizations=supported, admission=data) == "external()\n"
    with pytest.raises(ConstructError, match="outside.mode.lenient"):
        realize(_Outside("lenient"), realizations=supported, admission=data)


def test_explicit_empty_policy_distinct_from_omitted_policy() -> None:
    declared = LANGUAGE_ADMISSION.extend((AdmissionDeclaration(_Outside),))
    assert (
        realize(
            _Outside(),
            realizations=RealizationRegistry("demo", (_Unsupported,)),
            admission=declared,
        )
        == "external()\n"
    )
    with pytest.raises(ValueError, match="Duplicate Construct admission"):
        LANGUAGE_ADMISSION.extend((AdmissionDeclaration(Literal),))
    with pytest.raises(ValueError, match="Duplicate admission rule names"):
        LANGUAGE_ADMISSION.extend(
            (
                AdmissionDeclaration(
                    _Outside,
                    (
                        AdmissionRule(
                            "bound_arguments",
                            (_Outside,),
                            frozenset(),
                            frozenset({"x"}),
                            lambda _: frozenset({"x"}),
                        ),
                    ),
                ),
            )
        )


def test_unregistered_child_is_rejected_even_if_parent_template_omits_it() -> None:
    @realizes(Program)
    class _Program:
        template = "${body}"

    @realizes(Block)
    class _Block:
        template = "ignored"

    binding = RealizationRegistry("demo", (_Program, _Block, _Supported))
    with pytest.raises(
        ConstructError, match="Unregistered Construct admission: _Outside"
    ):
        realize(Program(Block((_Outside(),))), realizations=binding)


def test_catalog_cannot_erase_builtin_admission_contracts() -> None:
    with pytest.raises(ValueError, match="Missing or replaced baseline"):
        Composer(
            RealizationRegistry("demo", (_Supported,)),
            admission=AdmissionRegistry((AdmissionDeclaration(_Outside),)),
        )

    class Derived(Literal):
        pass

    with pytest.raises(ConstructError, match="Unregistered Construct admission"):
        realize(Derived(1), realizations=RealizationRegistry("demo", ()))


def test_baseline_admission_accepts_extensions_but_rejects_replacement() -> None:
    extended = LANGUAGE_ADMISSION.extend((AdmissionDeclaration(_Outside),))
    extended.require_baseline(LANGUAGE_ADMISSION)

    missing = AdmissionRegistry((AdmissionDeclaration(_Outside),))
    with pytest.raises(ValueError, match="Missing or replaced baseline"):
        missing.require_baseline(LANGUAGE_ADMISSION)

    # Replacing a policy must fail even when every baseline type is present.
    altered = AdmissionRule(
        "literal_override",
        (Literal,),
        frozenset(),
        frozenset({"literal.override"}),
        lambda _: frozenset({"literal.override"}),
    )
    replacement = AdmissionRegistry(
        AdmissionDeclaration(decl.construct, (altered,))
        if decl.construct is Literal
        else decl
        for decl in LANGUAGE_ADMISSION.declarations
    )
    with pytest.raises(ValueError, match="Missing or replaced baseline"):
        replacement.require_baseline(LANGUAGE_ADMISSION)


def test_mapping_provider_contracts_are_independent_of_target_packs() -> None:
    definition = InterfaceFunctionMapping(
        "example.ext.operation", (), lambda args: _Outside()
    )
    catalog = (AdmissionDeclaration(_Outside, (OUTSIDE_RULE,)),)
    interface_mappings = InterfaceMappingRegistry(
        (definition,), admission_declarations=catalog
    )

    @realizes(_Outside)
    class _MappingBased:
        template = "external()"
        supports = ("outside.mode.strict",)

    bindings = RealizationRegistry("demo", (_MappingBased,))
    # Registered extension is admitted via the Interface Mapping provider, while the same
    # Target recipe alone cannot declare the Model's semantic requirements.
    with pytest.raises(ConstructError, match="Unregistered Construct admission"):
        realize(_Outside(), realizations=bindings)
    assert (
        realize(
            _Outside(), realizations=bindings, admission=interface_mappings.admission
        )
        == "external()\n"
    )


def test_convert_passes_mapping_provider_admission_through_normalization() -> None:
    from demo_device_pyinto import c_device_bindings, interface_mapping_registry

    text = convert(
        "from demo_device.device import is_ready\nif is_ready():\n    print('ok')\n",
        interface_mappings=interface_mapping_registry(),
        realizations=c_device_bindings(),
    )
    assert "device_is_ready()" in text
