"""Explicit Python interface mapping declarations, no target APIs or inference in Core.

Both function Ports and object Ports resolve by exact fully qualified import.
Object declarations provide only explicit constructors, methods and properties.
They are the sole gateway from Python surface syntax to domain Constructs.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

from pyinto.admission import AdmissionDeclaration, AdmissionRegistry
from pyinto.constructs import (
    BooleanLiteral,
    FloatingLiteral,
    Literal,
    NoneLiteral,
    Value,
    ValueKind,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION

if TYPE_CHECKING:
    from pyinto.constructs import Construct, Reference, Symbol

_QUALIFIED = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
_IDENT = re.compile(r"[A-Za-z_]\w*")


@dataclass(frozen=True)
class InterfaceParameter:
    """One named Python parameter of a mapped external function.

    A default is an already-defined immutable Model literal, never an
    expression to execute or evaluate during normalization. None denotes a
    required parameter; use NoneLiteral() for a Python ``None`` default.
    """

    name: str
    kind: ValueKind
    default: Value | None = None


@dataclass(frozen=True)
class InterfaceVariadicParameter:
    """Named, homogeneous ``*args`` tail supplied as explicit positional values.

    Dynamic argument unpacking is not supported. The mapping factory receives
    the tail as the remaining elements of its flat argument tuple.
    """

    name: str
    kind: ValueKind


@dataclass(frozen=True, init=False)
class InterfaceFunctionMapping:
    """Statically declared external function signature and Model factory.

    ``parameters`` enables Python positional/keyword binding and defaults.
    The old positional-only signature remains valid for existing mappings.
    ``_force`` is a reserved Python-only keyword, never a Model argument.
    """

    source: str
    positional_kinds: tuple[ValueKind, ...]
    factory: Callable[[tuple[Value, ...]], Value]
    parameters: tuple[InterfaceParameter, ...] | None
    variadic: InterfaceVariadicParameter | None

    def __init__(
        self,
        source: str,
        positional_kinds: tuple[ValueKind, ...] = (),
        factory: Callable[[tuple[Value, ...]], Value] | None = None,
        *,
        parameters: tuple[InterfaceParameter, ...] | None = None,
        variadic: InterfaceVariadicParameter | None = None,
    ) -> None:
        if factory is None or not callable(factory):
            raise TypeError("Interface function mapping requires a callable factory")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "positional_kinds", positional_kinds)
        object.__setattr__(self, "factory", factory)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "variadic", variadic)


@dataclass(frozen=True)
class InterfaceMethodMapping:
    """Domain-object method supported at a known receiver and signature."""

    positional_kinds: tuple[ValueKind, ...]
    factory: Callable[[Construct, Reference, tuple[Value, ...]], Construct]


@dataclass(frozen=True)
class InterfaceClassMapping:
    """Opt-in instance Port, independent of the concrete Target Binding.

    Constructor keyword values are literal integers in the initial prototype.
    Cleanup is registered as an ordinary explicit instance method.
    """

    source: str
    constructors: Mapping[str, Callable[[Symbol, Mapping[str, int]], Construct]]
    methods: Mapping[str, InterfaceMethodMapping]
    properties: Mapping[str, Callable[[Construct, Reference], Value]]


class InterfaceMappingRegistry:
    """Immutable, explicitly selected interface mapping entries; collisions are errors."""

    @classmethod
    def from_declarations(
        cls,
        parents: Iterable[type[object]],
        *,
        admission_declarations: Iterable[AdmissionDeclaration] = (),
    ) -> InterfaceMappingRegistry:
        """Select nested @maps/@signature declarations and reuse the same validator.

        Declarations are explicit, never discovered or auto-registered by import.
        """
        from pyinto.interface_mapping.declarations import collect_function_declarations

        return cls(
            collect_function_declarations(parents),
            admission_declarations=admission_declarations,
        )

    def __init__(
        self,
        definitions: Iterable[InterfaceFunctionMapping | InterfaceClassMapping] = (),
        *,
        admission_declarations: Iterable[AdmissionDeclaration] = (),
    ) -> None:
        functions: dict[str, list[InterfaceFunctionMapping]] = {}
        classes: dict[str, InterfaceClassMapping] = {}
        for definition in definitions:
            if not _QUALIFIED.fullmatch(definition.source):
                raise ValueError(
                    f"Invalid qualified interface mapping name: {definition.source!r}"
                )
            if definition.source in classes or (
                isinstance(definition, InterfaceClassMapping)
                and definition.source in functions
            ):
                raise ValueError(
                    f"Duplicate interface mapping mapping: {definition.source!r}"
                )
            if isinstance(definition, InterfaceFunctionMapping):
                if not callable(definition.factory):
                    raise TypeError(
                        f"Invalid interface mapping factory: {definition.source!r}"
                    )
                if definition.parameters is not None:
                    if definition.positional_kinds:
                        raise ValueError(
                            "Named interface parameters cannot mix with positional_kinds"
                        )
                    if not isinstance(definition.parameters, tuple):
                        raise TypeError("Interface parameters must be a tuple")
                    seen: set[str] = set()
                    saw_default = False
                    for parameter in definition.parameters:
                        if not isinstance(parameter, InterfaceParameter):
                            raise TypeError("Invalid interface function parameter")
                        if (
                            not _IDENT.fullmatch(parameter.name)
                            or keyword.iskeyword(parameter.name)
                            or parameter.name == "_force"
                            or parameter.name in seen
                        ):
                            raise ValueError("Invalid or duplicate interface parameter")
                        seen.add(parameter.name)
                        if not isinstance(parameter.kind, ValueKind):
                            raise TypeError("Invalid interface parameter kind")
                        default = parameter.default
                        if default is not None:
                            if (
                                not isinstance(
                                    default,
                                    (
                                        Literal,
                                        FloatingLiteral,
                                        BooleanLiteral,
                                        NoneLiteral,
                                    ),
                                )
                                or default.kind is not parameter.kind
                            ):
                                raise ValueError(
                                    "Interface default must be an immutable literal of the declared kind"
                                )
                            saw_default = True
                        elif saw_default:
                            raise ValueError(
                                "Required interface parameter cannot follow a default"
                            )
                elif not isinstance(definition.positional_kinds, tuple) or any(
                    not isinstance(kind, ValueKind)
                    for kind in definition.positional_kinds
                ):
                    raise TypeError("Invalid interface positional kinds")
                variadic = definition.variadic
                if variadic is not None:
                    if not isinstance(variadic, InterfaceVariadicParameter):
                        raise TypeError("Invalid variadic interface parameter")
                    if (
                        not _IDENT.fullmatch(variadic.name)
                        or keyword.iskeyword(variadic.name)
                        or variadic.name == "_force"
                        or not isinstance(variadic.kind, ValueKind)
                        or (
                            definition.parameters is not None
                            and variadic.name in {p.name for p in definition.parameters}
                        )
                    ):
                        raise ValueError("Invalid variadic interface parameter")
                entries = functions.setdefault(definition.source, [])
                if any(
                    (existing.positional_kinds, existing.parameters, existing.variadic)
                    == (definition.positional_kinds, definition.parameters, variadic)
                    for existing in entries
                ):
                    raise ValueError(
                        f"Duplicate interface mapping signature: {definition.source!r}"
                    )
                entries.append(definition)
            elif isinstance(definition, InterfaceClassMapping):
                if not definition.constructors:
                    raise ValueError(
                        "interface mapping class requires an explicit constructor"
                    )
                if any(
                    not _IDENT.fullmatch(name) or not callable(factory)
                    for name, factory in definition.constructors.items()
                ):
                    raise ValueError("Invalid interface mapping class constructor")
                if any(
                    not _IDENT.fullmatch(name) or not callable(method.factory)
                    for name, method in definition.methods.items()
                ):
                    raise ValueError("Invalid interface mapping class method")
                if any(
                    not _IDENT.fullmatch(name) or not callable(factory)
                    for name, factory in definition.properties.items()
                ):
                    raise ValueError("Invalid interface mapping class property")
                # Registry snapshots declarations so plugin mutation cannot
                # change which operations were validated/registered.
                classes[definition.source] = replace(
                    definition,
                    constructors=MappingProxyType(dict(definition.constructors)),
                    methods=MappingProxyType(dict(definition.methods)),
                    properties=MappingProxyType(dict(definition.properties)),
                )
            else:
                raise TypeError("Unknown interface mapping declaration")
        self.admission: AdmissionRegistry = LANGUAGE_ADMISSION.extend(
            admission_declarations
        )
        self._entries = MappingProxyType(
            {source: tuple(definitions) for source, definitions in functions.items()}
        )
        self._classes = MappingProxyType(classes)

    def has_namespace(self, namespace: str) -> bool:
        """Recognize a static imported module prefix without importing Python code.

        Only explicitly registered fully-qualified operations establish a module
        namespace; arbitrary Python imports do not enable conversion.
        """
        prefix = namespace + "."
        return any(name.startswith(prefix) for name in self._entries) or any(
            name.startswith(prefix) for name in self._classes
        )

    def get(self, source: str) -> InterfaceFunctionMapping | None:
        """Check whether a source is registered (first signature if overloaded).

        Use ``signatures()`` when selecting a matching call signature.
        """
        definitions = self._entries.get(source, ())
        return definitions[0] if definitions else None

    def signatures(self, source: str) -> tuple[InterfaceFunctionMapping, ...]:
        """All declared candidate signatures in stable registration order."""
        return self._entries.get(source, ())

    def get_class(self, source: str) -> InterfaceClassMapping | None:
        """Resolve a registered object Port, never guess."""
        return self._classes.get(source)
