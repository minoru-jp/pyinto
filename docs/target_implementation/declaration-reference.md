# Realization Declaration Reference

These Shikumi declarations are provided by `pyinto.realizations.regulation`. A Pack is identified by the declarations on the class passed explicitly to `RealizationRegistry.from_pack(Pack)`, **not by its class name**. Read the [Implementation Guide](implementation-guide.md) first.

## API_001

The Target identifier. No Target lookup is performed automatically by name.

name: `pack_target`

kind: Value

input: Nonempty `str`, e.g. `pack_target @= 'outline'`

## API_002

An explicit enumeration of Realizations and type-spelling classes to register. Rules are not inferred from an empty Pack.

name: `pack_entries`

kind: Value

input: `tuple[type, ...]`, e.g. `pack_entries @= (MyRealizer,)`

## API_003

Select a single dispatch mode for the entire Pack; modes cannot be mixed within a Pack.

name: `pack_dispatch`

kind: Value

input: `'composition'` (default) or `'structural'`

## API_004

Declare whether the artifact preserves execution semantics or only projects information. No semantic metadata is automatically inserted into the artifact.

name: `pack_semantics`

kind: Value

input: `'preservation'` (default) or `'projection'`

## API_005

Control unmatched Constructs. With `traverse`, the visitor for the unmatched node is skipped, but traversal continues to its children.

name: `pack_unhandled`

kind: Value

input: `'error'` (default) or `'traverse'`

detail: `'traverse'` is allowed only with Structural + Projection.

## API_006

A zero-argument factory that creates a new Session for each request. Mandatory for Structural dispatch.

name: `pack_session`

kind: Value

input: `Callable[[], object]`, e.g. `pack_session @= MySession`

detail: May be omitted for Composition; the default is `TextArtifactSession`.

## API_007

Identify a **public element object**, not a string. Accepts Constructs, supported direct builtin Calls, and Model type-spelling elements.

name: `@realizes(element)`

kind: Operation

input: e.g. `@realizes(lang.FunctionDefinition)`

detail: Mutually exclusive with naming declarations. Selection uses exact Construct types, not an automatic subclass match.

## API_008

Select a Construct variant. Omission means `default`, **not** every variant.

name: `variant`

kind: Value

input: An existing variant or `'*'`, e.g. `variant @= 'integer'`

detail: `'*'` also matches future variants; exact variants take precedence. Duplicate keys are rejected. Unknown names are rejected when the variant domain is known. Structural + Projection rejects omitted variants for multi-variant or open-domain Constructs.

## API_009

Static Template for Composition; a Slot's first occurrence triggers child composition.

name: `template`

kind: Value

input: e.g. `template @= '${body}'`

detail: Must not be combined with `render` or `visit` on the same Realization.

## API_010

Dynamic Layout selection for Composition. A `TemplatePlan` may supply additional Slots.

name: `render`

kind: Operation

input: `Callable[[Construct, EmitContext], str | Text | TemplatePlan]`

detail: Must not be combined with `template` or `visit` on the same Realization.

## API_011

Visitor used by Structural traversal. Update the Target's `ctx.session` rather than returning an artifact.

name: `visit`

kind: Operation

input: `Callable[[Construct, EmitContext], None]`

output: Only `None`; other return values are rejected.

detail: Must not be combined with `template` or `render` on the same Realization.

## API_012

In Preservation, declare which Model-required Admission contracts are supported by the Realization.

name: `supports`

kind: Value

input: Unique, namespaced contract names in `tuple[str, ...]`, e.g. `('evaluation.operands.left_to_right',)`

detail: Projection skips the execution-semantic `required_contracts` comparison, but still validates the Model registration.

## API_013

Additional Composition declarations, illustrated by the C/Python reference Realizers.

name: `requires / separators / accepts`

kind: Value

detail: `requires @= 'name'` registers a required header name; `separators @= {slot: sep}` separates a Joined Slot; `accepts @= (kind_name, ...)` limits argument kinds for supported direct builtin Calls.

## API_014

Define textual Model type spelling and Target-specific naming rules.

name: `type_name / @naming / reserved / forbidden_prefixes / requirement_line`

kind: Value

detail: `type_name` is a string or callable type spelling; `@naming` is mutually exclusive with `@realizes`. `reserved` and `forbidden_prefixes` validate names. `requirement_line` permits only the `${name}` Slot.

## API_015

Load and validate an explicitly selected Pack. Invalid or duplicate declarations fail with `ValueError`.

name: `RealizationRegistry.from_pack(Pack)`

kind: Operation

input: The explicitly chosen Pack class

output: `RealizationRegistry`

## API_016

Normalize Python source into a Model and send it to a Target. The `realizations` argument is mandatory.

name: `pyinto.convert(source, *, realizations, interface_mappings=None, intrinsics=None, admission=None)`

kind: Operation

output: Any object returned by `Session.finish()`

detail: Unregistered Models are checked before invoking a Realizer or Session.

## API_017

Realize an already-constructed Model.

name: `pyinto.realize(program, *, realizations, admission=None)`

kind: Operation

output: Any object returned by `Session.finish()`

## API_018

Context available during Realization. Do not mutate input Constructs.

name: `EmitContext`

kind: Type

output: `root / current / parent / ancestors / path / registry / admission / session`

detail: `path` starts at root and includes current. `fresh(stem)` makes an auxiliary name. `session` holds Target-owned state. `headers` contains Composition requirement names.

## API_019

Required final-submission method for every Session.

name: `Session.finish()`

kind: Operation

output: Artifact of any type; the Host neither interprets nor stringifies it.

detail: `RealizationHost` creates a Session per request.

## API_020

Session method invoked at the end of Composition dispatch.

name: `Session.accept_composition(layout, context)`

kind: Operation

input: The connected `Layout` and `EmitContext`

detail: `TextArtifactSession` stores the Layout and renders it to a string on `finish()`.

## API_021

Publish the variant domain: a finite `frozenset[str]` or `None` for an extensible/open domain.

name: `Construct.variant_domain()`

kind: Operation

output: `frozenset[str] | None`

detail: See the [Construct / Variant Reference](construct-reference.md) for the list of built-in Constructs.

## API_022

Declare the optional runtime information channel. This is independent of Dispatch and Semantics; legacy Packs that omit it ignore the hook.

name: `pack_runtime`

kind: Value

input: `'required' / 'forbidden' / 'optional' / 'ignored'` (default)

detail: `required`: hook required, execute and call `finish(R)`. `forbidden`: reject a present hook. `optional`: execute a present hook and call `finish(R)`, otherwise call `finish(RUNTIME_ABSENT)`. `ignored`: allow a present hook but never execute it; call `finish()`. `required` and `optional` need a custom Session; the default text Session does not accept a runtime argument.

## API_023

Combine static Model information and a runtime value at Session finalization. The Target owns the runtime return type and its semantic checks.

name: `__pyinto_runtime__() / RUNTIME_ABSENT / Session.finish(R)`

kind: Operation

input: Declare a synchronous zero-argument top-level function in trusted Python source. Import the public `RUNTIME_ABSENT` sentinel from `pyinto.realizations`.

output: For `required` and present `optional`, the returned object R; for absent `optional`, `RUNTIME_ABSENT`.

detail: Model-only `realize()` rejects `required` because it lacks source. Sessions for Targets not using runtime information keep their existing `finish()` contract.


## API_024

Target-defined schema for the runtime result's values and types. If omitted, the Host performs no schema validation of R.

name: `pack_runtime_schema`

kind: Value

input: `type | Callable[[object], bool]`, e.g. `pack_runtime_schema @= ResultType` or `pack_runtime_schema @= validate_result`

detail: Allowed only for `pack_runtime='required'` or `'optional'`. A plain class is checked only with `isinstance`. Parameterized generic expressions such as `list[int]` and union expressions are not accepted directly; express nested types or value constraints with a predicate.

detail: Predicates take one argument R and must return a genuine `bool`. A false result, an invalid return type, or a validation exception raises `RuntimeSchemaError` before `Session.finish()`. An absent optional hook bypasses schema checking; a returned `None` does not.
