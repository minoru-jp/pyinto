"""Derive *static* free lexical bindings without a Closure Construct.

No source is executed and no runtime closure object is created.  Captures are
symbol declarations, not per-invocation environments.  The latter, including
escaping values and distinct calls of one factory, remains a Realization duty.
"""

from __future__ import annotations

from pyinto.constructs import (
    Construct,
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    Reference,
    Symbol,
)


def lexical_captures(definition: FunctionDefinition) -> tuple[Symbol, ...]:
    """Find direct non-module lexical dependencies of one function body.

    A captured Symbol belongs to a strict enclosing function scope.  Function
    declaration references (including direct calls to an enclosing function)
    use their existing stable ``FunctionSignature.value_symbol``.  The result
    contains each declaration once, in first-use order, preserving *identity*.

    Nested function bodies are excluded: each function's own captures can be
    inspected separately.  A Realization that needs transitively retained
    environments must analyze the nested definitions and their escape paths;
    this function does not infer liveness or allocate runtime frames.
    """
    if not isinstance(definition, FunctionDefinition):
        raise TypeError("lexical_captures requires a FunctionDefinition")

    current_scope = (*definition.signature.scope, definition.signature.name)
    try:
        own_value_symbol = definition.signature.value_symbol
    except ConstructError:
        own_value_symbol = None
    seen: set[int] = set()
    result: list[Symbol] = []

    def consider(symbol: Symbol) -> None:
        owner = symbol.scope
        if (
            not owner  # Module-level bindings are not captured lexical locals.
            or len(owner) >= len(current_scope)
            or current_scope[: len(owner)] != owner
            or symbol is own_value_symbol
        ):
            return
        key = id(symbol)
        if key not in seen:
            seen.add(key)
            result.append(symbol)

    def visit(item: object) -> None:
        if isinstance(item, FunctionDefinition):
            # Child definitions have their own frame and capture set.
            return
        if isinstance(item, Reference):
            consider(item.symbol)
        if isinstance(item, FunctionCall):
            signature = item.signature
            if signature is not definition.signature:
                # An unshaped Port function can still be directly called.
                # Its declaration is already available through the signature.
                try:
                    symbol = signature.value_symbol
                except ConstructError:
                    symbol = None
                if symbol is not None:
                    consider(symbol)
        if isinstance(item, Construct):
            for child in item.parts().values():
                visit(child)
        elif isinstance(item, (tuple, list)):
            for child in item:
                visit(child)

    visit(definition.body)
    return tuple(result)
