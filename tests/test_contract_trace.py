"""Contrace declarations must be implemented and exercised by these tests."""

from shikumi_contrace.checking import check
from shikumi_contrace.reading import untested_clauses

from pyinto.contracts.class_mapping_contract import ClassMappingContract
from pyinto.contracts.construct_contract import ConstructContract, FrontendContract
from pyinto.contracts.function_mapping_contract import FunctionMappingContract
from tests import (
    test_class_mapping,
    test_construct_pipeline,
    test_language_bindings,
    test_loop_and_context,
    test_mapping_integration,
)


def test_all_clauses_have_tests() -> None:
    within = (
        test_construct_pipeline,
        test_class_mapping,
        test_language_bindings,
        test_loop_and_context,
        test_mapping_integration,
    )
    for contract in (
        ConstructContract,
        FrontendContract,
        ClassMappingContract,
        FunctionMappingContract,
    ):
        missing = untested_clauses(contract, within=within)
        assert not missing, [clause.path for clause in missing]


def test_contract_structure_valid() -> None:
    findings = check(
        contract_assets=["pyinto.contracts"],
        tests=["tests"],
        implementations=[
            "pyinto.frontend.parser",
            "pyinto.frontend.context",
            "pyinto.frontend.statements",
            "pyinto.frontend.expressions",
            "pyinto.frontend.functions",
            "pyinto.frontend.classes",
            "pyinto.frontend.interface_mapping",
            "pyinto.frontend.annotations",
            "pyinto.frontend.decorators",
            "pyinto.frontend.decorator_effects",
            "pyinto.admission",
            "pyinto.constructs.admission",
            "pyinto.constructs.types",
            "pyinto.constructs.base",
            "pyinto.constructs.type_rules",
            "pyinto.constructs.values",
            "pyinto.constructs.collections",
            "pyinto.constructs.control",
            "pyinto.constructs.operations",
            "pyinto.constructs.functions",
            "pyinto.constructs.classes",
            "pyinto.realizations.registry",
            "pyinto.realizations.regulation",
            "pyinto.realizations.layout",
            "tests.support.c_realizer.pack",
            "tests.support.python_realizer.pack",
            "pyinto.interface_mapping.registry",
            "demo_device_pyinto.adapter",
            "tests.support.class_mapping",
        ],
    )
    assert not findings, [finding.message for finding in findings]
