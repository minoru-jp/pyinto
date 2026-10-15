# Conversion API

Initial public Python API. CLI and automatic Target/Cartridge discovery are not implemented.

## CVT_001

**Source conversion entry point · MUST.** `pyinto.convert(source, *, realizations, interface_mappings=None, admission=None)` accepts Python source text, normalizes it with `PythonFrontend`, then realizes the Model using the specified `RealizationRegistry` and a Target-owned Artifact Session. It returns the object submitted by `Session.finish()` without coercion. The Host neither infers a Target nor implicitly selects C. An explicit `admission` takes precedence; otherwise, registrations from an explicit `InterfaceMappingRegistry` are used where applicable.

Related: [CST_006](construct.md#cst_006).

## CVT_002

**Realization of an existing Model · MUST.** `pyinto.realize(program, *, realizations, admission=None)` realizes an existing Construct Tree without modifying it and returns an artifact of any Target-defined type. The same Program may be realized repeatedly with different Registries. With no explicit `admission`, only the Language Construct registry is used. External Constructs are rejected unless provider registrations are supplied explicitly.

Related: [CST_001](construct.md#cst_001).

## CVT_003

**Explicit dependencies and failures · MUST.** Passing something other than a `RealizationRegistry` as `realizations`, passing a non-Construct to `realize`, or passing an invalid `admission` produces `TypeError`. Unknown Constructs and unsupported Target operations fail with `ConstructError`. Supply external Interface Mappings explicitly using `interface_mappings=`. An unregistered Construct is rejected even when a Target has a recipe, and baseline Language Construct contracts cannot be overridden. Automatic Realizer or Interface discovery is not available.

## CVT_004

**Target-owned artifact and submission lifecycle · MUST.** The return type of `realize` and `convert` is `object`. The Host does not stringify, save files, or concatenate final text. It returns the result of `finish()` on a fresh Session that the Realizer creates for the request. In Composition, the existing Layout is passed through `accept_composition(layout, context)` for Target-selected final rendering. In Structural, the Host calls `visit(node, ctx)` for traversed Constructs before asking for submission. When processing fails, `finish()` is not invoked and state is not reused for later requests.

## CVT_005

**Runtime presence contract · MUST.** `convert()` identifies a top-level, synchronous, undecorated, zero-argument `def __pyinto_runtime__():` in the source AST and excludes it from the normal Frontend Model. `runtime` accepts `required`, `forbidden`, `optional`, or `ignored` (the default). `required` rejects missing hooks; `forbidden` rejects present hooks; `optional` executes a present hook but passes `RUNTIME_ABSENT` when it is missing; `ignored` accepts but never executes the hook and continues to call `finish()` without arguments. `realize()` has no source: it rejects `required` and passes `RUNTIME_ABSENT` to `optional`. Runtime policy is independent of Dispatch and Semantics.

title: Runtime hook presence and Target policy

level: MUST

## CVT_006

**Trusted execution and Session handoff · MUST.** For runtime-enabled Targets, after static Model checks and dispatch, the Host executes the **trusted Python source** once as Python and invokes `__pyinto_runtime__()` once. It passes its result R to `Session.finish(R)`. For an absent hook with `optional`, `finish(RUNTIME_ABSENT)` is called: this sentinel is distinct from a hook returning `None`. The Host does not normalize the hook body. The Target owns the meaning of R; if it declares `runtime_schema`, the Host validates R against that Target-defined value/type contract immediately before `finish(R)`. Without a schema declaration, no schema validation is performed. Execution exceptions propagate and never trigger an automatic static fallback. Since `convert()` takes source text rather than a module path, execution uses a temporary module namespace without a real file or package context, and unregisters it afterward. Top-level side effects may occur. **pyinto is not a sandbox. Only supply trusted source.**

title: Runtime execution trust boundary and Session handoff

level: MUST

## CVT_007

**Target-declared Runtime schema validation · MUST.** A Target Pack may declare `runtime_schema` as an ordinary Python type object or as `Callable[[object], bool]`, but only with `runtime='required'` or `'optional'`. If omitted, the Host does not validate R. After obtaining R and immediately before `Session.finish(R)`, the Host tests a type using only `isinstance(R, schema)`; parameterized generic expressions such as `list[int]` must instead be expressed as predicates. A predicate receives R and must return an actual `bool` (not merely a truthy value); only `True` is accepted. A false result, a non-boolean return value, or an exception in schema validation raises `RuntimeSchemaError` without calling `finish`, preserving the original exception as its cause where applicable. The validator does not transform R; the same object is forwarded. `RUNTIME_ABSENT` for a missing optional hook is not validated, whereas a hook returning `None` is validated. The Host does not invent a type system or interpret the Target's schema semantics.

title: Target-declared Runtime schema contract

level: MUST
