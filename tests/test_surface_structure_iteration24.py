"""Iteration 24: source-level no-op and static declaration documentation."""

from __future__ import annotations

import pytest

from pyinto import constructs as model
from pyinto.frontend import PythonFrontend, UnsupportedPython


def test_pass_preserves_statement_positions_without_implicit_side_effects() -> None:
    program = PythonFrontend().parse("pass\nx: int = 1\npass\n")
    first, middle, last = program.body.children
    assert isinstance(first, model.Pass)
    assert isinstance(middle, model.Initialize)
    assert isinstance(last, model.Pass)
    assert first.parts() == {}
    assert first.variant() == "default"


def test_pass_in_control_bodies_and_functions() -> None:
    program = PythonFrontend().parse("""
def do_work() -> None:
    if True:
        pass
    else:
        pass
    while False:
        pass
    return
""")
    definition = program.body.children[0]
    assert isinstance(definition, model.FunctionDefinition)
    branch = definition.body.children[0]
    loop = definition.body.children[1]
    assert isinstance(branch, model.Branch)
    assert isinstance(branch.then_body.children[0], model.Pass)
    assert branch.else_body is not None
    assert isinstance(branch.else_body.children[0], model.Pass)
    assert isinstance(loop, model.While)
    assert isinstance(loop.body.children[0], model.Pass)


def test_module_and_function_docstrings_are_static_metadata() -> None:
    program = PythonFrontend().parse('''"""Module  docs.\n  Exact spacing."""
def f() -> None:
    """Function docs."""
    pass
''')
    assert program.docstring == "Module  docs.\n  Exact spacing."
    assert len(program.body.children) == 1
    function = program.body.children[0]
    assert isinstance(function, model.FunctionDefinition)
    assert function.docstring == "Function docs."
    assert isinstance(function.body.children[0], model.Pass)
    assert "docstring" not in program.parts()
    assert "docstring" not in function.parts()


def test_empty_docstring_is_preserved_not_treated_as_absence() -> None:
    program = PythonFrontend().parse('""""""\npass')
    assert program.docstring == ""
    assert program.body.children == (model.Pass(),)


def test_class_and_constructor_docstrings_preserve_field_invariants() -> None:
    program = PythonFrontend().parse('''
class Box:
    """A typed box."""
    def __init__(self) -> None:
        """Create it."""
        self.size: int = 3
''')
    cls = program.body.children[0]
    assert isinstance(cls, model.ClassDefinition)
    assert cls.docstring == "A typed box."
    assert cls.methods[0].docstring == "Create it."
    assert len(cls.signature.fields) == 1
    assert isinstance(cls.methods[0].body.children[0], model.FieldInitialize)


def test_dataclass_docstring_does_not_become_a_field() -> None:
    program = PythonFrontend().parse('''
from dataclasses import dataclass
@dataclass
class Point:
    """Point documentation."""
    x: int
    y: int = 0
''')
    cls = program.body.children[0]
    assert isinstance(cls, model.ClassDefinition)
    assert cls.docstring == "Point documentation."
    assert [f.name for f in cls.signature.fields] == ["x", "y"]


def test_nonleading_str_expression_remains_unsupported() -> None:
    with pytest.raises(UnsupportedPython, match="Unsupported statement"):
        PythonFrontend().parse('pass\n"""Not a docstring"""\n')
    with pytest.raises(UnsupportedPython, match="Unsupported statement"):
        PythonFrontend().parse("""
def f() -> None:
    pass
    "not a docstring"
""")


def test_model_docstring_is_validated_without_becoming_output_policy() -> None:
    with pytest.raises(model.ConstructError, match="docstring"):
        model.Program(model.Block(()), 123)  # type: ignore[arg-type]
    with pytest.raises(model.ConstructError, match="docstring"):
        signature = model.FunctionSignature(
            "f", (), "None", model.ValueType(model.ValueKind.NONE)
        )
        model.FunctionDefinition(signature, model.Block(()), object())  # type: ignore[arg-type]


def test_existing_program_has_no_implicit_docstring() -> None:
    assert PythonFrontend().parse("x: int = 1").docstring is None
    assert PythonFrontend().parse("pass").body.children == (model.Pass(),)


def test_docstring_only_function_has_empty_executable_block() -> None:
    function = (
        PythonFrontend()
        .parse('def f() -> None:\n    """Only documentation"""\n')
        .body.children[0]
    )
    assert isinstance(function, model.FunctionDefinition)
    assert function.docstring == "Only documentation"
    assert function.body.children == ()


def test_docstring_metadata_does_not_change_admission_of_pass() -> None:
    from pyinto.constructs.admission import LANGUAGE_ADMISSION

    statement = model.Pass()
    assert LANGUAGE_ADMISSION.required_contracts(statement) == frozenset()
    assert isinstance(PythonFrontend().parse('"""doc"""\npass'), model.Program)


def test_class_docstring_type_is_checked_independently_of_methods() -> None:
    cls = (
        PythonFrontend()
        .parse("class A:\n    def __init__(self) -> None:\n        pass\n")
        .body.children[0]
    )
    assert isinstance(cls, model.ClassDefinition)
    with pytest.raises(model.ConstructError, match="docstring"):
        model.ClassDefinition(cls.signature, cls.methods, 42)  # type: ignore[arg-type]
