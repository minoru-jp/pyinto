# pyinto

A framework for transforming Python source code into outputs of arbitrary formats (code in other languages, binaries, or anything else) and content.

- However, not all Python code can be used as source input.
- It is not a tool for porting existing, working Python programs to other languages. Its purpose is conversion, and source is treated as a description that passes information to Targets.
- Except when `__pyinto_runtime__` is used, source is not expected to run as Python.

## Still in Alpha, so breaking changes will occur.

For the current implementation status, see [STATUS](https://github.com/minoru-jp/pyinto/blob/main/STATUS.md).

## Installation

Python 3.11 or later is required.

```bash
pip install pyinto
```

## Conceptual model

A conversion with pyinto proceeds as follows.

```text
Source ──(Host)──▶ Model ──(Realizer)──▶ Artifact
```

- **Source**: the Python text written for pyinto.
- **Host**: pyinto itself. It reads the Source, builds the Model, and calls the Realizer.
- **Model**: the tree of Constructs (the kinds of parts) built from one Source. It does not depend on any particular output format.
- **Target**: the output language or format (C, Rust, JSON, and so on).
- **Realizer**: the implementation for one Target. Each rule inside it is a Realization, and its entry declaration is the Target Pack.
- **Artifact**: what the Realizer produces.

Each stage contains the following.

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
              │    Realizer     │
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
- Even if the Host accepts the input, it is also rejected if the Realizer does not support it.
- In other words, this framework cannot use arbitrary Python code as conversion input. It can use only **restricted Python code** that the Host can model and that the Realizer supports.

## Main use cases and other possible applications

### Conversion into source files in other languages

This was the original motivation for creating pyinto. By creating a Realizer, it should be possible to convert code into any programming language. However, at present, there is no completed Realizer that performs conversion into a specific language.

#### The combination of Model and Realization also applies to libraries

When implementing basic conversion into a particular language, it is not necessary to implement support for all the libraries used by that language at the same time.

The Host does not provide Models even for the Python standard library.

Library interfaces can be modeled as needed, and corresponding Realizations must then be created.

Since a modeled library interface does not have to depend on a particular language, it may be possible to develop reusable assets based on *general* procedures rather than on a specific language. This is still at the experimental stage, however, and has yet to be demonstrated clearly.

### Generating artifacts from Python syntax and module execution results

Rather than seeing restricted Python code as a disadvantage, it can be used positively as a **mini-language**. Only when an execution Target (`purpose = "execution"`) is selected does the Host execute the source as ordinary Python. The static information obtained through AST analysis and the dynamic state obtained by that execution are combined to produce final artifacts.

A function defined with the name `__pyinto_runtime__` has a special meaning within the module and is excluded from AST analysis. Its return value is supplied by the Host when the Realizer produces the final artifact, allowing that information to be reflected in the artifact. Because such a source is executed, a source that defines `__pyinto_runtime__` cannot use `pyinto.kinds`, the vocabulary for conversion.

### Kind vocabulary (`pyinto.kinds`)

To pass type, memory, and declaration information to Targets, `pyinto.kinds` provides vocabulary. It is split into the surfaces `datatypes` (what a value is), `memory` (where a value lives, who owns it, and when it is released), and `declarations` (the character of a declaration such as a class), each with two tiers.

- `general`: general vocabulary that every language Target interprets. Python's built-in types (`int`, `float`, and so on) together with `Wide[int]`, `Unsigned[int]`, `Size`, `Owned[T]`, `Memory.release`, and so on. Source written only with these can be converted by any Target that supports the general vocabulary.
- `detailed`: choices close to particular languages, such as `Int[32]`, `Pointer[T]`, `Null`, and `@Interface`. A Target that does not support them may reject them.

```python
from pyinto.kinds.datatypes.general import Unsigned, Wide
from pyinto.kinds.memory.general import Memory, Owned

total: Unsigned[Wide[int]] = 0
cell: Owned[int] = Memory.new(int, 7)
Memory.release(cell)
```

The Host defines no meaning for these words; it only records them in the Model as labels and passes them to Targets. How to write them concretely is chosen by the Target.

### Collaborative development with LLMs

This approach of keeping the Host small and defining everything else outside it assumes implementation with the assistance of LLMs.

For how to implement a Realizer, see the [Realizer Guide](https://github.com/minoru-jp/pyinto/blob/main/docs/realizer/INDEX.md).

## Documentation

For details, see the following documents.

| Document | Description |
|---|---|
| [STATUS](https://github.com/minoru-jp/pyinto/blob/main/STATUS.md) | Current development status, implemented features, and limitations |
| [Realizer Guide](https://github.com/minoru-jp/pyinto/blob/main/docs/realizer/INDEX.md) | Guidelines for developing Realizers |
| [Specification](https://github.com/minoru-jp/pyinto/blob/main/docs/specification/INDEX.md) | pyinto specifications and behavioral contracts |
| [Glossary](https://github.com/minoru-jp/pyinto/blob/main/docs/GLOSSARY.md) | Definitions of terms used in the project |
| [Changelog](https://github.com/minoru-jp/pyinto/blob/main/CHANGELOG.md) | Development history and changes |

The Realizer Guide is organized particularly with LLM-assisted implementation work in mind.

Official documentation is currently maintained in Japanese.

## License

For license information, see the repository's [LICENSE](https://github.com/minoru-jp/pyinto/blob/main/LICENSE) file.
