"""Host-side execution of a trusted Python module's runtime hook."""

from __future__ import annotations

import sys
from collections.abc import Callable
from types import ModuleType
from typing import TypeAlias, get_origin
from uuid import uuid4

from pyinto.frontend.runtime import RUNTIME_HOOK

# Distinct from a runtime hook which legitimately returns None.
RUNTIME_ABSENT = object()


def execute_runtime(source: str) -> object:
    """Execute trusted module text once, then call its zero-argument hook once.

    ``convert`` accepts text, not a filesystem-backed module. This creates a
    temporary module namespace (so dataclasses/type introspection work during
    execution), without a real ``__file__`` or package context. It is removed
    from ``sys.modules`` after the hook returns, including on error. Returned
    dynamically defined classes therefore have no importable module identity.
    """
    name = f"_pyinto_runtime_{uuid4().hex}"
    module = ModuleType(name)
    module.__package__ = None
    sys.modules[name] = module
    try:
        # Do not inherit this module's own __future__ flags into user code.
        code = compile(source, "<pyinto-runtime>", "exec", dont_inherit=True)
        exec(code, module.__dict__)  # noqa: S102 - trusted source only
        callback = getattr(module, RUNTIME_HOOK)
        if not callable(callback):
            raise TypeError(f"{RUNTIME_HOOK} must be callable")
        return callback()
    finally:
        del sys.modules[name]


# A concrete class is a shorthand for isinstance; anything more expressive
# belongs to a predicate supplied by the Target, not to a Host type engine.
RuntimeSchema: TypeAlias = type | Callable[[object], bool]


class RuntimeSchemaError(ValueError):
    """The Runtime Result fails the Target-declared value/schema contract."""


def is_runtime_schema(schema: object) -> bool:
    """Accept actual classes or validators, not parameterized type expressions."""
    return get_origin(schema) is None and (isinstance(schema, type) or callable(schema))


def validate_runtime_schema(value: object, schema: RuntimeSchema) -> None:
    """Check a Runtime Result before invoking the Target's ``finish``.

    A validator is a predicate: only an actual bool result is valid. Validators
    cannot replace/normalize the Runtime Result. The Host forwards the same
    object to the Target on success.
    """
    if isinstance(schema, type):
        try:
            valid = isinstance(value, schema)
        except (TypeError, ValueError) as exc:
            raise RuntimeSchemaError("Runtime schema type check failed") from exc
    else:
        try:
            verdict = schema(value)
        except Exception as exc:
            raise RuntimeSchemaError(
                "Runtime schema validator raised an exception"
            ) from exc
        if type(verdict) is not bool:
            raise RuntimeSchemaError("Runtime schema validator must return bool")
        valid = verdict
    if not valid:
        raise RuntimeSchemaError("Runtime result does not satisfy Target schema")
