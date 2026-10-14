"""Transient state of one PythonFrontend.parse() call.

Scope, class resolution, and control-flow state are separate from the
frontend configuration (interface mapping and decorator registries). Each parse creates a
fresh context, so failed parses cannot leak lexical bindings or counters.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from pyinto.constructs import (
    ClassSignature,
    Construct,
    FunctionSignature,
    InstanceType,
    Symbol,
)
from pyinto.interface_mapping import InterfaceClassMapping

from .decorators import ClassDecorationPlan


@dataclass
class NameState:
    type_aliases: set[str] = field(default_factory=set)
    callable_aliases: set[str] = field(default_factory=set)
    symbols: dict[str, Symbol] = field(default_factory=dict)
    interface_aliases: dict[str, str] = field(default_factory=dict)
    # Local Python import name -> fully qualified module namespace. Parse-local.
    module_aliases: dict[str, str] = field(default_factory=dict)
    # Exact module paths imported for each bound root (not every sibling module).
    module_import_paths: dict[str, set[str]] = field(default_factory=dict)
    interface_objects: dict[str, tuple[InterfaceClassMapping, Construct]] = field(
        default_factory=dict
    )
    functions: dict[str, FunctionSignature] = field(default_factory=dict)
    active_function: FunctionSignature | None = None
    local_names: set[str] = field(default_factory=set)
    # Only the currently active callable: names explicitly bound to module scope.
    global_names: set[str] = field(default_factory=set)
    enclosing_scopes: list[
        tuple[dict[str, Symbol], set[str], dict[str, FunctionSignature]]
    ] = field(default_factory=list)
    function_body_depth: int | None = None
    source_names: set[str] = field(default_factory=set)


@dataclass
class ClassState:
    class_decorations: dict[ast.ClassDef, ClassDecorationPlan] = field(
        default_factory=dict
    )
    class_types: dict[str, InstanceType] = field(default_factory=dict)
    classes: dict[str, ClassSignature] = field(default_factory=dict)
    active_class_type: InstanceType | None = None
    collecting_methods: bool = False
    method_owner: InstanceType | None = None
    initialized_fields: set[str] = field(default_factory=set)
    class_module_functions: dict[str, FunctionSignature] = field(default_factory=dict)


@dataclass
class FlowState:
    loop_depth: int = 0
    block_depth: int = 0
    lambda_counter: int = 0
    # Names introduced inside currently active control bodies. These are
    # Frontend acceptance boundaries, not Python lexical scopes.
    control_local_bindings: list[set[str]] = field(default_factory=list)


@dataclass
class ParseContext:
    names: NameState = field(default_factory=NameState)
    classes: ClassState = field(default_factory=ClassState)
    flow: FlowState = field(default_factory=FlowState)

    @contextmanager
    def callable_scope(
        self,
        signature: FunctionSignature,
        *,
        local_names: set[str],
        global_names: set[str] | None = None,
        function_body_depth: int | None,
        enclosing_functions: dict[str, FunctionSignature] | None = None,
        method_owner: InstanceType | None = None,
        reset_method_state: bool = False,
    ) -> Iterator[None]:
        """Enter a lexical callable and restore all shared state on exit.

        A named function owns method-initialization state; an expression
        lambda intentionally inherits that state. Neither evaluates source.
        """
        names, classes, flow = self.names, self.classes, self.flow
        old_symbols = names.symbols
        old_objects = names.interface_objects
        old_locals = names.local_names
        old_globals = names.global_names
        old_functions = names.functions
        old_active = names.active_function
        old_body_depth = names.function_body_depth
        old_loop_depth = flow.loop_depth
        old_method_state = (
            classes.collecting_methods,
            classes.method_owner,
            classes.initialized_fields,
        )
        names.enclosing_scopes.append(
            (
                old_symbols,
                old_locals,
                old_functions if enclosing_functions is None else enclosing_functions,
            )
        )
        names.symbols = {
            parameter.name: parameter for parameter in signature.parameters
        }
        if signature.variadic_parameter is not None:
            param = signature.variadic_parameter
            names.symbols[param.name] = param
        names.interface_objects = {}
        names.local_names = local_names | set(names.symbols)
        names.global_names = set() if global_names is None else set(global_names)
        names.functions = {}
        names.active_function = signature
        names.function_body_depth = function_body_depth
        flow.loop_depth = 0
        if reset_method_state:
            classes.collecting_methods = False
            classes.method_owner = method_owner
            classes.initialized_fields = set()
        try:
            yield
        finally:
            names.enclosing_scopes.pop()
            names.symbols = old_symbols
            names.interface_objects = old_objects
            names.local_names = old_locals
            names.global_names = old_globals
            names.functions = old_functions
            names.active_function = old_active
            names.function_body_depth = old_body_depth
            flow.loop_depth = old_loop_depth
            if reset_method_state:
                (
                    classes.collecting_methods,
                    classes.method_owner,
                    classes.initialized_fields,
                ) = old_method_state
