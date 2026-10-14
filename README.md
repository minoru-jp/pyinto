# pyinto

**pyinto is a Host library that normalizes typed Python code into a Target-independent Model and lets Target Implementations realize that Model as a wide range of artifacts.**

## ⚠️ Development status

pyinto is an **experimental Alpha-stage library**. Its APIs, Model, specifications, and design are subject to change. **Breaking changes may be introduced without advance notice or a migration period.** Compatibility between releases is not guaranteed. Use caution before deploying it to production or adopting it as a long-term dependency. See [STATUS](STATUS.md) for the current implementation status.

## Installation

Requires Python 3.11 or later.

```bash
pip install pyinto
```

## Conceptual model

pyinto models the structure and semantics obtained from Python independently of any particular output format. A Target Implementation uses that Model to produce an artifact.

```text
              Typed Python Source
                       │
                       ▼
              ┌─────────────────┐
              │   pyinto Host   │
              │                 │
              │    Frontend     │
              │       ↓         │
              │ Construct Model │
              │       ↓         │
              │    Admission    │
              │       ↓         │
              │    Dispatch     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │     Target      │
              │ Implementation  │
              │                 │
              │  Realizations   │
              │       ↓         │
              │ Artifact State  │
              │       ↓         │
              │  Finalization   │
              └────────┬────────┘
                       │
                       ▼
                    Artifact
```

**The Host constructs the Model and controls Realization dispatch. The Target Implementation constructs and submits the artifact.**

## Host responsibilities

The pyinto Host provides:

- **Frontend:** statically analyzes typed Python and normalizes it into the Model.
- **Construct Model:** represents program structure and meaning without tying them to a Target.
- **Admission:** checks contracts governing the Model and its Realizations.
- **Realization Dispatch:** invokes Realizers according to the Model structure and the declared dispatch mode.

The Host does not prescribe an artifact format or internal representation.

## Target Implementation responsibilities

A Target Implementation consumes Model information supplied by the Host. It defines Realizations, manages generation state, constructs its artifacts, and submits the final result.

Translation into other programming languages remains a primary use case, **but there is no Host-imposed restriction on the form of the artifact**. A Target may produce structured data, diagrams, documentation, analysis reports, images, executable files or other **binary files**. An artifact need not even be a file: it may be any object the Target chooses to return.

A Target also chooses whether it aims to **preserve** execution semantics or **project** selected information from the Model.

## Realization dispatch modes

**Composition** recursively connects Realizations via Template/Slot references. It is particularly useful for constructing structured text, including source code. **Structural** walks the Model structure and invokes matching Realizers, making it suitable for information extraction, structural analysis, diagrams, and structured data. In both modes, the Target Implementation owns the final artifact.

## Target Implementations

**pyinto distributes the Host library only. It does not ship any concrete Target Implementation.** Installing pyinto alone therefore does not enable conversion into C or any other programming language. You must provide a suitable Target Implementation separately.

Target authors can use pyinto's public Model, Realization, Admission, and related interfaces. The repository includes development-only Python and C reference Realizers under `tests/support/`; these are test assets, not part of the pyinto distribution.

Start with the **[Target Implementation Guide](docs/target_implementation/INDEX.md)** for design choices, declarations, Constructs and variants, semantic contracts, artifact generation, and verification. The guide is structured with LLM-assisted implementation work in mind.

## Documentation

| Document | Purpose |
| --- | --- |
| [STATUS](STATUS.md) | Current development state, supported features, and limitations |
| [Target Implementation Guide](docs/target_implementation/INDEX.md) | Implementing Target Implementations |
| [Specification](docs/specification/INDEX.md) | Normative behavior and contracts |
| [Glossary](docs/GLOSSARY.md) | Project terminology |
| [Changelog](CHANGELOG.md) | Development history |

Japanese canonical sources and generated Japanese documents are maintained in `devdocs/`. English documents here are published derivatives, not independent normative sources. [Translation coverage](docs/TRANSLATION_STATUS.md) identifies which long-form specifications are currently abridged; consult the Japanese canonical documents for complete conditions.

## License

See [LICENSE](LICENSE).
