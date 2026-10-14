# pyinto

A framework for transforming Python source code into outputs of arbitrary formats (code in other languages, binaries, or anything else) and content.

- However, not all Python code can be used as source input.

## Still in Alpha, so breaking changes will occur.

For the current implementation status, see [STATUS](STATUS.md).

## Installation

Python 3.11 or later is required.

```bash
pip install pyinto
```

## Conceptual model

pyinto treats the structure and semantics extracted from Python code as a Model that is independent of any particular output format.

A Target Implementation produces artifacts based on this Model.

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

- Python syntax that the Host does not model is rejected when it is given to the Host.
- Even if the Host accepts the input, it is also rejected if the Target Implementation does not support it.
- In other words, this framework cannot use arbitrary Python code as conversion input. It can use only **restricted Python code** that the Host can model and that the Target Implementation supports.

## Main use cases and other possible applications

### Conversion into source files in other languages

This was the original motivation for creating pyinto. By creating a Target Implementation, it should be possible to convert code into any programming language. However, at present, there is no completed Target Implementation that performs conversion into a specific language.

#### The combination of Model and Realization also applies to libraries

When implementing basic conversion into a particular language, it is not necessary to implement support for all the libraries used by that language at the same time.

The Host does not provide Models even for the Python standard library.

Library interfaces can be modeled as needed, and corresponding Realizations must then be created.

Since a modeled library interface does not have to depend on a particular language, it may be possible to develop reusable assets based on *general* procedures rather than on a specific language. This is still at the experimental stage, however, and has yet to be demonstrated clearly.

### Generating artifacts from Python syntax and module execution results

Rather than seeing restricted Python code as a disadvantage, it can be used positively as a **mini-language**. Because it restricts Python instead of extending its syntax, the source code remains executable. These properties can be combined to produce final artifacts: the static information obtained through AST analysis and the dynamic state obtained by executing the code.

A function defined with the name `__pyinto_runtime__` has a special meaning within the module and is excluded from AST analysis. Its return value is supplied by the Host when the Target Implementation produces the final artifact, allowing that information to be reflected in the artifact.

### Collaborative development with LLMs

This approach of keeping the Host small and defining everything else outside it assumes implementation with the assistance of LLMs.

For how to implement a Target Implementation, see the [Target Implementation Guide](docs/target_implementation/INDEX.md).

## Documentation

For details, see the following documents.

| Document | Description |
|---|---|
| [STATUS](STATUS.md) | Current development status, implemented features, and limitations |
| [Target Implementation Guide](docs/target_implementation/INDEX.md) | Guidelines for developing Target Implementations |
| [Specification](docs/specification/INDEX.md) | pyinto specifications and behavioral contracts |
| [Glossary](docs/GLOSSARY.md) | Definitions of terms used in the project |
| [Changelog](CHANGELOG.md) | Development history and changes |

The Target Implementation Guide is organized particularly with LLM-assisted implementation work in mind.

Official documentation is currently maintained in Japanese.

## License

For license information, see the repository's [LICENSE](LICENSE) file.
