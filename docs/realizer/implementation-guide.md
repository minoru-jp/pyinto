# Realizer Guide

## Audience and prerequisites

This guide is for authors of independent Realizers using the **pyinto 0.2.0 Alpha Host**. The task is not to manipulate the Python AST directly. Instead, receive the Construct Model normalized by the Frontend through the Host's dispatch rules and return artifacts owned by the Target.

**Evidence priority:** public API signatures, [Declaration Reference](declaration-reference.md), [Construct / Variant Reference](construct-reference.md), [Admission Reference](admission-reference.md), and the [Specification](../specification/INDEX.md). The C/Python Realizers in `tests/support/` are reference implementations, not Host-distributed packages. Do **not** invent APIs, variants, contracts, or support for unknown features.

## Choose two independent axes and an unhandled policy

The **artifact type** (string, bytes, dictionary, or an object describing multiple files) belongs to the Target. Dispatch (how Realizations are invoked) and Semantics (what meaning is promised) are independent.

| Question | Choice | Reason |
| --- | --- | --- |
| Should Template Slots determine child dispatch? | `composition` | Uses existing deferred Layout composition. |
| Should every relevant Construct in `parts()` be observed? | `structural` | Depth-first preorder traversal, without a child-exit callback. |
| Must the artifact preserve execution semantics? | `preservation` | Default; checks each Realization's `supports`. |
| Does the artifact only extract structure or information? | `projection` | Execution-preservation `supports` checks are not required. |
| Should only selected Constructs be observed? | `structural` + `projection` + `traverse` | Skip unmatched visitors while continuing into their children. |

## Seven implementation steps

1. Specify the Python inputs, output format, and **meaning to preserve or project**.
2. Select `dispatch`, `semantics`, and `unhandled`. Defaults: `composition`, `preservation`, and `error`.
3. Register Realizations with `@realizes(lang.<Construct>)`. Supply `visit` for Structural, or `template`/`render` for Composition.
4. Define `session`. Sessions are **new per request** and expose `finish()`. Composition additionally requires `accept_composition(layout, context)`. `TextArtifactSession` is available for text artifacts.
5. Enumerate every registered class in `entries`, and validate it with `RealizationRegistry.from_pack(Pack)`.
6. Run `convert(source, realizations=registry)` or, for an existing Model, `realize(model, realizations=registry)`; receive the Target's artifact.
7. Follow the [Verification Guide](verification-guide.md). Test acceptance, rejection, and session isolation.

The Host owns **Realization invocation and Model Admission checks**. The Target Session owns artifact construction, ordering, and submission. `ctx.session` belongs to the Target; do not mutate Constructs in `ctx.path`.

## Runnable example: Structural + Projection

This minimal Target collects only function names and return types. Unregistered Realizations are traversed. **This code is covered by the documentation tests** and can be executed as written.

```python
from pyinto import convert
from pyinto.constructs import Construct
from pyinto.interfaces import language as lang
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes


class OutlineSession:
    def __init__(self):
        self.names = []

    def finish(self):
        return self.names


def collect(node: Construct, ctx: EmitContext) -> None:
    assert isinstance(node, lang.FunctionDefinition)
    assert isinstance(ctx.session, OutlineSession)
    ctx.session.names.append(
        (node.signature.name, node.signature.return_type.annotation())
    )


@realizes(lang.FunctionDefinition)
class FunctionOutline:
    visit = collect


class OutlinePack:
    target = "outline"
    dispatch = "structural"
    semantics = "projection"
    unhandled = "traverse"
    session = OutlineSession
    entries = (FunctionOutline,)


registry = RealizationRegistry.from_pack(OutlinePack)
source = "def add(a: int, b: int) -> int:\n    return a + b\n"
assert convert(source, realizations=registry) == [("add", "int")]
```

Here, `visit` returns nothing; it only updates session state. `traverse` skips unknown **Realizations**, not the Admission requirements of unknown **Construct types**.

## Runnable example: Composition + TextArtifactSession

Minimal Template/Slot composition. The returned value is produced by `TextArtifactSession.finish()`, chosen by the Target. The Host supplies an intermediate Layout, but does not automatically turn it into the final string artifact. **This only handles a single kind of integer value expression**; it is not a general semantics-preserving code translator.

```python
from pyinto import realize
from pyinto.constructs import Block, ExpressionStatement, Literal, Program
from pyinto.interfaces import language as lang
from pyinto.realizations import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import realizes


@realizes(lang.Program)
class ProgramRule:
    template = "${body}"


@realizes(lang.Block)
class BlockRule:
    template = "${children}"


@realizes(lang.ExpressionStatement)
class ExpressionRule:
    template = "${expression};"


def integer(node, ctx):
    assert isinstance(node, lang.Literal)
    return str(node.value)


@realizes(lang.Literal)
class IntegerRule:
    variant = "integer"
    render = integer


class TextPack:
    target = "demotext"
    dispatch = "composition"
    session = TextArtifactSession
    entries = (ProgramRule, BlockRule, ExpressionRule, IntegerRule)


registry = RealizationRegistry.from_pack(TextPack)
model = Program(Block((ExpressionStatement(Literal(2)),)))
assert realize(model, realizations=registry) == "2;\n"
```

A real preservation Target must reject unsupported variants/contracts and verify execution behavior with tests. `${...}` is a Template Slot, **not** a Python f-string. Children not referenced by a Template are not automatically realized in Composition.

## Things an LLM must not infer or fill in

- Omitting `variant` for `@realizes(lang.Literal)` means **`default`, not all variants**. Literal only supports `integer` and `string`, so such a declaration is rejected.
- Omitting `variant` for `Return` matches `default` alone. For `with_value`, declare it explicitly or select `variant = "*"`.
- Structural + Projection forbids omitting `variant` for multi-variant or open-domain Constructs. `"*"` catches future variants too, and an explicit declaration has precedence.
- `projection` is **not permission to report inaccurate information**. Describe what you extract and test its accuracy.
- `supports` is a **self-declared semantic guarantee**, not proof of preserved runtime behavior.
- `ctx.path` exposes ancestry/depth; Structural dispatch has no child-exit event.
- There is no discovery or automatic registration of a Pack, Registry, Realization, or Target by name.
