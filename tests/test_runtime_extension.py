"""Runtime hook contracts, execution order, and static dispatch compatibility."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from pyinto import PythonFrontend, convert, realize
from pyinto.constructs import ConstructError
from pyinto.interfaces import language as lang
from pyinto.realizations import RUNTIME_ABSENT
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)


@realizes(lang.Program)
class ProgramVisitor:
    visit = lambda node, ctx: ctx.session.events.append("visit")


@realizes(lang.Program)
class ProgramTemplate:
    template = "static"


class StructuralSession:
    def __init__(self) -> None:
        self.events: list[str] = []

    def accept_composition(self, layout: object, context: object) -> None:
        self.events.append("composition")

    def finish(self, result: object) -> tuple[list[str], object]:
        self.events.append("finish")
        return self.events, result


class StaticSession:
    def __init__(self) -> None:
        self.events: list[str] = []

    def finish(self) -> list[str]:
        self.events.append("finish")
        return self.events


def registry(
    policy: str,
    *,
    dispatch: str = "structural",
    session: type[Any] | None = None,
) -> RealizationRegistry:
    return RealizationRegistry(
        "runtime-test",
        (ProgramVisitor,) if dispatch == "structural" else (ProgramTemplate,),
        dispatch=dispatch,
        semantics="projection",
        unhandled="traverse" if dispatch == "structural" else "error",
        session_factory=session
        if session is not None
        else (
            StaticSession if policy in ("forbidden", "ignored") else StructuralSession
        ),
        runtime=policy,
    )


RUNTIME_SOURCE = """
x: int = 2

def __pyinto_runtime__() -> dict[str, int]:
    import math  # Unsupported inside the static Frontend, allowed here.
    return {"value": math.factorial(x)}
"""


def test_frontend_omits_magic_body_and_keeps_other_definitions() -> None:
    model = PythonFrontend().parse(RUNTIME_SOURCE)
    assert [type(n).__name__ for n in model.body.children] == ["Initialize"]
    assert len(model.body.children) == len(
        PythonFrontend().parse("x: int = 2").body.children
    )
    assert "__pyinto_runtime__" not in repr(model)


@pytest.mark.parametrize("dispatch", ["structural", "composition"])
def test_required_runtime_receives_result_after_dispatch(dispatch: str) -> None:
    result = convert(
        RUNTIME_SOURCE, realizations=registry("required", dispatch=dispatch)
    )
    if dispatch == "structural":
        assert result == (["visit", "finish"], {"value": 2})
    else:
        assert result == (["composition", "finish"], {"value": 2})


@pytest.mark.parametrize("policy", ["required", "forbidden", "optional", "ignored"])
@pytest.mark.parametrize("present", [False, True])
def test_all_policy_presence_combinations(policy: str, present: bool) -> None:
    source = RUNTIME_SOURCE if present else "x: int = 2"
    selected = registry(policy)
    if policy == "required" and not present:
        with pytest.raises(ValueError, match="requires __pyinto_runtime__"):
            convert(source, realizations=selected)
    elif policy == "forbidden" and present:
        with pytest.raises(ValueError, match="forbids __pyinto_runtime__"):
            convert(source, realizations=selected)
    else:
        result = convert(source, realizations=selected)
        if policy in ("required", "optional"):
            assert result[1] == ({"value": 2} if present else RUNTIME_ABSENT)
        else:
            assert result == ["visit", "finish"]


def test_optional_absence_is_distinct_from_none() -> None:
    without = convert("", realizations=registry("optional"))
    with_none = convert(
        "def __pyinto_runtime__():\n    return None", realizations=registry("optional")
    )
    assert without[1] is RUNTIME_ABSENT
    assert with_none[1] is None


def test_pack_policy_declaration_and_default() -> None:
    class RuntimePack:
        target = "structural-result"
        dispatch = "structural"
        semantics = "projection"
        unhandled = "traverse"
        entries = (ProgramVisitor,)
        session = StructuralSession
        runtime = "required"

    class LegacyPack:
        target = "legacy"
        dispatch = "structural"
        semantics = "projection"
        unhandled = "traverse"
        entries = (ProgramVisitor,)
        session = StaticSession

    assert RealizationRegistry.from_pack(RuntimePack).runtime == "required"
    assert RealizationRegistry.from_pack(LegacyPack).runtime == "ignored"
    with pytest.raises(ValueError, match="Invalid Target runtime policy"):
        registry("invalid")

    class InvalidPack:
        target = "bad"
        entries = ()
        runtime = "unknown"

    with pytest.raises(ValueError, match="Invalid Target runtime policy"):
        RealizationRegistry.from_pack(InvalidPack)


def test_runtime_pack_requires_explicit_compatible_session() -> None:
    class NoSessionPack:
        target = "bad"
        entries = (ProgramTemplate,)
        runtime = "required"

    with pytest.raises(
        ValueError, match="Runtime-enabled Target needs an artifact session"
    ):
        RealizationRegistry.from_pack(NoSessionPack)
    with pytest.raises(
        ValueError, match="Runtime-enabled Target needs an artifact session"
    ):
        RealizationRegistry("bad", (ProgramTemplate,), runtime="optional")


def test_realize_model_only_works_for_optional_but_not_required() -> None:
    model = PythonFrontend().parse(RUNTIME_SOURCE)
    assert realize(model, realizations=registry("optional"))[1] is RUNTIME_ABSENT
    with pytest.raises(ValueError, match="requires __pyinto_runtime__"):
        realize(model, realizations=registry("required"))


def test_execution_is_after_dispatch_and_happens_once(tmp_path: Path) -> None:
    marker = tmp_path / "state.txt"
    source = f"""
x: int = 1

def __pyinto_runtime__():
    from pathlib import Path
    path = Path({str(marker)!r})
    path.write_text("called", encoding="utf-8")
    return 42
"""

    @realizes(lang.Program)
    class CheckVisitor:
        def visit(node: object, ctx: object) -> None:
            assert not marker.exists()

    class ResultSession:
        def finish(self, result: object) -> object:
            assert marker.read_text(encoding="utf-8") == "called"
            return result

    selected = RealizationRegistry(
        "test",
        (CheckVisitor,),
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        session_factory=ResultSession,
        runtime="required",
    )
    assert convert(source, realizations=selected) == 42


def test_ignored_does_not_execute_trusted_source(tmp_path: Path) -> None:
    marker = tmp_path / "not_created"
    source = f"""
x: int = 1

def __pyinto_runtime__():
    from pathlib import Path
    Path({str(marker)!r}).write_text("not allowed")
"""
    assert convert(source, realizations=registry("ignored")) == ["visit", "finish"]
    assert not marker.exists()


def test_rejection_and_admission_failures_never_execute(tmp_path: Path) -> None:
    marker = tmp_path / "not_created"
    source = f"""
x: int = 1

def __pyinto_runtime__():
    from pathlib import Path
    Path({str(marker)!r}).write_text("no")
    return 0
"""
    with pytest.raises(ValueError, match="forbids"):
        convert(source, realizations=registry("forbidden"))
    with pytest.raises(ConstructError, match="No 'runtime-test' realization"):
        convert(
            source,
            realizations=RealizationRegistry(
                "runtime-test",
                (),
                dispatch="structural",
                session_factory=StructuralSession,
                runtime="required",
            ),
        )
    assert not marker.exists()


def test_runtime_exception_is_not_a_fallback() -> None:
    source = "def __pyinto_runtime__():\n    raise RuntimeError('boom')\n"
    with pytest.raises(RuntimeError, match="boom"):
        convert(source, realizations=registry("optional"))


@pytest.mark.parametrize(
    ("definition", "error"),
    [
        ("def __pyinto_runtime__(x): pass", "no arguments"),
        ("def __pyinto_runtime__(*args): pass", "no arguments"),
        ("@staticmethod\ndef __pyinto_runtime__(): pass", "no arguments"),
        ("async def __pyinto_runtime__(): pass", "synchronous"),
        ("class __pyinto_runtime__: pass", "synchronous"),
        ("__pyinto_runtime__ = 1", "synchronous"),
        ("def __pyinto_runtime__(): pass\ndef __pyinto_runtime__(): pass", "Duplicate"),
    ],
)
def test_bad_magic_definition_is_rejected(definition: str, error: str) -> None:
    with pytest.raises((ValueError, TypeError), match=error):
        PythonFrontend().parse(definition)
    with pytest.raises((ValueError, TypeError), match=error):
        convert(definition, realizations=registry("ignored"))


def test_runtime_detection_is_top_level_only() -> None:
    module = ast.parse(
        "def outer():\n    def __pyinto_runtime__():\n        return 2\n"
    )
    from pyinto.frontend.runtime import split_runtime

    _, present = split_runtime(module)
    assert not present


def test_runtime_hook_may_build_a_dataclass_without_frontend_support() -> None:
    source = """
def __pyinto_runtime__():
    from dataclasses import dataclass

    @dataclass
    class Result:
        total: int

    return Result(total=21)
"""
    _, result = convert(source, realizations=registry("required"))
    assert result.total == 21
    assert type(result).__name__ == "Result"


def test_execution_does_not_inherit_future_annotations() -> None:
    # The runtime executor itself imports future annotations, but the trusted
    # source must retain its own annotation evaluation semantics.
    #
    # The hook reads its own annotations so the check holds across versions:
    # before Python 3.14 the annotation is evaluated eagerly at definition time,
    # and from 3.14 (PEP 649/749) it is evaluated lazily on access. Either way
    # an undefined name raises NameError. If ``from __future__ import
    # annotations`` leaked into the source, the annotation would instead be the
    # string "UnknownType" and no error would be raised on any version.
    source = """
def __pyinto_runtime__() -> UnknownType:
    return __pyinto_runtime__.__annotations__["return"]
"""
    with pytest.raises(NameError, match="UnknownType"):
        convert(source, realizations=registry("required"))


# The declared schema belongs to the Target; the Host performs only its
# mechanical validation, after runtime evaluation and before finish(R).


def test_runtime_schema_type_from_pack_and_direct_registry() -> None:
    class TypedPack:
        target = "schema-type"
        dispatch = "structural"
        semantics = "projection"
        unhandled = "traverse"
        entries = (ProgramVisitor,)
        session = StructuralSession
        runtime = "required"
        runtime_schema = dict

    selected = RealizationRegistry.from_pack(TypedPack)
    assert selected.runtime_schema is dict
    assert convert(RUNTIME_SOURCE, realizations=selected)[1] == {"value": 2}
    assert convert(
        RUNTIME_SOURCE,
        realizations=RealizationRegistry(
            "schema-type-direct",
            (ProgramTemplate,),
            runtime="required",
            runtime_schema=dict,
            session_factory=StructuralSession,
        ),
    )[1] == {"value": 2}


@pytest.mark.parametrize("dispatch", ["structural", "composition"])
def test_schema_rejects_before_finish_for_both_dispatches(dispatch: str) -> None:
    class FinishMustNotRun:
        def __init__(self) -> None:
            self.events: list[str] = []

        def accept_composition(self, layout: object, context: object) -> None:
            pass

        def finish(self, result: object) -> object:
            pytest.fail("finish must not run when schema validation fails")

    selected = RealizationRegistry(
        "wrong-schema",
        (ProgramVisitor,) if dispatch == "structural" else (ProgramTemplate,),
        dispatch=dispatch,
        semantics="projection",
        unhandled="traverse" if dispatch == "structural" else "error",
        runtime="required",
        runtime_schema=list,
        session_factory=FinishMustNotRun,
    )
    from pyinto.realizations import RuntimeSchemaError

    with pytest.raises(RuntimeSchemaError, match="does not satisfy"):
        convert(RUNTIME_SOURCE, realizations=selected)


def test_schema_validator_checks_nested_values_and_preserves_identity() -> None:
    def validate_trace(value: object) -> bool:
        return (
            isinstance(value, dict)
            and isinstance(value.get("value"), int)
            and value["value"] > 0
        )

    class PredicatePack:
        target = "schema-predicate"
        dispatch = "structural"
        semantics = "projection"
        unhandled = "traverse"
        entries = (ProgramVisitor,)
        session = StructuralSession
        runtime = "required"
        runtime_schema = validate_trace

    selected = RealizationRegistry.from_pack(PredicatePack)
    assert selected.runtime_schema is validate_trace
    assert convert(RUNTIME_SOURCE, realizations=selected)[1] == {"value": 2}

    invalid = RUNTIME_SOURCE.replace("math.factorial(x)", "-5")
    from pyinto.realizations import RuntimeSchemaError

    with pytest.raises(RuntimeSchemaError, match="does not satisfy"):
        convert(invalid, realizations=selected)


@pytest.mark.parametrize("bad_result", [1, "yes", None, [], {}])
def test_schema_validator_must_return_real_bool(bad_result: object) -> None:
    from pyinto.realizations import RuntimeSchemaError

    selected = RealizationRegistry(
        "wrong-verdict",
        (ProgramVisitor,),
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        runtime="required",
        runtime_schema=lambda _value: bad_result,  # type: ignore[arg-type]
        session_factory=StructuralSession,
    )
    with pytest.raises(RuntimeSchemaError, match="must return bool"):
        convert(RUNTIME_SOURCE, realizations=selected)


def test_schema_validator_exception_preserves_cause() -> None:
    from pyinto.realizations import RuntimeSchemaError

    def broken(value: object) -> bool:
        raise LookupError("problem inside validator")

    selected = RealizationRegistry(
        "broken-predicate",
        (ProgramVisitor,),
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        runtime="required",
        runtime_schema=broken,
        session_factory=StructuralSession,
    )
    with pytest.raises(RuntimeSchemaError, match="raised an exception") as exc:
        convert(RUNTIME_SOURCE, realizations=selected)
    assert isinstance(exc.value.__cause__, LookupError)


def test_schema_checks_hook_returning_none_but_not_optional_absence() -> None:
    from pyinto.realizations import RuntimeSchemaError

    selected = RealizationRegistry(
        "none-schema",
        (ProgramVisitor,),
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        runtime="optional",
        runtime_schema=type(None),
        session_factory=StructuralSession,
    )
    assert convert("", realizations=selected)[1] is RUNTIME_ABSENT
    assert (
        realize(PythonFrontend().parse(""), realizations=selected)[1] is RUNTIME_ABSENT
    )
    assert (
        convert("def __pyinto_runtime__():\n    return None", realizations=selected)[1]
        is None
    )
    with pytest.raises(RuntimeSchemaError, match="does not satisfy"):
        convert(RUNTIME_SOURCE, realizations=selected)


@pytest.mark.parametrize("invalid", [42, "dict", list[int], dict[str, int], int | str])
def test_reject_invalid_runtime_schema_declarations(invalid: object) -> None:
    class InvalidSchemaPack:
        target = "invalid-schema"
        dispatch = "structural"
        entries = (ProgramVisitor,)
        session = StructuralSession
        runtime = "required"
        runtime_schema = invalid

    with pytest.raises(ValueError, match="Runtime schema must be a type or a callable"):
        RealizationRegistry.from_pack(InvalidSchemaPack)
    with pytest.raises(TypeError, match="Runtime schema must be a type or a callable"):
        RealizationRegistry(
            "invalid-schema",
            (ProgramVisitor,),
            dispatch="structural",
            runtime="required",
            runtime_schema=invalid,  # type: ignore[arg-type]
            session_factory=StructuralSession,
        )


@pytest.mark.parametrize("policy", ["ignored", "forbidden"])
def test_runtime_schema_rejected_for_non_consuming_policies(policy: str) -> None:
    class InvalidPolicySchemaPack:
        target = "schema-policy"
        dispatch = "structural"
        entries = (ProgramVisitor,)
        session = StructuralSession
        runtime = policy
        runtime_schema = dict

    with pytest.raises(ValueError, match="schema needs required or optional"):
        RealizationRegistry.from_pack(InvalidPolicySchemaPack)
    with pytest.raises(ValueError, match="schema needs required or optional"):
        RealizationRegistry(
            "schema-policy",
            (ProgramVisitor,),
            dispatch="structural",
            runtime=policy,
            runtime_schema=dict,
            session_factory=StructuralSession,
        )


def test_schema_default_is_unchecked_for_existing_runtime_target() -> None:
    assert registry("required").runtime_schema is None
    assert convert(RUNTIME_SOURCE, realizations=registry("required"))[1] == {"value": 2}
