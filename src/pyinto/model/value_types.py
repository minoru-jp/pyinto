"""Model value-kind references for Target authors.

Each symbol aliases the existing ValueKind singleton. This module does not
introduce new ValueType identities or change how port-typed values are keyed.
ValueKind members and PortType instances can be used as @realizes subjects.
"""

from pyinto.constructs.types import (
    CallableType,
    DictType,
    InstanceType,
    ListType,
    PortType,
    TupleType,
    ValueKind,
    ValueType,
)

Integer = ValueKind.INTEGER
Floating = ValueKind.FLOAT
String = ValueKind.STRING
Boolean = ValueKind.BOOLEAN
AnyValue = ValueKind.ANY
Object = ValueKind.OBJECT
Iterable = ValueKind.ITERABLE
NoneValue = ValueKind.NONE
Function = ValueKind.FUNCTION
Tuple = ValueKind.TUPLE
List = ValueKind.LIST
Dictionary = ValueKind.DICT
Instance = ValueKind.INSTANCE

__all__ = [
    "AnyValue",
    "Boolean",
    "CallableType",
    "DictType",
    "Dictionary",
    "Floating",
    "Function",
    "Instance",
    "InstanceType",
    "Integer",
    "Iterable",
    "List",
    "ListType",
    "NoneValue",
    "Object",
    "PortType",
    "String",
    "Tuple",
    "TupleType",
    "ValueKind",
    "ValueType",
]
