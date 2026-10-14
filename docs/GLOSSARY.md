# pyinto Glossary

Shared vocabulary for Model normalization, Target Implementations, and composition. These terms are distinct from any particular implementation class or API spelling.

## Model

A Target-independent description of structures, features, operations, and semantic contracts to be realized. It is the abstraction layer built from provider-owned Constructs and contracts, and contains no Target-specific implementation. A consolidated API such as `Model.language.Branch` is not implemented.

## Construct

A type or instance representing a concrete Model element, with structure and named children. It does not generate Target-specific code. The generic base remains `Construct`. Constructs that represent language structures are called **Language Constructs**.

## Interface

A semantic unit connecting an executable Python Source API (including language syntax) to its Model-side Constructs and semantic contracts. It is not restricted to the Java notion of an interface, and may entail concrete Python behavior. Python executes builtins itself; additional libraries are implemented by existing Python libraries or their providers. **Interface Mapping** bridges the Python and Model representations; separate Realizations implement them on a Target. Today `pyinto.interfaces.language` and `builtins` simply export existing Constructs, not a general Interface registrar or Python implementation wrapper.

## Realization

A Target-specific implementation rule for Construct structures and semantic contracts, formerly called a Binding. It may provide Templates, dynamic plans, requirements, or structure-ordered Visitors. It is neither the final emitted source string nor an automatic proof of semantic preservation.

## Template

A composition structure holding fixed text, Slots, and placement relationships from a Realization, prior to final string rendering. Not necessarily finished code.

## Slot

A location in a Template that connects a Realization for another Model element; it can recursively trigger more Realizations, not merely substitute a string.

## Frontend

Mechanism that reads Python syntax, explicit types, references, and registered external APIs and normalizes them into Constructs. `PythonFrontend` is an implementation inside the Host. It does not choose Target syntax or realization strategy.

## Composer

Resolves Realizations and mechanically connects child Realizations into Template Slots recursively without guessing Target semantics.

## Renderer

Converts an assembled Template/Slot Layout into final source text without inferring missing meaning or unsupported Realizations.

## Target

A language, environment, or format to which artifacts are realized. Languages such as C and Rust are primary uses, but the Model does not depend on a Target. A Target is not the same as a concrete implementation package.

## Target Implementation

The implementation unit providing Realizations for a given Target, encompassing language-structure and abstract-Interface implementations. Individual rules are Realizations; the Target owns generation state and artifacts. This term does not prescribe a new common base class. Historically related to the names "Target Pack" and "Target Cartridge".

## Contract

A semantic requirement on Model operations, types, constraints, evaluation order, and cleanup/exit behavior. Construct providers declare requirements through Admission; the Target declares `supports`. A successful match is not a proof of preserved behavior. These contracts are distinct from development-only Shikumi-Contrace test contracts.

## Deterministic derivation

Building an artifact from explicit structures, references, contracts, and selected Realizations. It neither guesses runtime results nor proves the output necessarily behaves correctly on a Target.

## pyinto

The project name and Python distribution name for the Host, which supplies Python source normalization and conversion entry points. Earlier public names included `henkan` (and before that `Skeleton`); `taiou` was not adopted.

## Host

The `pyinto` repository/distribution unit, combining Surface, common Foundation, language interfaces, and Python Source Adapter. It does not include a concrete Target Implementation.

## Surface

Logical role of user-facing conversion entry points such as `convert()` and `realize()`; not a synonym for the whole Host. There is no CLI yet.

## Foundation

Logical role for common Construct, Admission, and Realization registration, composition, and rendering. Not a separately published package.

## Language Construct

A Construct representing normalized language structure, such as `Branch`, `While`, or `Arithmetic`. Currently part of the Host. The generic `Construct` base keeps its name.

## Python Source Adapter

Logical Host role for normalizing Python syntax, types, and names to the Model, implemented using `PythonFrontend` and related classes. This does not imply pluggable multiple Frontends exist.

## Interface Mapping

Definitions and machinery mapping registered external Python functions, classes, or methods to Constructs. Existing API: `InterfaceMappingRegistry` and related declarations. This is not the definition of an abstract Interface itself. The names `PortType`, `PORT_OBJECT`, and `port:` persist in Model internals for type identity.
