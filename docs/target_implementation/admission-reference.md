# Admission Contract Reference

A Target's `pack_semantics` declares **the semantic guarantee claimed by the artifact**. It is not inferred from file extensions or from `pack_dispatch`. The existing normative obligations appear in the [Composition Specification](../specification/composition.md). This reference explains how Target authors should apply them without false claims.

## ADM_001

**Title:** Model admission and Target admission are distinct. **Level: MUST.**

The Host runs `admission.check_tree(root)` before choosing Realizers or creating a Session. A concrete Construct type not registered with its provider's Admission is rejected even if `pack_unhandled="traverse"`. An extended Admission passed to `realize(..., admission=...)` cannot replace or remove the baseline `LANGUAGE_ADMISSION` (`require_baseline`). An explicitly supplied Interface Mapping may provide Admission registrations to `convert(..., interface_mappings=...)`.

Related: [CMP_018](../specification/composition.md#cmp_018).

## ADM_002

**Title:** Required contracts for preservation. **Level: MUST.**

In Preservation (the default), obtain the required contracts from `admission.required_contracts(node)` and reject with `ConstructError` if **the set difference** from the chosen Realization's `supports` is nonempty. If a Target cannot preserve required meaning, reject it; do not fabricate `supports` declarations. `supports` is a self-declaration, not proof of preserved runtime behavior. Verify generated code independently.

Related: [CMP_013](../specification/composition.md#cmp_013), [CMP_017](../specification/composition.md#cmp_017).

## ADM_003

**Title:** Scope of projection. **Level: MUST.**

Projection need not reproduce execution semantics in the artifact, so the `required_contracts - supports` comparison is not required for individual Realizations. This relaxation does **not** permit unknown Model types or inaccurate reporting. State exactly what information is extracted and test it. **A general automatic contract system for proving the correctness of projections is not yet implemented.**

## ADM_004

**Title:** Two layers: unhandled Realization vs. Admission. **Level: MUST.**

`pack_unhandled="error"` rejects nodes without matching Realizations. `"traverse"` is available only for Structural + Projection. It skips the unmatched node's Visitor but continues into Constructs under `parts()`. Other variants of an otherwise handled type may be skipped when explicit variant selection is valid. Never claim to implement unhandled Constructs or variants.

## ADM_005

**Title:** Verify contract names independently of variants. **Level: MUST.**

Do not infer namespaced contract keys from code. Inspect the Model's Admission Rule, `required_contracts(node)`, the related Specification, and behavior tests. Variant coverage is handled through `Construct.variant_domain()` registration checks and an explicit `variant @= "*"`; this does not replace semantic-contract matching.

## CATALOG

This catalog is generated from rules in `LANGUAGE_ADMISSION.declarations`. The `.*` suffix on a provider-side `contracts` entry describes an **allowed contract namespace family**; it does not authorize wildcards in a Realizer's `supports`. The *actual* contracts for a given node must be queried using `LANGUAGE_ADMISSION.required_contracts(node)`. A listed contract is not necessarily required for every instance.

| Rule | Construct(s) | Contract keys / namespace families |
| --- | --- | --- |
| augmented_rebinding | AugAssign | `assignment.augmented.read_before_rhs`, `assignment.augmented.rebind`, `assignment.augmented.target_once` |
| bound_arguments | FunctionCall, InstanceCreation, ClassMethodCall, ClassReceiverCreation, MethodCall | `call.arguments.bound`, `call.arguments.left_to_right`, `call.arguments.reordered`, `call.defaults.omitted` |
| class_receiver | ClassMethodCall, ClassReceiverCreation | `class_receiver.runtime_identity` |
| collection_membership | Membership | `membership.dict.key_hash_equality`, `membership.list.identity_or_equality`, `membership.negated`, `membership.operands.left_to_right` |
| fixed_tuple_unpack | UnpackAssign | `assignment.unpack.rhs_once_before_writes`, `assignment.unpack.targets_left_to_right` |
| for_control_flow | For | `loop.for.break_continue`, `loop.for.normal_completion_else` |
| for_iteration_binding | For | `iteration.binding.introduced` |
| formatted_string_order | FormattedString | `format.string.fragments_once_in_order` |
| integer_operator_semantics | Arithmetic, IntegerUnary, AugAssign | `integer.bitwise.unbounded`, `integer.shift.python_counts` |
| integer_true_division | IntegerTrueDivision | `integer.true_division.python_float` |
| intrinsic_call_semantics | IntrinsicCall | `call.arguments.left_to_right`, `intrinsic.*` |
| iteration_binding | IterationEntry | `iteration.binding.introduced` |
| iteration_source | For, IterationEntry | `iteration.source.*` |
| method_dispatch | MethodCall | `method.dispatch.super`, `method.dispatch.virtual`, `method.lookup.lexical_base` |
| ordered_comparison_chain | ComparisonChain | `comparison.chain.left_to_right`, `comparison.chain.operands_once`, `comparison.chain.short_circuit` |
| ordered_operands | Arithmetic, IntegerTrueDivision, Comparison, FloatingArithmetic, FloatingComparison, StringConcat, StringRepeat, StringComparison, StringContains, StringElement | `evaluation.operands.left_to_right` |
| print_values_semantics | PrintValues | `output.print.evaluate_before_write`, `output.print.space_join_newline` |
| sequence_slice | SliceValue | `slice.evaluate_source_bounds_once_in_order`, `slice.list.shallow_outer_copy`, `slice.python_indices_and_zero_step`, `slice.string.unicode_codepoints` |
| string_membership_semantics | StringContains | `membership.negated`, `membership.string.unicode_substring` |
| unbound_call_order | Call, FunctionValueCall | `call.arguments.left_to_right`, `function_value.callee_before_arguments` |
| variadic_function_binding | FunctionDefinition, FunctionCall | `call.variadic.tuple_binding`, `function.variadic.tuple_binding` |
| with_context_management | With | `context.with.enter_exit_exception` |

## MODES

Dispatch (Composition/Structural) is independent of this matrix. The Host does not automatically attach semantic-mode metadata to artifacts.

| Mode | Required checks | Target author's responsibility |
| --- | --- | --- |
| `preservation` (default) | Model admission + `supports` comparison | Test preserved behavior and reject unsupported cases. |
| `projection` | Model admission only; no execution-semantic `supports` comparison | Test the stated extraction scope and accuracy; reject incorrect projections. |
