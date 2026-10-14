"""SDD 19: compose nominal inheritance with existing values and control flow.

These tests inspect *static* Model contracts. They do not execute source or
pretend that class, closure, or container Target Realizations already exist.
"""

from dataclasses import FrozenInstanceError

import pytest

from pyinto.analysis import lexical_captures
from pyinto.constructs import (
    DictElement,
    FieldRead,
    FieldWrite,
    FunctionDefinition,
    FunctionValueCall,
    Initialize,
    InstanceCreation,
    ListElement,
    MethodCall,
    MethodDispatch,
    Reference,
    TupleElement,
    ValueKind,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython

BASE = """\
from typing import Callable
class Base:
    def __init__(self, n: int) -> None:
        self.n: int = n
    def get(self) -> int:
        return self.n
    def set(self, n: int) -> None:
        self.n = n
class Child(Base):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.tag: str = "child"
    def get(self) -> int:
        return super().get() + 1
"""


def parse(source: str):
    return PythonFrontend().parse(BASE + "\n" + source)


def test_cst_040_derived_value_in_base_typed_list_preserves_nominal_shape():
    nodes = parse("xs: list[Base] = [Child(1)]\nx: Base = xs[0]\n").body.children
    init = nodes[-1]
    assert isinstance(init, Initialize)
    assert isinstance(init.value, ListElement)
    assert init.value.instance_type == nodes[0].signature.identity
    assert init.symbol.instance_type == nodes[0].signature.identity
    assert nodes[-2].value.items[0].instance_type == nodes[1].signature.identity


def test_cst_040_derived_value_in_base_typed_dict_preserves_nominal_shape():
    nodes = parse(
        'data: dict[str, Base] = {"a": Child(2)}\nx: Base = data["a"]\n'
    ).body.children
    read = nodes[-1].value
    assert isinstance(read, DictElement)
    assert read.instance_type == nodes[0].signature.identity
    assert nodes[-2].value.entries[0].value.instance_type == nodes[1].signature.identity


def test_cst_040_tuples_remain_structurally_invariant():
    nodes = parse(
        "b: Base = Child(1)\nt: tuple[Base, int] = (b, 3)\nx: Base = t[0]\n"
    ).body.children
    assert isinstance(nodes[-1].value, TupleElement)
    assert nodes[-1].value.instance_type == nodes[0].signature.identity
    # CST_037 intentionally does not add general tuple covariance.
    with pytest.raises(UnsupportedPython, match="initializer"):
        parse("t: tuple[Base, int] = (Child(1), 3)\n")


@pytest.mark.parametrize(
    ("container", "access", "receiver_class"),
    [
        ("xs: list[Base] = [Child(1)]", "xs[0]", "Base"),
        ('data: dict[str, Base] = {"a": Child(1)}', 'data["a"]', "Base"),
        ("b: Base = Child(1)\nt: tuple[Base, int] = (b, 3)", "t[0]", "Base"),
    ],
)
def test_frt_032_indexed_class_value_is_valid_virtual_receiver(
    container: str, access: str, receiver_class: str
):
    nodes = parse(f"{container}\nresult: int = {access}.get()\n").body.children
    call = nodes[-1].value
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.VIRTUAL
    assert call.lookup_start is None
    assert call.owner.identity.name == receiver_class
    assert call.signature.name == "get"
    assert call.receiver.instance_type.name == receiver_class
    assert call.parts()["receiver"] is call.receiver


@pytest.mark.parametrize(
    "expression",
    [
        "make().get()",
        "Wrap(Child(2)).read().get()",
        "w.read().get()",
    ],
)
def test_frt_032_returned_instance_stays_virtual_expression_receiver(expression: str):
    source = """\
def make() -> Base:
    return Child(2)
class Wrap:
    def __init__(self, item: Base) -> None:
        self.item: Base = item
    def read(self) -> Base:
        return self.item
w: Wrap = Wrap(Child(3))
"""
    nodes = parse(source + f"result: int = {expression}\n").body.children
    call = nodes[-1].value
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.VIRTUAL
    assert call.receiver.instance_type == nodes[0].signature.identity
    assert call.signature.name == "get"


def test_frt_032_attribute_chain_preserves_field_definition_owner():
    source = """\
class Wrap:
    def __init__(self, item: Base) -> None:
        self.item: Base = item
w: Wrap = Wrap(Child(1))
x: int = w.item.get()
"""
    nodes = parse(source).body.children
    call = nodes[-1].value
    assert isinstance(call, MethodCall)
    assert isinstance(call.receiver, FieldRead)
    assert call.receiver.owner is nodes[-3].signature
    assert call.owner is nodes[0].signature


def test_frt_032_field_container_element_can_be_receiver():
    source = """\
class Basket:
    def __init__(self) -> None:
        self.items: list[Base] = [Child(2)]
b: Basket = Basket()
x: int = b.items[0].get()
"""
    nodes = parse(source).body.children
    call = nodes[-1].value
    assert isinstance(call, MethodCall)
    assert isinstance(call.receiver, ListElement)
    assert isinstance(call.receiver.source, FieldRead)
    assert call.receiver.source.owner is nodes[-3].signature


def test_frt_032_virtual_call_keeps_base_signature_not_derived_implementation():
    source = """\
def invoke(value: Base) -> int:
    return value.get()
answer: int = invoke(Child(4))
"""
    nodes = parse(source).body.children
    method = nodes[-2].body.children[0].value
    assert isinstance(method, MethodCall)
    assert method.owner == nodes[0].signature
    assert method.signature == nodes[0].signature.method("get")
    assert method.dispatch is MethodDispatch.VIRTUAL
    # Actual instance class at run time remains a Realization concern.
    assert isinstance(nodes[-1].value.arguments[0], InstanceCreation)
    assert nodes[-1].value.arguments[0].instance_type == nodes[1].signature.identity


def test_frt_033_callable_instance_field_is_indirect_call_not_method_dispatch():
    source = """\
def double(n: int) -> int:
    return n + n
class Holder:
    def __init__(self, fn: Callable[[int], int]) -> None:
        self.fn: Callable[[int], int] = fn
    def invoke(self, n: int) -> int:
        return self.fn(n)
h: Holder = Holder(double)
result: int = h.fn(5)
"""
    nodes = parse(source).body.children
    for indirect in (nodes[-3].methods[1].body.children[0].value, nodes[-1].value):
        assert isinstance(indirect, FunctionValueCall)
        assert isinstance(indirect.callee, FieldRead)
        assert indirect.callee.kind is ValueKind.FUNCTION
        assert (
            indirect.callee.callable_type.parameter_types[0].kind is ValueKind.INTEGER
        )
        assert indirect.kind is ValueKind.INTEGER
        assert list(indirect.parts()) == ["callee", "arg0"]


def test_frt_033_inherited_callable_field_keeps_lexical_field_owner():
    source = """\
def double(n: int) -> int:
    return n + n
class Parent:
    def __init__(self, fn: Callable[[int], int]) -> None:
        self.fn: Callable[[int], int] = fn
class Descendant(Parent):
    def __init__(self, fn: Callable[[int], int]) -> None:
        super().__init__(fn)
d: Descendant = Descendant(double)
value: int = d.fn(4)
"""
    nodes = parse(source).body.children
    indirect = nodes[-1].value
    assert isinstance(indirect, FunctionValueCall)
    assert isinstance(indirect.callee, FieldRead)
    assert indirect.callee.owner is nodes[-4].signature
    assert indirect.callee.receiver.instance_type == nodes[-3].signature.identity


def test_frt_033_callable_field_through_nested_instance_attribute():
    source = """\
def ident(n: int) -> int:
    return n
class Holder:
    def __init__(self, fn: Callable[[int], int]) -> None:
        self.fn: Callable[[int], int] = fn
class Wrap:
    def __init__(self, holder: Holder) -> None:
        self.holder: Holder = holder
w: Wrap = Wrap(Holder(ident))
x: int = w.holder.fn(2)
"""
    indirect = parse(source).body.children[-1].value
    assert isinstance(indirect, FunctionValueCall)
    assert isinstance(indirect.callee, FieldRead)
    assert isinstance(indirect.callee.receiver, FieldRead)


def test_frt_033_method_remains_method_even_when_other_field_is_callable():
    source = """\
def ident(n: int) -> int:
    return n
class Holder:
    def __init__(self, fn: Callable[[int], int]) -> None:
        self.fn: Callable[[int], int] = fn
    def run(self, n: int) -> int:
        return self.fn(n)
h: Holder = Holder(ident)
x: int = h.run(2)
"""
    call = parse(source).body.children[-1].value
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.VIRTUAL


def test_cst_040_alias_mutation_is_a_field_write_not_rebinding():
    source = """\
x: Base = Child(1)
y: Base = x
y.n = 5
result: int = x.get()
"""
    nodes = parse(source).body.children
    assert isinstance(nodes[-2], FieldWrite)
    assert isinstance(nodes[-2].receiver, Reference)
    assert nodes[-2].receiver.symbol is nodes[-3].symbol
    assert isinstance(nodes[-1].value, MethodCall)
    assert nodes[-1].value.receiver.symbol is nodes[-4].symbol
    assert nodes[-2].owner is nodes[0].signature


def test_cst_040_nested_function_capture_of_base_receiver():
    source = """\
def factory(item: Base) -> Callable[[], int]:
    def read() -> int:
        return item.get()
    return read
f: Callable[[], int] = factory(Child(3))
x: int = f()
"""
    nodes = parse(source).body.children
    factory = nodes[2]
    assert isinstance(factory, FunctionDefinition)
    child = factory.body.children[0]
    assert isinstance(child, FunctionDefinition)
    captures = lexical_captures(child)
    assert captures == (factory.signature.parameters[0],)
    call = child.body.children[0].value
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.VIRTUAL
    assert call.receiver.symbol is captures[0]
    assert isinstance(nodes[-1].value, FunctionValueCall)


def test_cst_040_inherited_method_access_inside_base_closure():
    source = """\
def make(b: Base) -> Callable[[], int]:
    def nested() -> int:
        return b.get()
    return nested
f: Callable[[], int] = make(Child(3))
"""
    nodes = parse(source).body.children
    child = nodes[-2].body.children[0]
    assert lexical_captures(child)[0].instance_type == nodes[0].signature.identity


def test_cst_040_class_structure_is_immutable_after_composition():
    nodes = parse("x: Base = Child(1)\nr: int = x.get()\n").body.children
    old = tuple(nodes)
    with pytest.raises(FrozenInstanceError):
        nodes[1].signature.base = None
    with pytest.raises(FrozenInstanceError):
        nodes[-1].value.dispatch = MethodDispatch.SUPER
    assert tuple(nodes) == old


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("b: Base = Child(1)\nxs: list[Child] = [b]\n", "element"),
        ("b: Base = Child(1)\nx: Child = b\n", "initializer"),
        ("b: Base = Child(1)\nr: int = b.missing()\n", "Unknown"),
        ("xs: list[int] = [1]\nr: int = xs[0].get()\n", "interface mapping"),
        (
            """\
class Holder:
    def __init__(self, n: int) -> None:
        self.n: int = n
h: Holder = Holder(1)
r: int = h.n(2)
""",
            "Unknown",
        ),
    ],
)
def test_frt_034_invalid_combinations_remain_rejected(source: str, message: str):
    with pytest.raises(UnsupportedPython, match=message):
        parse(source)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        ("h.fn()", "argument"),
        ("h.fn(1, 2)", "argument"),
        ('h.fn("bad")', "argument"),
        ("h.fn(n=2)", "positional"),
    ],
)
def test_frt_034_callable_instance_field_checks_arity_types_and_keywords(
    call: str, message: str
):
    source = (
        """\
def ident(n: int) -> int:
    return n
class Holder:
    def __init__(self, fn: Callable[[int], int]) -> None:
        self.fn: Callable[[int], int] = fn
h: Holder = Holder(ident)
"""
        + f"result: int = {call}\n"
    )
    with pytest.raises(UnsupportedPython, match=message):
        parse(source)


def test_frt_034_target_realization_is_still_explicitly_unavailable():
    from pyinto.api import realize
    from tests.support.python_realizer.pack import python_bindings

    program = parse("x: Base = Child(2)\ny: int = x.get()\n")
    with pytest.raises((ValueError, LookupError)):
        realize(program, realizations=python_bindings())
