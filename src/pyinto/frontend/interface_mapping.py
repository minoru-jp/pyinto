"""interface mapping syntax adapters with explicit, narrow normalization dependencies.

A interface mapping normalizer is a per-parse component, not a PythonFrontend mixin.
It can request a value or declaration scope but cannot dispatch arbitrary
frontend methods or execute user-supplied interface mapping code.
"""

from __future__ import annotations

import ast
from collections.abc import Callable

from pyinto.constructs import (
    BooleanLiteral,
    Construct,
    FloatingLiteral,
    Literal,
    NoneLiteral,
    PortType,
    Reference,
    Symbol,
    Value,
)
from pyinto.interface_mapping import (
    InterfaceClassMapping,
    InterfaceFunctionMapping,
    InterfaceMappingRegistry,
)

from .context import ParseContext
from .errors import reject


class InterfaceMappingNormalizer:
    def __init__(
        self,
        context: ParseContext,
        registry: InterfaceMappingRegistry,
        *,
        value: Callable[[ast.expr], Value],
        declaration_scope: Callable[[], tuple[str, ...]],
    ) -> None:
        self._context = context
        self._interface_mappings = registry
        self._value = value
        self._declaration_scope = declaration_scope

    def object_constructor(
        self, name: str, annotation: str, node: ast.expr
    ) -> Construct:
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or not isinstance(node.func.value, ast.Name)
        ):
            raise reject(
                node, "interface mapping variable requires a registered constructor"
            )
        source = self._context.names.interface_aliases.get(node.func.value.id)
        if source is None or source != annotation:
            raise reject(
                node, "interface mapping constructor does not match annotation"
            )
        definition = self._interface_mappings.get_class(source)
        assert definition is not None
        factory = definition.constructors.get(node.func.attr)
        if factory is None:
            raise reject(node, "Unregistered interface mapping object constructor")
        if node.args or any(key.arg is None for key in node.keywords):
            raise reject(
                node, "interface mapping object constructors accept keywords only"
            )
        options: dict[str, int] = {}
        for item in node.keywords:
            assert item.arg is not None
            if item.arg in options:
                raise reject(item, "Duplicate interface mapping constructor keyword")
            literal = self._value(item.value)
            if not isinstance(literal, Literal) or type(literal.value) is not int:
                raise reject(
                    item, "interface mapping constraints must be integer literals"
                )
            options[item.arg] = literal.value
        shape = PortType(source, node.func.attr, tuple(sorted(options.items())))
        symbol = Symbol(name, shape, annotation, scope=self._declaration_scope())
        try:
            construct = factory(symbol, options)
        except (TypeError, ValueError) as exc:
            raise reject(
                node, f"Invalid interface mapping object declaration: {exc}"
            ) from exc
        if not isinstance(construct, Construct):
            raise reject(node, "interface mapping constructor must produce a Construct")
        self._context.names.symbols[name] = symbol
        self._context.names.interface_objects[name] = (definition, construct)
        return construct

    def object_receiver(
        self, node: ast.Attribute
    ) -> tuple[InterfaceClassMapping, Construct, Reference]:
        if not isinstance(node.value, ast.Name):
            raise reject(node, "interface mapping receiver must be a direct variable")
        name = node.value.id
        entry = self._context.names.interface_objects.get(name)
        if entry is None:
            raise reject(node, f"Unregistered interface mapping object: {name!r}")
        return (*entry, Reference(self._context.names.symbols[name]))

    def object_method(self, node: ast.Call) -> Construct:
        assert isinstance(node.func, ast.Attribute)
        definition, origin, receiver = self.object_receiver(node.func)
        if node.keywords:
            raise reject(
                node,
                "interface mapping object methods accept positional arguments only",
            )
        method = definition.methods.get(node.func.attr)
        if method is None:
            raise reject(node, "Unregistered interface mapping object method")
        if len(node.args) != len(method.positional_kinds):
            raise reject(node, "interface mapping method argument count mismatch")
        arguments = tuple(self._value(arg) for arg in node.args)
        if tuple(arg.kind for arg in arguments) != method.positional_kinds:
            raise reject(node, "interface mapping method argument kind mismatch")
        try:
            result = method.factory(origin, receiver, arguments)
        except (TypeError, ValueError) as exc:
            raise reject(node, f"Invalid interface mapping method: {exc}") from exc
        if not isinstance(result, Construct):
            raise reject(node, "interface mapping method must produce a Construct")
        return result

    def is_module_call(self, node: ast.Call) -> bool:
        """Whether an attribute call starts from an imported module binding."""
        func: ast.expr = node.func
        while isinstance(func, ast.Attribute):
            func = func.value
        return (
            isinstance(func, ast.Name) and func.id in self._context.names.module_aliases
        )

    def _call_source(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            source = self._context.names.interface_aliases.get(node.func.id)
            if source is None:
                raise reject(
                    node, f"Unregistered interface mapping call: {node.func.id!r}"
                )
            return source
        attributes: list[str] = []
        part: ast.expr = node.func
        while isinstance(part, ast.Attribute):
            attributes.append(part.attr)
            part = part.value
        if not isinstance(part, ast.Name):
            raise reject(
                node,
                "Only directly imported interface mapping calls or explicitly imported module calls are supported",
            )
        module = self._context.names.module_aliases.get(part.id)
        if module is None:
            raise reject(
                node,
                "Only directly imported interface mapping calls or explicitly imported module calls are supported",
            )
        source = ".".join((module, *reversed(attributes)))
        # Importing a package does not itself import every nested submodule.
        # Only a module explicitly imported in the source may own the call.
        if (
            source.rpartition(".")[0]
            not in self._context.names.module_import_paths[part.id]
        ):
            raise reject(
                node, f"Module function was not explicitly imported: {source!r}"
            )
        return source

    def _bind_signature(
        self,
        node: ast.Call,
        definition: InterfaceFunctionMapping,
        values: dict[ast.expr, Value],
    ) -> tuple[Value, ...]:
        """Bind already-normalized operands against one declared signature.

        The registry may provide many candidates. This method never normalizes
        an expression a second time and never invokes a mapping factory.
        """
        named_keywords = [key for key in node.keywords if key.arg != "_force"]
        variadic = definition.variadic
        if definition.parameters is None:
            fixed = definition.positional_kinds
            if len(node.args) < len(fixed) or (
                variadic is None and len(node.args) != len(fixed)
            ):
                raise reject(
                    node, "interface mapping positional argument count mismatch"
                )
            if named_keywords:
                raise reject(
                    node,
                    "Only the reserved _force interface mapping keyword is supported",
                )
            arguments = tuple(values[arg] for arg in node.args)
            if tuple(value.kind for value in arguments[: len(fixed)]) != fixed or (
                variadic is not None
                and any(
                    value.kind is not variadic.kind for value in arguments[len(fixed) :]
                )
            ):
                raise reject(
                    node, "interface mapping positional argument kind mismatch"
                )
            return arguments

        parameters = definition.parameters
        if variadic is None and len(node.args) > len(parameters):
            raise reject(node, "interface mapping argument count mismatch")
        positions = {parameter.name: i for i, parameter in enumerate(parameters)}
        bindings: list[tuple[int, ast.expr]] = list(
            enumerate(node.args[: len(parameters)])
        )
        taken = set(range(min(len(node.args), len(parameters))))
        for key in named_keywords:
            assert key.arg is not None  # Expanded keywords rejected in mapped_call.
            index = positions.get(key.arg)
            if index is None:
                raise reject(key, f"Unknown interface mapping keyword: {key.arg}")
            if index in taken:
                raise reject(key, f"Duplicate interface mapping argument: {key.arg}")
            bindings.append((index, key.value))
            taken.add(index)
        missing = [i for i in range(len(parameters)) if i not in taken]
        if any(parameters[i].default is None for i in missing):
            raise reject(node, "Missing required interface mapping argument")
        supplied: dict[int, Value] = {}
        for index, expression in bindings:
            value = values[expression]
            if value.kind is not parameters[index].kind:
                raise reject(
                    expression,
                    f"interface mapping argument kind mismatch: {parameters[index].name}",
                )
            supplied[index] = value
        tail = tuple(values[arg] for arg in node.args[len(parameters) :])
        if variadic is not None and any(
            value.kind is not variadic.kind for value in tail
        ):
            raise reject(node, "interface mapping variadic argument kind mismatch")
        # Factories build Construct parts in parameter order. If doing so would
        # reorder expressions that can carry effects, decline this call. This
        # also covers keyword arguments after a variadic positional tail.
        order = tuple(index for index, _ in bindings) + tuple(
            range(len(parameters), len(parameters) + len(tail))
        )
        if order != tuple(sorted(order)) and any(
            not isinstance(
                value,
                (Literal, FloatingLiteral, BooleanLiteral, NoneLiteral, Reference),
            )
            for value in values.values()
        ):
            raise reject(
                node,
                "Reordered interface mapping arguments with effects are unsupported",
            )
        complete: list[Value] = []
        for index, parameter in enumerate(parameters):
            value = supplied.get(index)
            if value is None:
                value = parameter.default
                assert value is not None
            complete.append(value)
        return (*complete, *tail)

    def mapped_call(self, node: ast.Call) -> Value:
        source = self._call_source(node)
        signatures = self._interface_mappings.signatures(source)
        if not signatures:
            raise reject(node, f"Unregistered interface mapping call: {source!r}")
        force_keywords = [key for key in node.keywords if key.arg == "_force"]
        if len(force_keywords) > 1:
            raise reject(node, "Duplicate reserved _force keyword")
        if force_keywords:
            forced = force_keywords[0].value
            if not isinstance(forced, ast.Constant) or not (
                forced.value is None or type(forced.value) in (bool, int, str)
            ):
                raise reject(node, "_force must be a literal without side effects")
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            raise reject(node, "Expanded interface mapping arguments are unsupported")
        if any(key.arg is None for key in node.keywords):
            raise reject(node, "Expanded interface mapping keywords are unsupported")

        # Each Python argument expression is normalized exactly once, even
        # while checking multiple signatures. No trial factory is invoked.
        values = {
            expression: self._value(expression)
            for expression in (
                *node.args,
                *(key.value for key in node.keywords if key.arg != "_force"),
            )
        }
        matches: list[tuple[InterfaceFunctionMapping, tuple[Value, ...]]] = []
        first_error: Exception | None = None
        for definition in signatures:
            try:
                bound = self._bind_signature(node, definition, values)
            except ValueError as exc:
                if first_error is None:
                    first_error = exc
                continue
            matches.append((definition, bound))
        if not matches:
            if len(signatures) == 1 and first_error is not None:
                raise first_error
            raise reject(node, "No matching interface mapping signature")
        if len(matches) != 1:
            raise reject(node, "Ambiguous interface mapping signatures")
        definition, arguments = matches[0]
        try:
            result = definition.factory(arguments)
        except (TypeError, ValueError) as exc:
            raise reject(node, f"interface mapping factory failed: {exc}") from exc
        if not isinstance(result, Value):
            raise reject(
                node, "interface mapping factory must produce a Value Construct"
            )
        return result
