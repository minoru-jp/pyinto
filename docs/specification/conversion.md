# Conversion API

Initial public Python API. CLI and automatic Target/Cartridge discovery are not implemented.

## CVT_001

**Source conversion entry point · MUST.** `pyinto.convert(source, *, realizations, interface_mappings=None, admission=None)` accepts Python source text, normalizes it with `PythonFrontend`, then realizes the Model using the specified `RealizationRegistry` and a Target-owned Artifact Session. It returns the object submitted by `Session.finish()` without coercion. The Host neither infers a Target nor implicitly selects C. An explicit `admission` takes precedence; otherwise, registrations from an explicit `InterfaceMappingRegistry` are used where applicable.

Related: [CST_006](construct.md#cst_006).

## CVT_002

**Realization of an existing Model · MUST.** `pyinto.realize(program, *, realizations, admission=None)` realizes an existing Construct Tree without modifying it and returns an artifact of any Target-defined type. The same Program may be realized repeatedly with different Registries. With no explicit `admission`, only the Language Construct registry is used. External Constructs are rejected unless provider registrations are supplied explicitly.

Related: [CST_001](construct.md#cst_001).

## CVT_003

**Explicit dependencies and failures · MUST.** Passing something other than a `RealizationRegistry` as `realizations`, passing a non-Construct to `realize`, or passing an invalid `admission` produces `TypeError`. Unknown Constructs and unsupported Target operations fail with `ConstructError`. Supply external Interface Mappings explicitly using `interface_mappings=`. An unregistered Construct is rejected even when a Target has a recipe, and baseline Language Construct contracts cannot be overridden. Automatic Target Implementation or Interface discovery is not available.

## CVT_004

**Target-owned artifact and submission lifecycle · MUST.** The return type of `realize` and `convert` is `object`. The Host does not stringify, save files, or concatenate final text. It returns the result of `finish()` on a fresh Session created for the request. In Composition, the existing Layout is passed through `accept_composition(layout, context)` for Target-selected final rendering. In Structural, the Host calls `visit(node, ctx)` for traversed Constructs before asking for submission. When processing fails, `finish()` is not invoked and state is not reused for later requests.
