"""Target packs use only public Realization and Naming declarations."""

from __future__ import annotations

from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import (
    ROLE_MARKERS,
    read_entry,
    realization_target,
)
from tests.support.c_realizer.pack import C_DECLARATIONS, c_bindings
from tests.support.python_realizer.pack import PYTHON_DECLARATIONS, python_bindings


def test_declaration_kinds_are_only_realization_and_naming() -> None:
    assert set(ROLE_MARKERS) == {"realizes", "naming"}


def test_all_c_and_development_python_entries_use_public_decorators() -> None:
    for declarations in (C_DECLARATIONS, PYTHON_DECLARATIONS):
        for declaration in declarations:
            info = read_entry(declaration)
            assert info.has_marker("realizes") != info.has_marker("naming"), (
                declaration.__name__
            )
            if info.has_marker("realizes"):
                assert realization_target(info.marker("realizes")) is not None


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
