"""SDD phase 17: nominal, statically shaped instance classes and receiver roles."""

from dataclasses import FrozenInstanceError

import pytest

from pyinto.constructs import (
    Arithmetic,
    ClassDefinition,
    ClassSignature,
    ConstructError,
    FieldDefinition,
    FieldInitialize,
    FieldRead,
    FieldWrite,
    FunctionDefinition,
    FunctionSignature,
    Initialize,
    InstanceCreation,
    InstanceType,
    MethodCall,
    ParameterRole,
    Reference,
    Return,
    Symbol,
    TupleElement,
    ValueKind,
    ValueType,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython

COUNTER = """\
class Counter:
    def __init__(self, initial: int) -> None:
        self.value: int = initial

    def add(self, amount: int) -> None:
        self.value = self.value + amount

    def get(self) -> int:
        return self.value

counter: Counter = Counter(10)
alias: Counter = counter
alias.add(5)
result: int = counter.get()
"""


def test_cst_034_class_structure_reuses_methods_and_field_declarations() -> None:
    program = PythonFrontend().parse(COUNTER)
    clazz = program.body.children[0]
    assert isinstance(clazz, ClassDefinition)
    assert clazz.signature.identity == InstanceType("Counter")
    assert [f.name for f in clazz.signature.fields] == ["value"]
    assert tuple(m.signature for m in clazz.methods) == clazz.signature.methods
    assert all(isinstance(m, FunctionDefinition) for m in clazz.methods)
    assert tuple(clazz.parts()) == ("name", "fields", "methods")
    initializer, add, get = clazz.methods
    assert isinstance(initializer.body.children[0], FieldInitialize)
    assert isinstance(add.body.children[0], FieldWrite)
    assert isinstance(get.body.children[0], Return)
    assert isinstance(get.body.children[0].value, FieldRead)


def test_cst_035_receiver_role_is_explicit_not_based_on_name_or_only_position() -> None:
    program = PythonFrontend().parse(COUNTER)
    clazz = program.body.children[0]
    assert isinstance(clazz, ClassDefinition)
    for definition in clazz.methods:
        signature = definition.signature
        receiver = signature.receiver
        assert receiver is signature.parameters[0]
        assert receiver is not None
        assert receiver.role is ParameterRole.RECEIVER
        assert receiver.kind is ValueKind.INSTANCE
        assert receiver.instance_type == clazz.signature.identity
        assert receiver.scope == ("Counter", signature.name)
        assert all(p.role is ParameterRole.ORDINARY for p in signature.parameters[1:])
    method = clazz.methods[1]
    body = method.body.children[0]
    assert isinstance(body, FieldWrite)
    assert isinstance(body.receiver, Reference)
    assert body.receiver.symbol is method.signature.receiver
    assert isinstance(body.value, Arithmetic)
    assert isinstance(body.value.left, FieldRead)
    assert body.value.left.receiver.symbol is method.signature.receiver


def test_frt_026_class_creation_aliasing_field_read_and_method_call() -> None:
    statements = PythonFrontend().parse(COUNTER).body.children
    instance = statements[1]
    alias = statements[2]
    method_stmt = statements[3]
    result = statements[4]
    assert isinstance(instance, Initialize)
    assert isinstance(instance.value, InstanceCreation)
    assert instance.value.instance_type == InstanceType("Counter")
    assert instance.symbol.instance_type == InstanceType("Counter")
    assert isinstance(alias, Initialize)
    assert isinstance(alias.value, Reference)
    assert alias.value.symbol is instance.symbol
    assert isinstance(method_stmt.value, MethodCall)
    assert isinstance(method_stmt.value.receiver, Reference)
    assert method_stmt.value.receiver.symbol is alias.symbol
    assert method_stmt.value.signature.name == "add"
    assert tuple(method_stmt.value.parts()) == ("receiver", "method", "arg0")
    assert isinstance(result, Initialize)
    assert isinstance(result.value, MethodCall)
    assert result.value.kind is ValueKind.INTEGER


def test_frt_026_receiver_can_have_non_self_name() -> None:
    source = """\
class Box:
    def __init__(this, x: int) -> None:
        this.value: int = x
    def read(me) -> int:
        return me.value
b: Box = Box(4)
y: int = b.read()
"""
    cls = PythonFrontend().parse(source).body.children[0]
    assert isinstance(cls, ClassDefinition)
    assert cls.methods[0].signature.receiver.name == "this"
    assert cls.methods[1].signature.receiver.name == "me"
    assert cls.methods[1].signature.receiver.role is ParameterRole.RECEIVER


def test_frt_026_typing_method_instance_and_nested_collections() -> None:
    source = """\
from typing import Callable
class Cell:
    def __init__(self, n: int) -> None:
        self.n: int = n
    def get(self) -> int:
        return self.n

def ident(x: Cell) -> Cell:
    return x
c: Cell = Cell(1)
cs: list[Cell] = [c, ident(c)]
t: tuple[Cell, int] = (c, 3)
p: Cell = t[0]
d: dict[str, Cell] = {'x': c}
fn: Callable[[Cell], Cell] = ident
"""
    stmts = PythonFrontend().parse(source).body.children
    class_type = InstanceType("Cell")
    assert isinstance(stmts[1], FunctionDefinition)
    assert stmts[1].signature.parameters[0].instance_type == class_type
    assert stmts[1].signature.return_type.instance_type == class_type
    assert isinstance(stmts[5].value, TupleElement)
    assert stmts[5].value.instance_type == class_type
    assert stmts[7].symbol.callable_type.return_type.instance_type == class_type


def test_frt_026_method_can_use_other_receiver_and_return_instance() -> None:
    source = """\
class Cell:
    def __init__(self, x: int) -> None:
        self.value: int = x
    def same(self, other: Cell) -> Cell:
        return other
    def read_other(self, other: Cell) -> int:
        return other.value
x: Cell = Cell(3)
y: Cell = x.same(x)
answer: int = x.read_other(y)
"""
    stmts = PythonFrontend().parse(source).body.children
    assert isinstance(stmts[2].value, MethodCall)
    assert stmts[2].value.instance_type == InstanceType("Cell")
    assert isinstance(stmts[3].value, MethodCall)
    assert stmts[3].value.kind is ValueKind.INTEGER


def test_cst_035_nominal_classes_are_distinct_despite_identical_fields() -> None:
    same_shape = """\
class A:
    def __init__(self, v: int) -> None:
        self.value: int = v
class B:
    def __init__(self, v: int) -> None:
        self.value: int = v
"""
    with pytest.raises(UnsupportedPython, match="does not match initializer"):
        PythonFrontend().parse(same_shape + "a: A = A(1)\nb: B = a\n")
    with pytest.raises(UnsupportedPython, match="type cannot change"):
        PythonFrontend().parse(same_shape + "a: A = A(1)\nb: B = B(2)\nb = a\n")
    assert InstanceType("A") != InstanceType("B")


def test_cst_035_model_validation_rejects_invalid_instance_fields_and_receivers() -> (
    None
):
    cls = InstanceType("Something")
    with pytest.raises(ConstructError, match="nominal class"):
        ValueType(ValueKind.INSTANCE)
    with pytest.raises(ValueError, match="nominal class"):
        Symbol("x", ValueType(ValueKind.INSTANCE), "Something")
    with pytest.raises(ValueError, match="Receiver must"):
        Symbol("x", ValueType(ValueKind.INTEGER), "int", role=ParameterRole.RECEIVER)
    with pytest.raises(ConstructError, match="None type"):
        FieldDefinition("bad", ValueType(ValueKind.NONE))
    with pytest.raises(ConstructError, match="matching declared receiver"):
        ClassSignature(
            cls,
            (),
            (FunctionSignature("__init__", (), "None", ValueType(ValueKind.NONE)),),
        )


def test_cst_034_static_model_is_frozen() -> None:
    instance = PythonFrontend().parse(COUNTER).body.children[1].value
    assert isinstance(instance, InstanceCreation)
    with pytest.raises(FrozenInstanceError):
        instance.arguments = ()
    assert InstanceCreation.accepts_part_name("arg0")
    assert not InstanceCreation.accepts_part_name("arg01")
    assert MethodCall.accepts_part_name("arg5")
    assert not MethodCall.accepts_part_name("arg2x")


def test_cst_036_field_and_method_membership_is_checked_on_model_construction() -> None:
    from pyinto.constructs import Literal

    cls = PythonFrontend().parse(COUNTER).body.children[0]
    assert isinstance(cls, ClassDefinition)
    receiver = Reference(cls.methods[0].signature.receiver)
    alien = FieldDefinition("alien", ValueType(ValueKind.INTEGER))
    with pytest.raises(ConstructError, match="undeclared field"):
        FieldRead(receiver, alien, cls.signature)
    with pytest.raises(ConstructError, match="Field assignment"):
        FieldWrite(receiver, alien, cls.signature, Literal(1))
    method = cls.methods[1].signature
    unrelated = FunctionSignature(
        "unknown",
        method.parameters,
        method.return_annotation,
        method.return_type,
        scope=method.scope,
    )
    with pytest.raises(ConstructError, match="undeclared method"):
        MethodCall(receiver, unrelated, (Literal(1),), cls.signature)


def test_frt_026_class_methods_do_not_form_lexical_scopes() -> None:
    source = """\
class C:
    def __init__(self) -> None:
        return
    def f(self) -> int:
        return g()
"""
    with pytest.raises(UnsupportedPython, match="Unresolved|Unregistered"):
        PythonFrontend().parse(source)
    source = """\
def g() -> int:
    return 7
class C:
    def __init__(self) -> None:
        return
    def g(self) -> int:
        return g()
"""
    result = PythonFrontend().parse(source)
    assert isinstance(result.body.children[1], ClassDefinition)
    method = result.body.children[1].methods[1]
    from pyinto.constructs import FunctionCall

    statement = method.body.children[0]
    assert isinstance(statement, Return)
    assert isinstance(statement.value, FunctionCall)
    assert statement.value.signature is result.body.children[0].signature


def test_frt_026_initializer_fields_are_sequentially_definite() -> None:
    source = """\
class C:
    def __init__(self, value: int) -> None:
        if value > 0:
            return
        self.value: int = value
"""
    with pytest.raises(UnsupportedPython, match="start of __init__"):
        PythonFrontend().parse(source)
    source = """\
class C:
    def __init__(self, value: int) -> None:
        self.first: int = value
        self.second: int = self.first
"""
    clazz = PythonFrontend().parse(source).body.children[0]
    assert isinstance(clazz, ClassDefinition)
    assert [f.name for f in clazz.signature.fields] == ["first", "second"]


def test_frt_028_target_realization_is_not_implicitly_available() -> None:
    from pyinto import realize
    from tests.support.c_realizer import c_bindings

    model = PythonFrontend().parse(COUNTER)
    snapshot = repr(model)
    with pytest.raises(ConstructError, match="No 'c' realization for ClassDefinition"):
        realize(model, realizations=c_bindings())
    assert repr(model) == snapshot


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("class A: pass", "Class body must contain only"),
        ("class A:\n    x: int = 1", "Class body must contain only"),
        (
            "class A:\n    def hello(self) -> int:\n        return 1",
            "explicit __init__",
        ),
        ("class A(B):\n    def __init__(self) -> None:\n        pass", "Inheritance"),
        (
            "@register\nclass A:\n    def __init__(self) -> None:\n        pass",
            "Inheritance",
        ),
        (
            "class A(metaclass=type):\n    def __init__(self) -> None:\n        pass",
            "Inheritance",
        ),
        (
            "class A:\n    @staticmethod\n    def __init__(self) -> None:\n        pass",
            "simple typed parameters",
        ),
        ("class A:\n    def __init__(self: int) -> None:\n        pass", "unannotated"),
        ("class A:\n    def __init__() -> None:\n        pass", "unannotated"),
        (
            "class A:\n    def __init__(self) -> int:\n        return 1",
            "None-returning",
        ),
        (
            "class A:\n    def __new__(self) -> None:\n        pass\n    def __init__(self) -> None:\n        pass",
            "supported special method",
        ),
        (
            "class A:\n    def __init__(self, x: int = []) -> None:\n        pass",
            "scalar literal default",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x = 1",
            "Undeclared instance field",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int",
            "Instance field must be initialized",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n        self.x: int = 2",
            "Duplicate instance field",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n        self.x: str = 'x'",
            "Duplicate instance field",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = self.x",
            "Read before instance field initialization",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n    def foo(self) -> int:\n        return self.missing",
            "Undeclared instance field",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n    def x(self) -> int:\n        return 1",
            "Field conflicts with method",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 'wrong'",
            "type mismatch",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\na: A = A()\na.x = 'wrong'",
            "Field assignment type mismatch",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\na: A = A()\na.foo()",
            "Unknown or reserved instance method",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\na: A = A()\na.__init__()",
            "Unknown or reserved instance method",
        ),
        (
            "class A:\n    def __init__(self, x: int) -> None:\n        self.x: int = x\na: A = A('x')",
            "initializer argument mismatch",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n    def add(self, y: int) -> None:\n        self.x = self.x + y\na: A = A()\na.add('x')",
            "Method argument mismatch",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\na: A = A()\na.x(3)",
            "Unknown or reserved instance method",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\na: A = A()\na.new = 5",
            "Undeclared instance field",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\na: A = A()\na.x: int = 3",
            "Typed instance fields require __init__",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n        self = A()",
            "Method receiver cannot be rebound",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\na: A = A()\nf: int = A",
            "Unresolved name",
        ),
    ],
)
def test_frt_027_rejects_dynamic_or_ill_typed_class_forms(
    source: str, message: str
) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend().parse(source)
