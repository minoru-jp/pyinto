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
from pyinto.constructs.types import MappedType, ValueType
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
    purpose_errors,
    read_entry,
    read_pack,
    realization_target,
)
from pyinto.realizations.runtime import RuntimeSchema, is_runtime_schema

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LayoutSelector = Callable[[Construct, "EmitContext"], str | Text | TemplatePlan]
Visitor = Callable[[Construct, "EmitContext"], None]
TypeSpeller = Callable[[Symbol | ValueType | MappedType], str]
TypeSelector = Callable[[ValueType | MappedType, TypeSpeller], str]


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

    def type_name(self, model_type: Symbol | ValueType | MappedType) -> str:
        """Spell a type for a callback, recording its declared requirements."""
        self.headers.update(self.registry.type_requirements(model_type))
        return self.registry.type_name(model_type)

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
        item = read_pack(pack)
        return cls(
            cast(str, item.value("target")),
            cast(tuple[type[object], ...], item.value("entries")),
            dispatch=cast(str, item.values.get("dispatch", "composition")),
            session_factory=cast(
                Callable[[], object] | None, item.values.get("session")
            ),
            semantics=cast(str, item.values.get("semantics", "preservation")),
            unhandled=cast(str, item.values.get("unhandled", "error")),
            purpose=cast(str, item.values.get("purpose", "conversion")),
            runtime=cast(str | None, item.values.get("runtime")),
            runtime_schema=cast(
                RuntimeSchema | None, item.values.get("runtime_schema")
            ),
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
        purpose: str = "conversion",
        runtime: str | None = None,
        runtime_schema: RuntimeSchema | None = None,
    ):
        if not target_name:
            raise ValueError("Target name must not be empty")
        if dispatch not in ("composition", "structural"):
            raise ValueError("Invalid Target dispatch mode")
        if semantics not in ("preservation", "projection"):
            raise ValueError("Invalid Target semantics mode")
        if runtime_schema is not None and not is_runtime_schema(runtime_schema):
            raise TypeError("Runtime schema must be a type or a callable validator")
        for problem in purpose_errors(
            purpose,
            runtime,
            semantics=semantics,
            has_session=session_factory is not None,
            has_schema=runtime_schema is not None,
        ):
            raise ValueError(problem)
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
        recipes: dict[tuple[type[Construct], str], _Recipe] = {}
        calls: dict[str, _Recipe] = {}
        spellings: dict[str, str | TypeSelector] = {}
        type_requires: dict[str, tuple[str, ...]] = {}
        reserved: frozenset[str] = frozenset()
        prefixes: tuple[str, ...] = ()
        requirement_template = "${name}"
        seen_naming = False
        for declaration in declarations:
            entry = read_entry(declaration)
            recipe = _Recipe(
                template=cast(str | None, entry.values.get("template")),
                selector=cast(LayoutSelector | None, entry.values.get("render")),
                visitor=cast(Visitor | None, entry.values.get("visit")),
                accepts=cast(tuple[str, ...] | None, entry.values.get("accepts")),
                requires=cast(tuple[str, ...], entry.values.get("requires", ())),
                supports=frozenset(
                    cast(tuple[str, ...], entry.values.get("supports", ()))
                ),
                separators=MappingProxyType(
                    dict(cast(dict[str, str], entry.values.get("separators", {})))
                ),
            )
            element_route = (
                realization_target(entry.marker("realizes"))
                if entry.has_marker("realizes")
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
                    not entry.has("variant")
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
                    and not entry.has("variant")
                    and (domain is None or len(domain) > 1)
                ):
                    raise ValueError(
                        f"{kind.__name__} requires explicit variant in "
                        "structural projection (use '*' for all variants)"
                    )
                variant = cast(str, entry.values.get("variant", "default"))
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
                spellings[name] = cast(str | TypeSelector, entry.value("type_name"))
                type_requires[name] = cast(
                    tuple[str, ...], entry.values.get("requires", ())
                )
            elif entry.has_marker("naming"):
                if seen_naming:
                    raise ValueError("Duplicate naming entry")
                seen_naming = True
                if entry.has("reserved"):
                    reserved = cast(frozenset[str], entry.value("reserved"))
                if entry.has("forbidden_prefixes"):
                    prefixes = cast(tuple[str, ...], entry.value("forbidden_prefixes"))
                if entry.has("requirement_line"):
                    requirement_template = cast(str, entry.value("requirement_line"))
        self.target = target_name
        self.dispatch = dispatch
        self.semantics = semantics
        self.unhandled = unhandled
        self.purpose = purpose
        self.runtime = runtime
        self.runtime_schema = runtime_schema
        self.session_factory: Callable[[], object] = (
            session_factory if session_factory is not None else TextArtifactSession
        )
        self._recipes = MappingProxyType(recipes)
        self._calls = MappingProxyType(calls)
        self._types = MappingProxyType(spellings)
        self._type_requires = MappingProxyType(type_requires)
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

    def covers_type(self, key: str) -> bool:
        """Whether a type spelling is registered for ``integer``, ``kind:Wide`` ..."""
        return key in self._types

    def covers_construct(self, kind: type[Construct]) -> bool:
        """Whether any variant (or ``*``) of a Construct type is registered."""
        return any(registered is kind for registered, _ in self._recipes)

    def type_requirements(
        self, model_type: Symbol | ValueType | MappedType
    ) -> frozenset[str]:
        """Requirement names declared by every type spelling the type uses."""
        used: set[str] = set()
        self.type_name(model_type, _used=used)
        return frozenset(
            requirement for key in used for requirement in self._type_requires[key]
        )

    def type_name(
        self,
        model_type: Symbol | ValueType | MappedType,
        *,
        _used: set[str] | None = None,
    ) -> str:
        """Spell a complete Model type through this Target's registered rules.

        A dynamic spelling receives the concrete shape and a ``spell`` callback
        that re-enters these same rules for nested types. Each top-level request
        owns its own recursion guard, including when a selector fails.
        """
        # Keyed by repr so that kind labels (excluded from ValueType
        # equality) still distinguish Pointer[Int[32]] from Int[32].
        active: set[str] = set()

        def spell(item: Symbol | ValueType | MappedType) -> str:
            if isinstance(item, Symbol):
                if item.type is None:
                    raise ConstructError("Callable cannot have a variable type")
                concrete = item.type
            elif isinstance(item, (ValueType, MappedType)):
                concrete = item
            else:
                raise ConstructError("Type representation needs a Model type or Symbol")
            identity = repr(concrete)
            if identity in active:
                raise ConstructError("Cyclic type spelling for a Model type")
            if isinstance(concrete, MappedType):
                key = concrete.key
            elif concrete.label is not None:
                key = f"kind:{concrete.label.name}"
            else:
                key = concrete.kind.value
            spelling = self._types.get(key)
            if spelling is None:
                raise ConstructError(
                    f"No {self.target!r} type representation for {key!r}"
                )
            if _used is not None:
                _used.add(key)
            active.add(identity)
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
                active.remove(identity)

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

    def _collect_type_requirements(self, model_type: ValueType | MappedType) -> None:
        """Gather type-spelling requirements while composing.

        Requirements render before the types that need them, so they are
        collected here. Spelling errors still surface at final rendering,
        keeping the existing order of reported failures.
        """
        try:
            requirements = self.context.registry.type_requirements(model_type)
        except ConstructError:
            return
        self.context.headers.update(requirements)

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
            self._collect_type_requirements(part.type)
            return TypeName(part.type)
        if isinstance(part, (ValueType, MappedType)):
            self._collect_type_requirements(part)
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
