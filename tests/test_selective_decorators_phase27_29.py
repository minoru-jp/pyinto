"""Static/class methods and the intentionally reduced dataclass contract."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    ClassDefinition,
    ClassMethodCall,
    ClassReceiverCreation,
    ClassReference,
    FieldInitialize,
    FunctionDefinition,
    Initialize,
    InstanceCreation,
    MethodKind,
    ParameterRole,
    Reference,
    Return,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def parsed(source: str):
    return PythonFrontend().parse(source).body.children


BASIC = """
class Tools:
    def __init__(self) -> None:
        self.v: int = 1

    @staticmethod
    def add(x: int, y: int = 4) -> int:
        return x + y

    @classmethod
    def new(cls, n: int) -> Tools:
        return cls(n)
"""
# The initializer accepting one int is deliberate for factory tests.
FACTORY = """
class Box:
    def __init__(self, n: int) -> None:
        self.n: int = n

    @classmethod
    def create(klass, n: int = 5) -> "Box":
        return klass(n)

    @staticmethod
    def double(x: int) -> int:
        return x * 2
"""


def test_static_method_has_no_receiver_and_can_call_with_default() -> None:
    source = """
class Tools:
    def __init__(self) -> None:
        self.v: int = 1
    @staticmethod
    def add(x: int, y: int = 4) -> int:
        return x + y
answer: int = Tools.add(3)
"""
    cls, assignment = parsed(source)
    assert isinstance(cls, ClassDefinition)
    signature = cls.signature.method("add")
    assert signature is not None
    assert signature.method_kind is MethodKind.STATIC
    assert signature.receiver is None
    assert [param.role for param in signature.parameters] == [
        ParameterRole.ORDINARY,
        ParameterRole.ORDINARY,
    ]
    assert isinstance(assignment, Initialize)
    call = assignment.value
    assert isinstance(call, ClassMethodCall)
    assert isinstance(call.class_source, ClassReference)
    assert call.omitted_arguments == (1,)
    assert call.supplied_evaluation_arguments == (call.arguments[0],)


def test_class_method_class_receiver_and_dynamic_factory() -> None:
    cls, assignment = parsed(FACTORY + "value: Box = Box.create()\n")
    assert isinstance(cls, ClassDefinition)
    signature = cls.signature.method("create")
    assert signature is not None
    assert signature.method_kind is MethodKind.CLASS
    assert signature.receiver is None
    assert signature.class_receiver is not None
    assert signature.class_receiver.role is ParameterRole.CLASS_RECEIVER
    declaration = next(
        method for method in cls.methods if method.signature.name == "create"
    )
    assert isinstance(declaration, FunctionDefinition)
    returned = declaration.body.children[0]
    assert isinstance(returned, Return)
    assert isinstance(returned.value, ClassReceiverCreation)
    assert isinstance(returned.value.receiver, Reference)
    assert returned.value.receiver.symbol is signature.class_receiver
    assert isinstance(assignment.value, ClassMethodCall)
    assert assignment.value.omitted_arguments == (0,)


def test_class_receiver_of_inherited_method_is_runtime_derived() -> None:
    source = (
        FACTORY
        + """
class Special(Box):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.other: int = 2

value: Box = Special.create(6)
"""
    )
    base, derived, assignment = parsed(source)
    assert isinstance(base, ClassDefinition)
    assert isinstance(derived, ClassDefinition)
    assert isinstance(assignment, Initialize)
    call = assignment.value
    assert isinstance(call, ClassMethodCall)
    assert isinstance(call.class_source, ClassReference)
    assert call.class_source.signature.identity.name == "Special"
    assert call.signature.scope == ("Box",)
    assert call.owner.identity.name == "Special"


def test_static_method_inherited() -> None:
    source = (
        FACTORY
        + """
class Special(Box):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.other: int = 1
x: int = Special.double(4)
"""
    )
    _, _, init = parsed(source)
    assert isinstance(init.value, ClassMethodCall)
    assert init.value.signature.method_kind is MethodKind.STATIC


def test_dataclass_synthesizes_existing_field_initializer_contract() -> None:
    source = """
from dataclasses import dataclass
@dataclass
class Point:
    x: int
    y: float = 2.5

p: Point = Point(3)
q: Point = Point(y=5.0, x=1)
"""
    cls, p, q = parsed(source)
    assert isinstance(cls, ClassDefinition)
    assert [f.name for f in cls.signature.fields] == ["x", "y"]
    assert [x.name for x in cls.signature.methods] == ["__init__"]
    assert isinstance(cls.methods[0].body.children[0], FieldInitialize)
    assert isinstance(cls.methods[0].body.children[1], FieldInitialize)
    assert isinstance(p, Initialize) and isinstance(p.value, InstanceCreation)
    assert p.value.omitted_arguments == (1,)
    assert isinstance(q, Initialize) and isinstance(q.value, InstanceCreation)
    assert q.value.argument_evaluation_order == (1, 0)


def test_dataclass_method_and_import_alias() -> None:
    source = """
from dataclasses import dataclass as data
@data
class Point:
    x: int
    def get(self) -> int:
        return self.x
p: Point = Point(2)
answer: int = p.get()
"""
    cls, *_ = parsed(source)
    assert isinstance(cls, ClassDefinition)
    assert {m.signature.name for m in cls.methods} == {"__init__", "get"}


def test_empty_dataclass_allowed() -> None:
    cls, assignment = parsed(
        "from dataclasses import dataclass\n@dataclass\nclass Marker:\n    pass\nitem: Marker = Marker()"
    )
    assert isinstance(cls, ClassDefinition)
    assert isinstance(assignment.value, InstanceCreation)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n    @unknown\n    def foo(self) -> None:\n        return",
            "method decorator",
        ),
        (
            "class A:\n    @staticmethod\n    def __init__(self) -> None:\n        return",
            "simple typed",
        ),
        (
            "class A:\n    @classmethod\n    def __init__(cls) -> None:\n        return",
            "simple typed",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n    @staticmethod\n    def foo(self) -> None:\n        return",
            "annotation",
        ),
        (
            "class A:\n    def __init__(self) -> None:\n        self.x: int = 1\n    @classmethod\n    def foo(cls, n: int) -> int:\n        return n\ny: int = A.foo()",
            "argument",
        ),
        (
            "from dataclasses import dataclass\n@dataclass\nclass A:\n    x: list[int] = []",
            "scalar literal",
        ),
        (
            "from dataclasses import dataclass\n@dataclass\nclass A:\n    x: int = 1\n    y: int",
            "Required data class field",
        ),
        (
            "from dataclasses import dataclass\n@dataclass\nclass A:\n    x: int\n    def __init__(self, x: int) -> None:\n        self.x: int = x",
            "cannot define __init__",
        ),
        ("@dataclass\nclass A:\n    x: int", "decorator"),
        (
            "from dataclasses import dataclass\n@dataclass(order=True)\nclass A:\n    x: int",
            "decorator",
        ),
        (
            "from dataclasses import dataclass\n@dataclass\nclass A:\n    x: int\n    y = 3",
            "typed field",
        ),
    ],
)
def test_restricted_forms_rejected(source: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        parsed(source)


def test_classmethod_can_delegate_to_another_classmethod() -> None:
    source = """
class Box:
    def __init__(self, n: int) -> None:
        self.n: int = n
    @classmethod
    def fresh(klass) -> "Box":
        return klass.create(7)
    @classmethod
    def create(klass, n: int) -> "Box":
        return klass(n)
b: Box = Box.fresh()
"""
    cls, assignment = parsed(source)
    assert isinstance(cls, ClassDefinition)
    factory = next(m for m in cls.methods if m.signature.name == "fresh")
    result = factory.body.children[0]
    assert isinstance(result, Return)
    assert isinstance(result.value, ClassMethodCall)
    assert isinstance(result.value.class_source, Reference)
    assert result.value.class_source.symbol.role is ParameterRole.CLASS_RECEIVER
    assert isinstance(assignment.value, ClassMethodCall)


@pytest.mark.parametrize(
    "field_value",
    [
        "x: int = -3",
        "x: float = 1.25",
        "x: bool = True",
        'x: str = "hello"',
        "x: object = None",
    ],
)
def test_dataclass_scalar_defaults_are_accepted(field_value: str) -> None:
    source = f"from dataclasses import dataclass\n@dataclass\nclass D:\n    {field_value}\nd: D = D()"
    cls, assignment = parsed(source)
    assert isinstance(cls, ClassDefinition)
    assert len(cls.signature.fields) == 1
    assert isinstance(assignment.value, InstanceCreation)
    assert assignment.value.omitted_arguments == (0,)


def test_dataclass_preserves_nested_field_types() -> None:
    source = """
from dataclasses import dataclass
@dataclass
class Item:
    count: int
@dataclass
class Bundle:
    items: list[Item]
    lookup: dict[str, int]
b: Bundle = Bundle([Item(2)], {"a": 3})
"""
    item, bundle, assignment = parsed(source)
    assert isinstance(item, ClassDefinition)
    assert isinstance(bundle, ClassDefinition)
    assert isinstance(assignment.value, InstanceCreation)
    assert bundle.signature.fields[0].type.list_type is not None
    assert bundle.signature.fields[1].type.dict_type is not None


def test_class_receiver_cannot_escape_as_untyped_class_object() -> None:
    source = """
class A:
    def __init__(self) -> None:
        self.x: int = 1
    @classmethod
    def value(cls) -> object:
        return cls
"""
    with pytest.raises(UnsupportedPython, match="Class receiver can only"):
        parsed(source)


def test_static_method_can_be_called_without_constructing_instance() -> None:
    source = """
class Calculator:
    def __init__(self) -> None:
        self.value: int = 0
    @staticmethod
    def compute(n: int) -> int:
        return n + 1
result: int = Calculator.compute(3)
"""
    cls, result = parsed(source)
    assert isinstance(cls, ClassDefinition)
    assert isinstance(result, Initialize)
    assert isinstance(result.value, ClassMethodCall)
    assert result.value.signature.method_kind is MethodKind.STATIC


def test_classmethod_override_preserves_method_kind() -> None:
    source = """
class Parent:
    def __init__(self, n: int) -> None:
        self.n: int = n
    @classmethod
    def build(cls, n: int) -> "Parent":
        return cls(n)
class Derived(Parent):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.extra: int = 1
    @staticmethod
    def build(n: int) -> "Parent":
        return Parent(n)
"""
    with pytest.raises(UnsupportedPython, match="method kind"):
        parsed(source)


def test_static_method_wrong_argument_type_rejected() -> None:
    source = """
class Tool:
    def __init__(self) -> None:
        self.n: int = 1
    @staticmethod
    def calc(n: int) -> int:
        return n
value: int = Tool.calc("wrong")
"""
    with pytest.raises(
        UnsupportedPython, match="argument type|argument mismatch|type mismatch"
    ):
        parsed(source)


def test_instance_via_class_no_implicit_receiver_allowed() -> None:
    source = """
class Thing:
    def __init__(self) -> None:
        self.v: int = 1
    def get(self) -> int:
        return self.v
x: int = Thing.get()
"""
    with pytest.raises(UnsupportedPython, match="requires an instance"):
        parsed(source)


def test_dynamic_dataclass_options_not_silently_accepted() -> None:
    source = """
from dataclasses import dataclass
@dataclass(frozen=True)
class X:
    a: int
"""
    with pytest.raises(UnsupportedPython, match="decorator"):
        parsed(source)
