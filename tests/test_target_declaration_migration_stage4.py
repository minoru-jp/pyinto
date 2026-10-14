"""Target packs use only public Realization and Naming declarations."""

from __future__ import annotations

from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import (
    NAMING,
    REALIZES,
    ROLE_TYPES,
    entry_regulation,
    realization_target,
)
from tests.support.c_realizer.pack import C_DECLARATIONS, c_bindings
from tests.support.python_realizer.pack import PYTHON_DECLARATIONS, python_bindings


def test_declaration_kinds_are_only_realization_and_naming() -> None:
    assert set(ROLE_TYPES) == {REALIZES, NAMING}


def test_all_c_and_development_python_entries_use_public_decorators() -> None:
    for declarations in (C_DECLARATIONS, PYTHON_DECLARATIONS):
        for declaration in declarations:
            result = entry_regulation.validate(declaration)
            assert result.is_valid, (declaration.__name__, result.diagnostics)
            info = result.view.focused
            assert info.has(REALIZES) != info.has(NAMING), declaration.__name__
            if info.has(REALIZES):
                assert realization_target(info.values(REALIZES)[0]) is not None


def test_c_pack_has_unchanged_construct_call_and_type_routes() -> None:
    registry = c_bindings()
    assert isinstance(registry, RealizationRegistry)
    assert len(registry._recipes) == 17
    assert registry._calls.keys() == {"print"}
    assert registry._types == {
        "integer": "long long",
        "boolean": "_Bool",
        "string": "const char *",
    }
    assert (lang.While, "default") in registry._recipes
    assert (lang.While, "with_else") in registry._recipes
    assert (lang.For, "default") in registry._recipes
    assert (lang.For, "with_else") in registry._recipes
    assert registry._calls["print"].accepts == ("string",)
    assert registry._calls["print"].requires == ("stdio.h",)


def test_development_python_pack_retains_variants_and_direct_print() -> None:
    registry = python_bindings()
    assert isinstance(registry, RealizationRegistry)
    assert len(registry._recipes) == 24
    assert registry._calls.keys() == {"print"}
    assert not registry._types
    assert (builtin.Range, "1") in registry._recipes
    assert (builtin.Range, "2") in registry._recipes
    assert (builtin.Range, "3") in registry._recipes
    assert (lang.With, "default") in registry._recipes


def test_public_identity_of_migrated_c_role_elements() -> None:
    elements = {
        "construct": lang.While,
        "call": builtin.PrintCall,
        "type": vt.Integer,
    }
    assert realization_target(elements["construct"]) == ("construct", lang.While)
    assert realization_target(elements["call"]) == ("call", "print")
    assert realization_target(elements["type"]) == ("type", "integer")
