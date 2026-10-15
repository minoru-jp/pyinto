# Target Verification Guide

**Definition of done:** tests must verify public-API Pack registration, acceptance of intended Models, rejection of unsupported Models, artifact type/content, evidence for semantic claims, and an independent Session for each request. Do not describe untested behavior as supported.

The executable examples in the [Implementation Guide](implementation-guide.md) are checked by pytest. `tests/support/c_realizer/` is a regression/reference implementation, not a published Target Pack.

## Implementation and documentation checks

Run the following sequence:

1. Test `RealizationRegistry.from_pack(Pack)`, including cases that must fail declaration validation.
2. Feed `convert`/`realize` both minimal and multi-node inputs; compare artifacts to concrete expected values.
3. Test explicit variants, precedence over `*`, missing declarations, unknown variants, and the unhandled policy.
4. For Preservation, inspect required contracts; independently test rejection on missing `supports` **and** preserved execution behavior.
5. For Projection, distinguish skipping an unregistered Realization from rejecting an unregistered Model type.
6. Run two different inputs using the same Registry and verify that Session state never leaks between requests.
7. Confirm that the Host neither coerces artifacts to strings nor mutates source Constructs.

Run documentation examples with `python -m pytest tests/test_target_documentation.py -q` at repository root. Check generated Japanese canonical documents with `python scripts/docs.py check`. Host validation uses Ruff, basedpyright, and the existing pytest + Contrace suite.

## Acceptance test matrix

Not every item applies to every Target. Mark unsupported features as out of scope instead of assuming they work.

| Subject | Positive check | Rejection / caveat |
| --- | --- | --- |
| Pack | Can read Target identity and declared modes | Reject invalid dispatch/semantics/unhandled choices and duplicate entries |
| Variant | Exact match overrides `*` | Reject known invalid variants and ambiguous omissions |
| Structural | Preorder visits follow `parts()` with correct `ctx.path` | Reject non-`None` returns from `visit` |
| Composition | Recursively resolve Template Slots and pass a Layout | Reject missing Slots, invalid Templates, and unhandled Realizations |
| Projection + traverse | Skip unmatched Realizations while visiting children | Must not skip unregistered Model types in Admission |
| Preservation | `supports` satisfies required contracts | Reject insufficiency before rendering/visiting |
| Session | Fresh state for every request | No artifact leakage across invocations |
| Artifact | Preserve Target-specific type and content | Host must not stringify or implicitly convert to code |

## Invalid conclusions that must not count as completion

- `semantics="projection"` does not automatically prove extraction correctness.
- `supports` does not prove behavioral preservation. Test generated programs separately.
- Composition does not automatically emit children omitted by a Template.
- Structural invokes a single preorder Visitor; there is currently no child-exit hook.
- A capability of the C/Python reference Target is not necessarily a universal Target capability.
- A successful documentation generation check does not guarantee runtime semantic correctness.
