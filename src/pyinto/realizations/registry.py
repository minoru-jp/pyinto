"""Validated Realization lookup and mechanical tree composition."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from pyinto.admission import AdmissionRegistry
from pyinto.constructs import (
    Call,
    Construct,
    ConstructError,
    Identifier,
    Program,
    Symbol,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.constructs.types import PortType, ValueType
from pyinto.realizations.artifacts import TextArtifactSession
from pyinto.realizations.call_layout import (
    check_direct_call_slots,
    check_direct_expression_slots,
)
from pyinto.realizations.layout import (
    Joined,
    Layout,
    Name,
    Requirements,
    Template,
    TemplatePlan,
    Text,
    TypeName,
    holes_in_order,
)
from pyinto.realizations.layout import (
    render as render_layout,
)
from pyinto.realizations.regulation import (
    ACCEPTS,
    FORBIDDEN_PREFIXES,
    NAMING,
    PACK_DISPATCH,
    PACK_ENTRIES,
    PACK_RUNTIME,
    PACK_RUNTIME_SCHEMA,
    PACK_SEMANTICS,
    PACK_SESSION,
    PACK_TARGET,
    PACK_UNHANDLED,
    REALIZES,
    RENDER,
    REQUIREMENT_LINE,
    REQUIRES,
    RESERVED,
    SEPARATORS,
    SUPPORTS,
    TEMPLATE,
    TYPE_NAME,
    VARIANT,
    VISIT,
    entry_regulation,
    pack_regulation,
    realization_target,
)
from pyinto.realizations.runtime import RuntimeSchema, is_runtime_schema

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LayoutSelector = Callable[[Construct, "EmitContext"], str | Text | TemplatePlan]
Visitor = Callable[[Construct, "EmitContext"], None]
TypeSpeller = Callable[[Symbol | ValueType | PortType], str]
TypeSelector = Callable[[ValueType | PortType, TypeSpeller], str]


@dataclass
class EmitContext:
    """Information visible to Target Realizations during composition.

    ``root`` and ``path`` expose the original Construct tree, without copies or
    access-control wrappers. A selector may inspect any related Construct (and
    its symbols/contracts), but must not mutate the input tree. ``path`` runs
    from the root to the currently selected Construct, inclusive; it is empty
    outside composition. ``headers`` and ``serial`` are *generation* state,
    independent of the input tree.
    """

    registry: RealizationRegistry
    admission: AdmissionRegistry = field(default_factory=lambda: LANGUAGE_ADMISSION)
    headers: set[str] = field(default_factory=set)
    serial: int = 0
    root: Construct | None = None
    path: tuple[Construct, ...] = ()
    session: object | None = None  # Target-owned artifact construction state

    def __post_init__(self) -> None:
        self.admission.require_baseline(LANGUAGE_ADMISSION)

    @property
    def current(self) -> Construct | None:
        return self.path[-1] if self.path else None

    @property
    def parent(self) -> Construct | None:
        return self.path[-2] if len(self.path) > 1 else None

    @property
    def ancestors(self) -> tuple[Construct, ...]:
        """Root-first ancestors, excluding the currently selected Construct."""
        return self.path[:-1]

    def fresh(self, stem: str) -> str:
        """Reserve a target-private identifier for a Realization's expansion."""
        name = f"sk_{stem}_{self.serial}"
        self.serial += 1
        return name


@dataclass(frozen=True)
class _Recipe:
    template: str | None
    selector: LayoutSelector | None
    visitor: Visitor | None
    accepts: tuple[str, ...] | None
    requires: tuple[str, ...]
    supports: frozenset[str]
    separators: Mapping[str, str]

    def select(self, node: Construct, ctx: EmitContext) -> str | Text | TemplatePlan:
        if self.selector is not None:
            try:
                result = self.selector(node, ctx)
            except ConstructError:
                raise
            except (TypeError, ValueError) as exc:
                raise ConstructError(str(exc)) from exc
            if not isinstance(result, (str, Text, TemplatePlan)):
                raise ConstructError(
                    "Realization renderer must return template text, a TemplatePlan, "
                    "or a Text fragment"
                )
            return result
        if self.template is None:
            raise ConstructError("No Realization template")
        return self.template

    def visit(self, node: Construct, ctx: EmitContext) -> None:
        if self.visitor is None:
            raise ConstructError("No structural Realization visitor")
        try:
            result = self.visitor(node, ctx)
        except ConstructError:
            raise
        except (TypeError, ValueError) as exc:
            raise ConstructError(str(exc)) from exc
        if result is not None:
            raise ConstructError("Structural Realization visitor must return None")


class RealizationRegistry:
    """Immutable target rules. A fresh Composer owns emission-specific state."""

    @classmethod
    def from_pack(
        cls,
        pack: type[object],
    ) -> RealizationRegistry:
        result = pack_regulation.validate(pack)
        if not result.is_valid:
            raise ValueError(
                "Invalid Target Pack: "
                + "; ".join(d.message for d in result.diagnostics)
            )
        item = result.view.focused
        return cls(
            item.values(PACK_TARGET)[0],
            item.values(PACK_ENTRIES)[0],
            dispatch=item.values(PACK_DISPATCH)[0]
            if item.has(PACK_DISPATCH)
            else "composition",
            session_factory=cast(Callable[[], object], item.values(PACK_SESSION)[0])
            if item.has(PACK_SESSION)
            else None,
            semantics=item.values(PACK_SEMANTICS)[0]
            if item.has(PACK_SEMANTICS)
            else "preservation",
            unhandled=item.values(PACK_UNHANDLED)[0]
            if item.has(PACK_UNHANDLED)
            else "error",
            runtime=item.values(PACK_RUNTIME)[0]
            if item.has(PACK_RUNTIME)
            else "ignored",
            runtime_schema=cast(RuntimeSchema, item.values(PACK_RUNTIME_SCHEMA)[0])
            if item.has(PACK_RUNTIME_SCHEMA)
            else None,
        )

    def __init__(
        self,
        target_name: str,
        declarations: Iterable[type[object]],
        *,
        dispatch: str = "composition",
        session_factory: Callable[[], object] | None = None,
        semantics: str = "preservation",
        unhandled: str = "error",
        runtime: str = "ignored",
        runtime_schema: RuntimeSchema | None = None,
    ):
        if not target_name:
            raise ValueError("Target name must not be empty")
        if dispatch not in ("composition", "structural"):
            raise ValueError("Invalid Target dispatch mode")
        if semantics not in ("preservation", "projection"):
            raise ValueError("Invalid Target semantics mode")
        if runtime not in ("required", "forbidden", "optional", "ignored"):
            raise ValueError("Invalid Target runtime policy")
        if runtime_schema is not None:
            if not is_runtime_schema(runtime_schema):
                raise TypeError("Runtime schema must be a type or a callable validator")
            if runtime not in ("required", "optional"):
                raise ValueError(
                    "Runtime schema needs required or optional runtime policy"
                )
        if unhandled not in ("error", "traverse"):
            raise ValueError("Invalid unhandled Construct policy")
        if unhandled == "traverse" and (
            dispatch != "structural" or semantics != "projection"
        ):
            raise ValueError(
                "Unhandled traverse needs structural dispatch and projection semantics"
            )
        if session_factory is not None and not callable(session_factory):
            raise TypeError("Artifact session factory must be callable")
        if dispatch == "structural" and session_factory is None:
            raise ValueError("Structural Target needs an artifact session")
        if runtime in ("required", "optional") and session_factory is None:
            raise ValueError("Runtime-enabled Target needs an artifact session")
        recipes: dict[tuple[type[Construct], str], _Recipe] = {}
        calls: dict[str, _Recipe] = {}
        spellings: dict[str, str | TypeSelector] = {}
        reserved: frozenset[str] = frozenset()
        prefixes: tuple[str, ...] = ()
        requirement_template = "${name}"
        seen_naming = False
        for declaration in declarations:
            result = entry_regulation.validate(declaration)
            if not result.is_valid:
                raise ValueError(
                    f"Invalid target entry {declaration.__name__}: "
                    + "; ".join(d.message for d in result.diagnostics)
                )
            entry = result.view.focused
            recipe = _Recipe(
                template=entry.values(TEMPLATE)[0] if entry.has(TEMPLATE) else None,
                selector=cast(LayoutSelector, entry.values(RENDER)[0])
                if entry.has(RENDER)
                else None,
                visitor=cast(Visitor, entry.values(VISIT)[0])
                if entry.has(VISIT)
                else None,
                accepts=entry.values(ACCEPTS)[0] if entry.has(ACCEPTS) else None,
                requires=tuple(entry.values(REQUIRES)),
                supports=frozenset(entry.values(SUPPORTS)[0])
                if entry.has(SUPPORTS)
                else frozenset(),
                separators=MappingProxyType(dict(entry.values(SEPARATORS)[0]))
                if entry.has(SEPARATORS)
                else MappingProxyType({}),
            )
            element_route = (
                realization_target(entry.values(REALIZES)[0])
                if entry.has(REALIZES)
                else None
            )
            if (
                element_route is not None
                and element_route[0] in ("construct", "call")
                and (recipe.visitor is not None) != (dispatch == "structural")
            ):
                raise ValueError(
                    f"{target_name} realization dispatch does not match "
                    f"{dispatch!r} mode"
                )
            if element_route is not None and element_route[0] == "construct":
                kind = cast(type[Construct], element_route[1])
                # Structural projection must distinguish an intentionally
                # selected variant from an accidentally omitted declaration.
                domain = kind.variant_domain()
                if (
                    not entry.has(VARIANT)
                    and domain is not None
                    and "default" not in domain
                ):
                    raise ValueError(
                        f"{kind.__name__}: invalid variant 'default'; "
                        "this Construct has no default variant"
                    )
                if (
                    dispatch == "structural"
                    and semantics == "projection"
                    and not entry.has(VARIANT)
                    and (domain is None or len(domain) > 1)
                ):
                    raise ValueError(
                        f"{kind.__name__} requires explicit variant in "
                        "structural projection (use '*' for all variants)"
                    )
                variant = entry.values(VARIANT)[0] if entry.has(VARIANT) else "default"
                key = (kind, variant)
                if key in recipes:
                    raise ValueError(
                        f"Duplicate {target_name} realization for {kind.__name__}:{variant}"
                    )
                recipes[key] = recipe
            elif element_route is not None and element_route[0] == "call":
                name = cast(str, element_route[1])
                if name in calls:
                    raise ValueError(f"Duplicate call realization for {name!r}")
                calls[name] = recipe
            elif element_route is not None and element_route[0] == "type":
                name = cast(str, element_route[1])
                if name in spellings:
                    raise ValueError(f"Duplicate type spelling {name!r}")
                spellings[name] = cast(str | TypeSelector, entry.values(TYPE_NAME)[0])
            elif entry.has(NAMING):
                if seen_naming:
                    raise ValueError("Duplicate naming entry")
                seen_naming = True
                if entry.has(RESERVED):
                    reserved = entry.values(RESERVED)[0]
                if entry.has(FORBIDDEN_PREFIXES):
                    prefixes = entry.values(FORBIDDEN_PREFIXES)[0]
                if entry.has(REQUIREMENT_LINE):
                    requirement_template = entry.values(REQUIREMENT_LINE)[0]
        self.target = target_name
        self.dispatch = dispatch
        self.semantics = semantics
        self.unhandled = unhandled
        self.runtime = runtime
        self.runtime_schema = runtime_schema
        self.session_factory: Callable[[], object] = (
            session_factory if session_factory is not None else TextArtifactSession
        )
        self._recipes = MappingProxyType(recipes)
        self._calls = MappingProxyType(calls)
        self._types = MappingProxyType(spellings)
        self._reserved = reserved
        self._prefixes = prefixes
        self._requirement_line = requirement_template

    def _lookup(self, node: Construct) -> _Recipe | None:
        """Apply the same exact route for both dispatch filtering and lookup."""
        if isinstance(node, Call):
            return self._calls.get(node.callee.name)
        kind = type(node)
        return self._recipes.get((kind, node.variant())) or self._recipes.get(
            (kind, "*")
        )

    def has_recipe(self, node: Construct) -> bool:
        """Whether this Construct/variant (including wildcard) or Call matches.

        Only structural projection dispatch uses this to traverse explicitly
        unhandled nodes. A registered Realization's errors are never skipped.
        """
        return self._lookup(node) is not None

    def recipe(self, node: Construct, ctx: EmitContext) -> _Recipe:
        recipe = self._lookup(node)
        if recipe is None:
            where = (
                f"call {node.callee.name!r}"
                if isinstance(node, Call)
                else f"{type(node).__name__}:{node.variant()}"
            )
            raise ConstructError(f"No {self.target!r} realization for {where}")
        if isinstance(node, Call):
            if node.callee.kind is not None:
                raise ConstructError("Call target must be a registered callable")
            signature = tuple(arg.kind.value for arg in node.arguments)
            if recipe.accepts is not None and signature != recipe.accepts:
                raise ConstructError(
                    f"{node.callee.name} expects {recipe.accepts}, got {signature}"
                )
        unsupported = (
            ctx.admission.required_contracts(node) - recipe.supports
            if self.semantics == "preservation"
            else frozenset()
        )
        if unsupported:
            raise ConstructError(
                f"{self.target!r} realization for {type(node).__name__} "
                f"does not support contracts: {', '.join(sorted(unsupported))}"
            )
        ctx.headers.update(recipe.requires)
        return recipe

    def type_name(self, model_type: Symbol | ValueType | PortType) -> str:
        """Spell a complete Model type through this Target's registered rules.

        A dynamic spelling receives the concrete shape and a ``spell`` callback
        that re-enters these same rules for nested types. Each top-level request
        owns its own recursion guard, including when a selector fails.
        """
        active: set[ValueType | PortType] = set()

        def spell(item: Symbol | ValueType | PortType) -> str:
            if isinstance(item, Symbol):
                if item.type is None:
                    raise ConstructError("Callable cannot have a variable type")
                concrete = item.type
            elif isinstance(item, (ValueType, PortType)):
                concrete = item
            else:
                raise ConstructError("Type representation needs a Model type or Symbol")
            if concrete in active:
                raise ConstructError("Cyclic type spelling for a Model type")
            key = (
                concrete.key if isinstance(concrete, PortType) else concrete.kind.value
            )
            spelling = self._types.get(key)
            if spelling is None:
                raise ConstructError(
                    f"No {self.target!r} type representation for {key!r}"
                )
            active.add(concrete)
            try:
                if callable(spelling):
                    try:
                        value = spelling(concrete, spell)
                    except ConstructError:
                        raise
                    except (TypeError, ValueError) as exc:
                        raise ConstructError(str(exc)) from exc
                else:
                    value = spelling
                if not isinstance(value, str) or not value:
                    raise ConstructError("Type Realization must yield nonempty text")
                return value
            finally:
                active.remove(concrete)

        return spell(model_type)

    def name(self, name: str) -> str:
        if (
            not _IDENTIFIER.fullmatch(name)
            or name in self._reserved
            or any(name.startswith(p) for p in self._prefixes)
        ):
            raise ConstructError(
                f"Name is not portable to {self.target.upper()}: {name!r}"
            )
        return name

    def requirements(self, ctx: EmitContext) -> str:
        return "\n".join(
            self._requirement_line.replace("${name}", name)
            for name in sorted(ctx.headers)
        )


class Composer:
    """Resolve child-to-Slot connections recursively, without source text output."""

    def __init__(
        self,
        registry: RealizationRegistry,
        *,
        admission: AdmissionRegistry | None = None,
        session: object | None = None,
    ) -> None:
        self.context = EmitContext(
            registry=registry,
            admission=admission if admission is not None else LANGUAGE_ADMISSION,
            session=session,
        )

    def layout(self, node: Construct) -> Layout:
        # A top-level composition begins a fresh emission, so names and header
        # requirements cannot leak between independent calls on one Composer.
        if not self.context.path:
            self.context.admission.check_tree(node)
            self.context = EmitContext(
                registry=self.context.registry,
                admission=self.context.admission,
                root=node,
                session=self.context.session,
            )
        ctx = self.context
        previous_path = ctx.path
        ctx.path = (*previous_path, node)
        try:
            recipe = ctx.registry.recipe(node, ctx)
            template = recipe.select(node, ctx)
            if isinstance(template, str):
                # Check simple call layouts even when a recipe *claims* all
                # required contracts. Dynamic TemplatePlans need target-specific
                # verification because their Slots may be built recursively.
                check_direct_call_slots(node, template)
                check_direct_expression_slots(node, template)
            if isinstance(template, Text):
                if node.parts():
                    raise ConstructError(
                        "Text fragments may only realize leaf Constructs"
                    )
                return template
            parts = dict(node.parts())
            # Program requirements are composer-owned, never Realization input.
            reserved = {"requirements"} if isinstance(node, Program) else set()
            if isinstance(template, TemplatePlan):
                additions = template.slots
                duplicate = additions.keys() & (parts.keys() | reserved)
                if duplicate:
                    raise ConstructError(
                        f"Realization cannot replace Model parts: {sorted(duplicate)}"
                    )
                unused = additions.keys() - set(holes_in_order(template.source))
                if unused:
                    raise ConstructError(f"Unused Realization slots: {sorted(unused)}")
                parts.update(additions)
                template = template.source
            slots = holes_in_order(template)
            unused_separators = recipe.separators.keys() - set(slots)
            if unused_separators:
                raise ConstructError(
                    f"Separators refer to unused Slots: {sorted(unused_separators)}"
                )
            # Output requirements belong to the composition layer, not to the
            # source Program. They are populated after all children are composed.
            unknown = set(slots) - parts.keys() - reserved
            if unknown:
                raise ConstructError(f"Unfilled template holes: {sorted(unknown)}")
            return Template(
                template,
                {
                    key: Requirements()
                    if key in reserved
                    else self._part(parts[key], separator=recipe.separators.get(key))
                    for key in slots
                },
            )
        finally:
            ctx.path = previous_path

    def _part(self, part: object, *, separator: str | None = None) -> Layout:
        if separator is not None and not isinstance(part, tuple):
            raise ConstructError("Slot separator requires a tuple Model part")
        if isinstance(part, Construct):
            return self.layout(part)
        if isinstance(part, tuple):
            return Joined(
                tuple(self._part(child) for child in part),
                separator if separator is not None else "\n",
            )
        if isinstance(part, Joined):
            return Joined(
                tuple(self._part(child) for child in part.children), part.separator
            )
        if isinstance(part, Identifier):
            return Name(part.value)
        if isinstance(part, Symbol):
            if part.type is None:
                raise ConstructError("Callable cannot have a variable type")
            return TypeName(part.type)
        if isinstance(part, (ValueType, PortType)):
            return TypeName(part)
        if isinstance(part, (Text, Name, TypeName, Requirements, Template)):
            return part
        if isinstance(part, str):
            return Text(part)
        raise ConstructError(f"Unsupported Slot component: {type(part).__name__}")

    def source(self, root: Construct) -> str:
        layout = self.layout(root)
        result = render_layout(layout, self.context)
        return result.rstrip("\n") + "\n"
