"""SDD 18: static single inheritance, super calls and virtual dispatch."""

from dataclasses import FrozenInstanceError

import pytest

from pyinto.constructs import (
    ClassDefinition,
    FieldInitialize,
    FieldRead,
    FieldWrite,
    FunctionDefinition,
    Initialize,
    InstanceCreation,
    MethodCall,
    MethodDispatch,
    Reference,
    Return,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython

INHERITANCE = """\
class Base:
    def __init__(self, x: int) -> None:
        self.value: int = x
    def get(self) -> int:
        return self.value
    def update(self, x: int) -> None:
        self.value = x

class Derived(Base):
    def __init__(self, x: int) -> None:
        super().__init__(x)
        self.other: int = 10
    def get(self) -> int:
        return super().get() + self.other
    def total(self) -> int:
        return self.get()

def read(x: Base) -> int:
    return x.get()

as_base: Base = Derived(5)
as_derived: Derived = Derived(6)
result: int = read(as_base)
other: int = as_derived.total()
as_base.update(7)
check: int = as_derived.value
"""


def parse():
    return PythonFrontend().parse(INHERITANCE)


def test_cst_037_base_chain_is_nominal_not_a_copied_class_body():
    body = parse().body.children
    base, derived = body[:2]
    assert isinstance(base, ClassDefinition)
    assert isinstance(derived, ClassDefinition)
    assert derived.signature.base is base.signature
    assert derived.signature.identity.base == base.signature.identity
    assert base.signature.identity.is_subtype_of(base.signature.identity)
    assert derived.signature.identity.is_subtype_of(base.signature.identity)
    assert not base.signature.identity.is_subtype_of(derived.signature.identity)
    assert derived.signature.fields[0].name == "other"
    assert base.signature.fields[0].name == "value"
    assert derived.signature.resolve_field("value") == (
        base.signature,
        base.signature.fields[0],
    )
    assert derived.signature.resolve_method("update") == (
        base.signature,
        base.signature.methods[2],
    )
    assert derived.signature.resolve_method("get") == (
        derived.signature,
        derived.signature.methods[1],
    )
    assert derived.signature.resolve_method("missing") is None


def test_cst_037_base_reference_preserves_runtime_instance_type():
    body = parse().body.children
    init = body[3]
    assert isinstance(init, Initialize)
    assert isinstance(init.value, InstanceCreation)
    assert init.symbol.instance_type == body[0].signature.identity
    assert init.value.instance_type == body[1].signature.identity


def test_cst_038_super_has_static_lookup_base_but_same_receiver():
    derived = parse().body.children[1]
    assert isinstance(derived, ClassDefinition)
    init, get, total = derived.methods
    assert isinstance(init, FunctionDefinition)
    call = init.body.children[0].value
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.SUPER
    assert call.lookup_start is derived.signature.base
    assert call.owner is derived.signature
    assert call.signature is derived.signature.base.method("__init__")
    assert isinstance(call.receiver, Reference)
    assert call.receiver.symbol is init.signature.receiver
    assert call.receiver.instance_type == derived.signature.identity
    assert isinstance(init.body.children[1], FieldInitialize)
    value = get.body.children[0]
    assert isinstance(value, Return)
    method_call = value.value.left
    assert isinstance(method_call, MethodCall)
    assert method_call.dispatch is MethodDispatch.SUPER
    assert method_call.lookup_start is derived.signature.base
    assert method_call.receiver.symbol is get.signature.receiver
    virtual = total.body.children[0].value
    assert isinstance(virtual, MethodCall)
    assert virtual.dispatch is MethodDispatch.VIRTUAL
    assert virtual.lookup_start is None


def test_cst_039_base_typed_receiver_preserves_virtual_dispatch():
    body = parse().body.children
    function = body[2]
    call = function.body.children[0].value
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.VIRTUAL
    assert call.owner is body[0].signature
    assert call.signature is body[0].signature.method("get")
    assert call.receiver.instance_type == body[0].signature.identity
    assert call.lookup_start is None
    assert isinstance(body[6].value, MethodCall)
    assert body[6].value.dispatch is MethodDispatch.VIRTUAL


def test_cst_039_inherited_members_preserve_definition_owner():
    body = parse().body.children
    inherited_call = body[7].value
    inherited_read = body[8].value
    assert isinstance(inherited_call, MethodCall)
    assert inherited_call.owner == body[0].signature  # static receiver type
    assert inherited_call.signature == body[0].signature.method("update")
    assert inherited_call.signature == body[0].signature.method("update")
    assert isinstance(inherited_read, FieldRead)
    assert inherited_read.owner is body[0].signature
    assert inherited_read.receiver.instance_type == body[1].signature.identity


def test_cst_039_field_mutation_on_inherited_slot():
    source = INHERITANCE + "as_derived.value = 12\n"
    result = PythonFrontend().parse(source).body.children[-1]
    assert isinstance(result, FieldWrite)
    assert result.owner.identity.name == "Base"
    assert result.receiver.instance_type.name == "Derived"


def test_cst_037_three_levels_have_no_depth_special_case():
    source = (
        INHERITANCE
        + """\
class Leaf(Derived):
    def __init__(self, x: int) -> None:
        super().__init__(x)
        self.z: int = 1
    def total(self) -> int:
        return super().total() + self.z
leaf: Base = Leaf(2)
"""
    )
    statements = PythonFrontend().parse(source).body.children
    leaf = statements[-2]
    assert isinstance(leaf, ClassDefinition)
    assert leaf.signature.identity.is_subtype_of(statements[0].signature.identity)
    assert leaf.signature.resolve_field("value")[0] == statements[0].signature
    super_call = leaf.methods[-1].body.children[0].value.left
    assert super_call.dispatch is MethodDispatch.SUPER
    assert super_call.lookup_start.identity.name == "Derived"
    assert statements[-1].value.instance_type.name == "Leaf"


def test_cst_037_nominal_compatibility_is_one_way():
    source = INHERITANCE + "wrong: Derived = as_base\n"
    with pytest.raises(UnsupportedPython, match="initializer"):
        PythonFrontend().parse(source)
    source = INHERITANCE + "as_derived = as_base\n"
    with pytest.raises(UnsupportedPython, match="type cannot change"):
        PythonFrontend().parse(source)


@pytest.mark.parametrize(
    "invalid",
    [
        "class Unknown(Missing):\n    def __init__(self) -> None:\n        pass\n",
        "class Broken(Base, Derived):\n    def __init__(self) -> None:\n        pass\n",
        "class Illegal(Base()):\n    def __init__(self) -> None:\n        pass\n",
        "class Cycle(Cycle):\n    def __init__(self) -> None:\n        pass\n",
        "@decorator\nclass Decorated(Base):\n    def __init__(self) -> None:\n        pass\n",
        "class Meta(Base, metaclass=type):\n    def __init__(self) -> None:\n        pass\n",
    ],
)
def test_frt_029_rejects_unbounded_dynamic_inheritance(invalid):
    with pytest.raises(UnsupportedPython):
        PythonFrontend().parse(INHERITANCE + invalid)


@pytest.mark.parametrize(
    "method",
    [
        """def get(self, x: int) -> int:
        return x""",
        '''def get(self) -> str:
        return "wrong"''',
    ],
)
def test_frt_030_rejects_incompatible_override(method):
    source = """\
class B:
    def __init__(self) -> None:
        self.v: int = 1
    def get(self) -> int:
        return self.v
class D(B):
    def __init__(self) -> None:
        super().__init__()
""" + "\n".join("    " + line for line in method.splitlines())
    with pytest.raises(UnsupportedPython, match="Override"):
        PythonFrontend().parse(source)


@pytest.mark.parametrize(
    "method",
    [
        """def __init__(self) -> None:
        self.x: int = 1""",
        """def __init__(self) -> None:
        self.x: int = 1
        super().__init__()""",
    ],
)
def test_frt_030_requires_base_initialization_first(method):
    source = """\
class B:
    def __init__(self) -> None:
        self.v: int = 1
class D(B):
""" + "\n".join("    " + line for line in method.splitlines())
    with pytest.raises(UnsupportedPython, match="start with super"):
        PythonFrontend().parse(source)


def test_frt_030_super_rejected_in_base_method():
    with pytest.raises(UnsupportedPython, match="super"):
        PythonFrontend().parse("""\
class B:
    def __init__(self) -> None:
        self.x: int = 1
    def get(self) -> int:
        return super().get()
""")


def test_frt_030_super_must_have_no_arguments():
    with pytest.raises(UnsupportedPython, match="super"):
        PythonFrontend().parse(
            INHERITANCE.replace("super().get()", "super(Derived, self).get()")
        )


def test_frt_030_super_cannot_call_unknown_method():
    with pytest.raises(UnsupportedPython, match="Unknown"):
        PythonFrontend().parse(
            INHERITANCE.replace("super().get()", "super().nothing()")
        )


def test_frt_030_unrelated_class_still_rejected():
    with pytest.raises(UnsupportedPython, match="initializer"):
        PythonFrontend().parse(
            INHERITANCE
            + """\
class Else:
    def __init__(self, v: int) -> None:
        self.x: int = v
bad: Else = Derived(1)
"""
        )


def test_cst_039_static_and_super_calls_do_not_mutate_source():
    program = parse()
    old = program.body.children
    assert tuple(program.body.children) == old
    with pytest.raises(FrozenInstanceError):
        program.body.children[1].signature.identity.base = None


def test_cst_039_target_realization_is_not_claimed():
    from pyinto.api import realize
    from tests.support.c_realizer import c_bindings

    program = parse()
    with pytest.raises((ValueError, LookupError)):
        realize(program, realizations=c_bindings())


def test_frt_030_super_initializer_cannot_repeat():
    source = INHERITANCE.replace(
        "self.other: int = 10",
        "self.other: int = 10\n        super().__init__(x)",
    )
    with pytest.raises(UnsupportedPython, match="exactly once"):
        PythonFrontend().parse(source)


def test_frt_030_virtual_dispatch_remains_virtual_on_explicit_derived():
    statements = parse().body.children
    call = statements[6].value  # as_derived.total()
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.VIRTUAL
    assert call.owner is statements[1].signature
    assert call.signature is statements[1].signature.method("total")


def test_cst_037_ordinary_class_does_not_gain_base():
    cls = (
        PythonFrontend()
        .parse("""\
class A:
    def __init__(self) -> None:
        self.x: int = 1
""")
        .body.children[0]
    )
    assert cls.signature.base is None
    assert cls.signature.identity.base is None


def test_frt_031_derived_return_can_upcast_to_base():
    program = PythonFrontend().parse(
        INHERITANCE
        + """\
def provide() -> Base:
    return Derived(9)
returned: Base = provide()
"""
    )
    provide = program.body.children[-2]
    result = provide.body.children[0].value
    assert isinstance(result, InstanceCreation)
    assert result.instance_type.name == "Derived"
    assert provide.signature.return_type.instance_type.name == "Base"


def test_frt_030_shadowed_super_is_not_mistaken_for_builtin():
    source = INHERITANCE.replace(
        "def total(self) -> int:\n        return self.get()",
        "def total(self, super: int) -> int:\n        return super().get()",
    )
    with pytest.raises(UnsupportedPython, match="super"):
        PythonFrontend().parse(source)


@pytest.mark.parametrize(
    "replacement",
    [
        """    def update(self, x: str) -> None:
        self.value = 3""",
        """    def value(self) -> int:
        return 0""",
    ],
)
def test_frt_031_rejects_incompatible_inherited_members(replacement):
    source = INHERITANCE.replace(
        "    def total(self) -> int:\n        return self.get()", replacement
    )
    with pytest.raises(UnsupportedPython):
        PythonFrontend().parse(source)


def test_frt_029_rejects_type_name_super_as_class():
    with pytest.raises(UnsupportedPython, match="Duplicate or reserved"):
        PythonFrontend().parse("""\
class super:
    def __init__(self) -> None:
        self.v: int = 1
""")
