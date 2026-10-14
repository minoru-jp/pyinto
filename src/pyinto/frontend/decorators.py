"""Explicit declaration markers and trusted, registered normalization adapters.

No Python decorator expression is evaluated. Import spelling identifies a rule;
the rule's effect is handled only when an adapter was explicitly registered.
A normalizer is *frontend configuration*, not a Model Interface or Realization.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pyinto.constructs import FunctionDefinition, MethodKind

DecoratorTarget = Literal["class", "method", "function"]


@dataclass(frozen=True)
class DecoratorRule:
    """A qualified name, eligible declaration site, and explicit semantic effect."""

    source: str
    target: DecoratorTarget
    effect: str
    import_required: bool = True

    def __post_init__(self) -> None:
        if not self.source or not all(p.isidentifier() for p in self.source.split(".")):
            raise ValueError("Decorator source requires a qualified identifier")
        if self.target not in {"class", "method", "function"}:
            raise ValueError("Unsupported decorator declaration target")
        if not self.effect:
            raise ValueError("Decorator effect must be explicit")


@dataclass(frozen=True)
class ClassDecorationPlan:
    """Explicit class-declaration expansion, independent of any Target syntax.

    A trusted adapter may add syntactic method declarations to be normalized by
    the *existing* typed function rules. This is not a general decorator call.
    """

    synthesized_methods: tuple[ast.FunctionDef, ...] = ()
    allow_field_declarations: bool = False
    allow_bases: bool = True


ClassNormalizer = Callable[[ast.ClassDef], ClassDecorationPlan]
MethodNormalizer = Callable[[ast.FunctionDef], MethodKind]
FunctionNormalizer = Callable[[ast.FunctionDef, FunctionDefinition], FunctionDefinition]


class DecoratorRegistry:
    """Name/effect rules and adapters, with independent per-parse import bindings.

    A registered name without a registered handler is *not* accepted. Adapters
    run only on explicitly registered effects; source decorator bodies never run.
    """

    def __init__(self, rules: tuple[DecoratorRule, ...] = ()) -> None:
        self._rules: dict[str, DecoratorRule] = {}
        self._aliases: dict[str, str] = {}
        self._class_normalizers: dict[str, ClassNormalizer] = {}
        self._method_normalizers: dict[str, MethodNormalizer] = {}
        self._function_normalizers: dict[str, FunctionNormalizer] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: DecoratorRule) -> None:
        if rule.source in self._rules:
            raise ValueError(f"Duplicate decorator source: {rule.source}")
        self._rules[rule.source] = rule

    def _require_effect(self, target: DecoratorTarget, effect: str) -> None:
        if not any(
            rule.target == target and rule.effect == effect
            for rule in self._rules.values()
        ):
            raise ValueError(f"Unregistered {target} decorator effect: {effect}")

    def register_class_normalizer(
        self, effect: str, normalizer: ClassNormalizer
    ) -> None:
        self._require_effect("class", effect)
        if effect in self._class_normalizers:
            raise ValueError(f"Duplicate class decorator normalizer: {effect}")
        self._class_normalizers[effect] = normalizer

    def register_method_normalizer(
        self, effect: str, normalizer: MethodNormalizer
    ) -> None:
        self._require_effect("method", effect)
        if effect in self._method_normalizers:
            raise ValueError(f"Duplicate method decorator normalizer: {effect}")
        self._method_normalizers[effect] = normalizer

    def register_function_normalizer(
        self, effect: str, normalizer: FunctionNormalizer
    ) -> None:
        self._require_effect("function", effect)
        if effect in self._function_normalizers:
            raise ValueError(f"Duplicate function decorator normalizer: {effect}")
        self._function_normalizers[effect] = normalizer

    def fresh(self) -> DecoratorRegistry:
        """Share immutable registrations, but never reuse import bindings."""
        fresh = DecoratorRegistry(tuple(self._rules.values()))
        fresh._class_normalizers = self._class_normalizers.copy()
        fresh._method_normalizers = self._method_normalizers.copy()
        fresh._function_normalizers = self._function_normalizers.copy()
        return fresh

    def clear_imports(self) -> None:
        self._aliases.clear()

    @property
    def imported_names(self) -> frozenset[str]:
        return frozenset(self._aliases)

    def has_module(self, module: str) -> bool:
        return any(
            rule.import_required and rule.source.rpartition(".")[0] == module
            for rule in self._rules.values()
        )

    def bind_import(self, source: str, local: str) -> bool:
        """Bind only a registered importable decorator; return False if unknown."""
        rule = self._rules.get(source)
        if rule is None or not rule.import_required:
            return False
        if local in self._aliases:
            raise ValueError(f"Duplicate decorator import: {local}")
        self._aliases[local] = source
        return True

    def lookup(
        self, name: str, *, target: DecoratorTarget, shadowed: set[str]
    ) -> DecoratorRule | None:
        if name in shadowed:
            return None
        source = self._aliases.get(name)
        if source is None:
            builtin = f"builtins.{name}"
            rule = self._rules.get(builtin)
            source = builtin if rule is not None and not rule.import_required else None
        rule = self._rules.get(source) if source is not None else None
        return rule if rule is not None and rule.target == target else None

    def class_plan(
        self, rule: DecoratorRule, node: ast.ClassDef
    ) -> ClassDecorationPlan:
        normalizer = self._class_normalizers.get(rule.effect)
        if normalizer is None:
            raise ValueError("No normalizer for registered class decorator")
        plan = normalizer(node)
        if not isinstance(plan, ClassDecorationPlan):
            raise TypeError(
                "Class decorator normalizer must return ClassDecorationPlan"
            )
        return plan

    def method_kind(self, rule: DecoratorRule, node: ast.FunctionDef) -> MethodKind:
        normalizer = self._method_normalizers.get(rule.effect)
        if normalizer is None:
            raise ValueError("No normalizer for registered method decorator")
        kind = normalizer(node)
        if not isinstance(kind, MethodKind):
            raise TypeError("Method decorator normalizer must return MethodKind")
        return kind

    def require_function_normalizer(self, rule: DecoratorRule) -> FunctionNormalizer:
        normalizer = self._function_normalizers.get(rule.effect)
        if normalizer is None:
            raise ValueError("No normalizer for registered function decorator")
        return normalizer


def default_decorators() -> DecoratorRegistry:
    """Only the three currently adopted, statically normalized effects."""
    from .decorator_effects import dataclass_plan

    decorators = DecoratorRegistry(
        (
            DecoratorRule("builtins.staticmethod", "method", "static", False),
            DecoratorRule("builtins.classmethod", "method", "class", False),
            DecoratorRule("dataclasses.dataclass", "class", "dataclass"),
        )
    )
    decorators.register_method_normalizer("static", lambda _: MethodKind.STATIC)
    decorators.register_method_normalizer("class", lambda _: MethodKind.CLASS)
    decorators.register_class_normalizer("dataclass", dataclass_plan)
    return decorators
