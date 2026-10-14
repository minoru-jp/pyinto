"""Target-neutral admission contracts owned by Construct providers.

Providers declare each concrete Construct, including those whose current
realization admission requirements are empty. A Target Pack merely declares
which concrete obligation keys it supports; it cannot invent or waive them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import MappingProxyType

from pyinto.constructs.base import Construct
from pyinto.constructs.types import ConstructError


@dataclass(frozen=True)
class AdmissionRule:
    """A provider-defined, Target-independent group of semantic obligations.

    A contract ending in ``.*`` declares an *open family* of concrete names.
    This never authorizes a Target to use wildcard ``supports`` declarations.
    """

    name: str
    constructs: tuple[type[Construct], ...]
    guarded_fields: frozenset[str]
    contracts: frozenset[str]
    resolve: Callable[[Construct], frozenset[str]]


@dataclass(frozen=True)
class AdmissionDeclaration:
    """Explicit provider-owned admission policy for one *exact* Construct type.

    An empty ``rules`` tuple is an intentional declaration that no additional
    runtime admission keys have yet been established for this Construct, NOT a
    claim that arbitrary Target recipes preserve its semantics.
    """

    construct: type[Construct]
    rules: tuple[AdmissionRule, ...] = ()


def _matches_contract(name: str, declared: frozenset[str]) -> bool:
    return name in declared or any(
        token.endswith(".*") and name.startswith(token[:-1]) for token in declared
    )


def collect_contracts(
    node: Construct, rules: Iterable[AdmissionRule]
) -> frozenset[str]:
    """Extract only explicit, provider-defined obligations, without inference."""
    required: set[str] = set()
    for rule in rules:
        if type(node) in rule.constructs:
            names = rule.resolve(node)
            if not all(_matches_contract(name, rule.contracts) for name in names):
                raise ValueError(f"Admission rule {rule.name} emitted undeclared key")
            required.update(names)
    return frozenset(required)


class AdmissionRegistry:
    """Immutable provider catalog, independent of any selected Target Pack.

    Exact type registration ensures that subclassing a known Construct never
    silently inherits an admission policy that did not examine its new fields.
    """

    def __init__(self, declarations: Iterable[AdmissionDeclaration] = ()) -> None:
        policies: dict[type[Construct], tuple[AdmissionRule, ...]] = {}
        rule_names: dict[str, AdmissionRule] = {}
        for declaration in declarations:
            cls = declaration.construct
            if not isinstance(cls, type) or not issubclass(cls, Construct):
                raise TypeError("Admission declaration requires a Construct type")
            if cls in policies:
                raise ValueError(f"Duplicate Construct admission: {cls.__name__}")
            if len({rule.name for rule in declaration.rules}) != len(declaration.rules):
                raise ValueError("Duplicate admission rule names")
            for rule in declaration.rules:
                if cls not in rule.constructs:
                    raise ValueError(
                        f"Admission rule {rule.name} does not cover {cls.__name__}"
                    )
                if not rule.name or not rule.contracts or not rule.constructs:
                    raise ValueError("Invalid admission rule declaration")
                if not rule.guarded_fields <= set(
                    getattr(cls, "__dataclass_fields__", {})
                ):
                    raise ValueError(
                        f"Admission rule {rule.name} guards unknown fields"
                    )
                other = rule_names.setdefault(rule.name, rule)
                if other is not rule:
                    raise ValueError("Duplicate admission rule names")
            policies[cls] = declaration.rules
        self._policies = MappingProxyType(policies)

    @property
    def declarations(self) -> tuple[AdmissionDeclaration, ...]:
        return tuple(
            AdmissionDeclaration(cls, rules) for cls, rules in self._policies.items()
        )

    def require_baseline(self, baseline: AdmissionRegistry) -> None:
        """Require an unchanged provider-owned baseline, allowing additions.

        This check is independent of any particular Interface. It is used by
        the Host to protect its Language Construct policies from replacement.
        """
        for cls, rules in baseline._policies.items():
            if cls not in self._policies or self._policies[cls] != rules:
                raise ValueError(
                    f"Missing or replaced baseline Construct admission: {cls.__name__}"
                )

    def extend(self, declarations: Iterable[AdmissionDeclaration]) -> AdmissionRegistry:
        """Provider-only extension. Existing policies cannot be replaced."""
        return AdmissionRegistry((*self.declarations, *tuple(declarations)))

    def _rules_for(self, node: Construct) -> tuple[AdmissionRule, ...]:
        try:
            return self._policies[type(node)]
        except KeyError as exc:
            raise ConstructError(
                f"Unregistered Construct admission: {type(node).__name__}"
            ) from exc

    def check_tree(self, root: Construct) -> None:
        """Reject undeclared children even if a Template ignores their Slots.

        This is an inventory check, not a requirement that all children are
        realized. Whether omission preserves meaning remains a separate issue.
        """
        visited: set[int] = set()
        pending: list[object] = [root]
        while pending:
            item = pending.pop()
            if isinstance(item, Construct):
                if id(item) in visited:
                    continue
                visited.add(id(item))
                self._rules_for(item)
                pending.extend(item.parts().values())
            elif isinstance(item, (tuple, list)):
                pending.extend(item)

    def required_contracts(self, node: Construct) -> frozenset[str]:
        """Fail closed on unregistered concrete Construct types."""
        return collect_contracts(node, self._rules_for(node))
