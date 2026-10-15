"""Plain class-attribute declarations: read only what the class body states."""

from __future__ import annotations

from typing import ClassVar

import pytest

from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations.registry import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import (
    ENTRY_FIELDS,
    PACK_FIELDS,
    naming,
    read_entry,
    read_pack,
    realizes,
)


@realizes(lang.Block)
class Block:
    template = "${children}"


@realizes(lang.Program)
class Program:
    template = "${requirements}${body}"


def test_plain_entry_and_pack_register() -> None:
    class Pack:
        target = "plain"
        entries = (Block, Program)
        session = TextArtifactSession

    registry = RealizationRegistry.from_pack(Pack)
    assert registry.target == "plain"


def test_declaration_names_are_the_documented_sets() -> None:
    assert set(ENTRY_FIELDS) == {
        "variant",
        "template",
        "render",
        "visit",
        "type_name",
        "accepts",
        "supports",
        "requires",
        "separators",
        "reserved",
        "forbidden_prefixes",
        "requirement_line",
    }
    assert set(PACK_FIELDS) == {
        "target",
        "entries",
        "dispatch",
        "session",
        "semantics",
        "unhandled",
        "runtime",
        "runtime_schema",
    }


def test_misspelled_entry_name_is_rejected() -> None:
    @realizes(lang.While)
    class Misspelled:
        tempalte = "while (${condition}) { ${body} }"

    with pytest.raises(ValueError, match="unknown declaration 'tempalte'"):
        read_entry(Misspelled)


def test_misspelled_pack_name_is_rejected() -> None:
    class Pack:
        target = "plain"
        entries = (Block,)
        dispach = "structural"

    with pytest.raises(
        ValueError, match="Invalid Target Pack Pack: unknown declaration"
    ):
        RealizationRegistry.from_pack(Pack)


def test_retired_pack_prefix_is_reported_as_unknown() -> None:
    class Pack:
        pack_target = "plain"
        entries = (Block,)

    with pytest.raises(ValueError, match="unknown declaration 'pack_target'"):
        read_pack(Pack)


def test_private_helpers_and_dunders_are_ignored() -> None:
    @realizes(lang.Block)
    class WithHelper:
        """Docstrings and private helpers are ordinary Python details."""

        _joiner = "\n"
        template = "${children}"

        @staticmethod
        def _helper() -> str:
            return "unused"

    entry = read_entry(WithHelper)
    assert dict(entry.values) == {"template": "${children}"}


def test_functions_can_be_defined_in_the_body() -> None:
    @realizes(lang.Block)
    class Rendered:
        def render(node: object, context: object) -> str:
            return "${children}"

    entry = read_entry(Rendered)
    assert callable(entry.value("render"))


def test_classvar_annotation_is_accepted() -> None:
    @realizes(lang.FunctionDefinition)
    class Function:
        separators: ClassVar[dict[str, str]] = {"parameters": ", "}
        template = "${return_type} ${name}(${parameters}) {${body}}"

    assert read_entry(Function).value("separators") == {"parameters": ", "}


def test_value_types_are_checked() -> None:
    @realizes(lang.While)
    class WrongType:
        template = 3

    with pytest.raises(ValueError, match="template must be str, got int"):
        read_entry(WrongType)


def test_requires_needs_a_tuple_of_strings() -> None:
    @realizes(builtin.PrintCall)
    class BareString:
        accepts = ("string",)
        requires = "stdio.h"
        template = "puts(${arg0});"

    with pytest.raises(ValueError, match="requires must be a tuple of str"):
        read_entry(BareString)

    @realizes(builtin.PrintCall)
    class Several:
        accepts = ("string",)
        requires = ("stdio.h", "stdlib.h")
        template = "puts(${arg0});"

    assert read_entry(Several).value("requires") == ("stdio.h", "stdlib.h")


def test_declarations_are_not_inherited() -> None:
    @realizes(lang.While)
    class Base:
        template = "while (${condition}) { ${body} }"

    @realizes(lang.While)
    class Derived(Base):
        variant = "default"

    with pytest.raises(ValueError, match="declarations are not inherited"):
        read_entry(Derived)


def test_plain_base_classes_remain_allowed() -> None:
    class Mixin:
        def helper(self) -> None:
            return None

    @realizes(lang.Block)
    class Entry(Mixin):
        template = "${children}"

    assert read_entry(Entry).value("template") == "${children}"


def test_role_marker_applies_once_and_only_to_classes() -> None:
    @realizes(lang.Block)
    @realizes(lang.Block)
    class Twice:
        template = "${children}"

    with pytest.raises(ValueError, match="@realizes may be applied only once"):
        read_entry(Twice)

    with pytest.raises(TypeError, match="can only decorate a class"):
        realizes(lang.Block)(lambda: None)  # type: ignore[arg-type]


def test_entry_cannot_declare_two_roles() -> None:
    @naming
    @realizes(vt.Integer)
    class Both:
        type_name = "long long"

    with pytest.raises(ValueError, match="exactly one role"):
        read_entry(Both)


def test_non_class_declaration_is_rejected() -> None:
    with pytest.raises(ValueError, match="declaration must be a class"):
        read_entry(object())


def test_nested_classes_are_rejected_outside_interface_mappings() -> None:
    @realizes(lang.Block)
    class Outer:
        template = "${children}"

        class Inner:
            pass

    with pytest.raises(ValueError, match="unknown declaration 'Inner'"):
        read_entry(Outer)
