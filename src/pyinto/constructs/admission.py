from __future__ import annotations

import pyinto.constructs as model
from pyinto.admission import (
    AdmissionDeclaration,
    AdmissionRegistry,
    AdmissionRule,
)
from pyinto.constructs import (
    Arithmetic,
    AugAssign,
    Call,
    ClassMethodCall,
    ClassReceiverCreation,
    Comparison,
    ComparisonChain,
    Construct,
    FloatingArithmetic,
    FloatingComparison,
    For,
    FormattedString,
    FunctionCall,
    FunctionDefinition,
    FunctionValueCall,
    InstanceCreation,
    IntegerTrueDivision,
    IntegerUnary,
    IntrinsicCall,
    IterationEntry,
    Membership,
    MethodCall,
    MethodDispatch,
    PrintValues,
    SliceValue,
    StringComparison,
    StringConcat,
    StringContains,
    StringElement,
    StringRepeat,
    UnpackAssign,
    With,
)
from pyinto.constructs.control import iteration_source_shape


def _bound_arguments(node: Construct) -> frozenset[str]:
    assert isinstance(node, _BOUND_CALLS)
    required = {"call.arguments.bound"}
    # Model specifies the order in which explicit argument expressions are
    # evaluated, independently of how the Target spells a call. Positional
    # arguments also need this guarantee: C, for example, does not fix their
    # evaluation order. Never try to infer whether expressions have effects.
    supplied = tuple(
        index
        for index in node.argument_evaluation_order
        if index not in node.omitted_arguments
    )
    if len(supplied) >= 2:
        required.add("call.arguments.left_to_right")
    # Reordering for parameter binding is a distinct requirement; defaults
    # inserted by the Frontend are not source-evaluated expressions.
    if supplied != tuple(sorted(supplied)):
        required.add("call.arguments.reordered")
    if node.omitted_arguments:
        required.add("call.defaults.omitted")
    return frozenset(required)


def _variadic_binding(node: Construct) -> frozenset[str]:
    assert isinstance(node, (FunctionDefinition, FunctionCall))
    if node.signature.variadic_parameter is None:
        return frozenset()
    return frozenset(
        {"function.variadic.tuple_binding"}
        if isinstance(node, FunctionDefinition)
        else {"call.variadic.tuple_binding"}
    )


def _method_dispatch(node: Construct) -> frozenset[str]:
    assert isinstance(node, MethodCall)
    if node.dispatch is MethodDispatch.SUPER:
        return frozenset({"method.dispatch.super", "method.lookup.lexical_base"})
    return frozenset({"method.dispatch.virtual"})


def _class_receiver(node: Construct) -> frozenset[str]:
    assert isinstance(node, (ClassMethodCall, ClassReceiverCreation))
    return frozenset({"class_receiver.runtime_identity"})


def _for_control_flow(node: Construct) -> frozenset[str]:
    """Requirements of a for loop, regardless of the Target's loop syntax.

    All loops must honor break and continue in the current loop. An else block
    additionally requires normal completion to be distinguished from break.
    We do not inspect the body to predict reachability or side effects.
    """
    assert isinstance(node, For)
    requirements = {"loop.for.break_continue"}
    if node.else_body is not None:
        requirements.add("loop.for.normal_completion_else")
    return frozenset(requirements)


def _with_context_management(node: Construct) -> frozenset[str]:
    """Enter/exit order, unwinding and exception behavior belong to With."""
    assert isinstance(node, With)
    return frozenset({"context.with.enter_exit_exception"})


def _iteration_source(node: Construct) -> frozenset[str]:
    assert isinstance(node, (For, IterationEntry))
    source = node.entry.iterable if isinstance(node, For) else node.iterable
    shape, _ = iteration_source_shape(source)
    return frozenset({f"iteration.source.{shape}"})


def _iteration_binding(node: Construct) -> frozenset[str]:
    """Only freshly introduced loop bindings require an extra Target contract."""
    assert isinstance(node, (For, IterationEntry))
    entry = node.entry if isinstance(node, For) else node
    return (
        frozenset({"iteration.binding.introduced"})
        if entry.introduces_binding
        else frozenset()
    )


def _augmented_rebinding(node: Construct) -> frozenset[str]:
    assert isinstance(node, AugAssign)
    return frozenset(
        {
            "assignment.augmented.target_once",
            "assignment.augmented.read_before_rhs",
            "assignment.augmented.rebind",
        }
    )


def _comparison_chain(node: Construct) -> frozenset[str]:
    assert isinstance(node, ComparisonChain)
    return frozenset(
        {
            "comparison.chain.operands_once",
            "comparison.chain.short_circuit",
            "comparison.chain.left_to_right",
        }
    )


def _intrinsic_call(node: Construct) -> frozenset[str]:
    assert isinstance(node, IntrinsicCall)
    required = {node.definition.key, *node.definition.obligations}
    if node.receiver is not None:
        required.add("intrinsic.receiver_once")
        if node.arguments:
            required.add("intrinsic.receiver_before_arguments")
    if node.arguments:
        required.add("intrinsic.arguments.once")
    if len(node.arguments) >= 2:
        required.add("call.arguments.left_to_right")
    return frozenset(required)


def _format_fragments(node: Construct) -> frozenset[str]:
    assert isinstance(node, FormattedString)
    return frozenset({"format.string.fragments_once_in_order"})


def _membership_semantics(node: Construct) -> frozenset[str]:
    assert isinstance(node, Membership)
    family = (
        "membership.list.identity_or_equality"
        if node.container.kind is model.ValueKind.LIST
        else "membership.dict.key_hash_equality"
    )
    required = {"membership.operands.left_to_right", family}
    if node.negate:
        required.add("membership.negated")
    return frozenset(required)


def _string_membership_semantics(node: Construct) -> frozenset[str]:
    assert isinstance(node, StringContains)
    required = {"membership.string.unicode_substring"}
    if node.negate:
        required.add("membership.negated")
    return frozenset(required)


def _unpack_assignment(node: Construct) -> frozenset[str]:
    assert isinstance(node, UnpackAssign)
    return frozenset(
        {
            "assignment.unpack.rhs_once_before_writes",
            "assignment.unpack.targets_left_to_right",
        }
    )


def _slice_semantics(node: Construct) -> frozenset[str]:
    assert isinstance(node, SliceValue)
    family = (
        "slice.list.shallow_outer_copy"
        if node.kind is model.ValueKind.LIST
        else "slice.string.unicode_codepoints"
    )
    return frozenset(
        {
            "slice.evaluate_source_bounds_once_in_order",
            "slice.python_indices_and_zero_step",
            family,
        }
    )


def _print_values(node: Construct) -> frozenset[str]:
    assert isinstance(node, PrintValues)
    return frozenset(
        {"output.print.space_join_newline", "output.print.evaluate_before_write"}
    )


# The Model already specifies operand evaluation order. The sequence contract
# is independent of whether the selected Target evaluates operators left-first.
# No side-effect analysis, or Target-specific language rules, are done here.
_ORDERED_BINARY = (
    Arithmetic,
    IntegerTrueDivision,
    Comparison,
    FloatingArithmetic,
    FloatingComparison,
    StringConcat,
    StringRepeat,
    StringComparison,
    StringContains,
    StringElement,
)


def _ordered_operands(node: Construct) -> frozenset[str]:
    assert isinstance(node, _ORDERED_BINARY)
    return frozenset({"evaluation.operands.left_to_right"})


def _integer_operator_semantics(node: Construct) -> frozenset[str]:
    """Explicit operator contract, never derived from a Target's width.

    Bitwise operators use the infinite-sign-extension integer model; shifts
    also require Python's nonnegative shift-count rule and signed behavior.
    """
    assert isinstance(node, (Arithmetic, IntegerUnary, AugAssign))
    if node.operator in {"&", "|", "^", "~", "<<", ">>"}:
        required = {"integer.bitwise.unbounded"}
        if node.operator in {"<<", ">>"}:
            required.add("integer.shift.python_counts")
        return frozenset(required)
    return frozenset()


def _integer_true_division(node: Construct) -> frozenset[str]:
    assert isinstance(node, IntegerTrueDivision)
    return frozenset({"integer.true_division.python_float"})


def _unbound_call_order(node: Construct) -> frozenset[str]:
    assert isinstance(node, (Call, FunctionValueCall))
    requirements: set[str] = set()
    if len(node.arguments) >= 2:
        requirements.add("call.arguments.left_to_right")
    if isinstance(node, FunctionValueCall) and node.arguments:
        requirements.add("function_value.callee_before_arguments")
    return frozenset(requirements)


_BOUND_CALLS = (
    FunctionCall,
    InstanceCreation,
    ClassMethodCall,
    ClassReceiverCreation,
    MethodCall,
)

# This is the *single* runtime inventory for currently enforced obligations.
# Add a new Model obligation here only when its meaning is defined. The audit
# tests force guarded fields and semantic obligations to be reconciled.
ADMISSION_RULES: tuple[AdmissionRule, ...] = (
    AdmissionRule(
        "variadic_function_binding",
        (FunctionDefinition, FunctionCall),
        frozenset({"signature"}),
        frozenset({"function.variadic.tuple_binding", "call.variadic.tuple_binding"}),
        _variadic_binding,
    ),
    AdmissionRule(
        "string_membership_semantics",
        (StringContains,),
        frozenset(),
        frozenset({"membership.string.unicode_substring", "membership.negated"}),
        _string_membership_semantics,
    ),
    AdmissionRule(
        "collection_membership",
        (Membership,),
        frozenset(),
        frozenset(
            {
                "membership.operands.left_to_right",
                "membership.list.identity_or_equality",
                "membership.dict.key_hash_equality",
                "membership.negated",
            }
        ),
        _membership_semantics,
    ),
    AdmissionRule(
        "sequence_slice",
        (SliceValue,),
        frozenset(),
        frozenset(
            {
                "slice.evaluate_source_bounds_once_in_order",
                "slice.python_indices_and_zero_step",
                "slice.list.shallow_outer_copy",
                "slice.string.unicode_codepoints",
            }
        ),
        _slice_semantics,
    ),
    AdmissionRule(
        "fixed_tuple_unpack",
        (UnpackAssign,),
        frozenset(),
        frozenset(
            {
                "assignment.unpack.rhs_once_before_writes",
                "assignment.unpack.targets_left_to_right",
            }
        ),
        _unpack_assignment,
    ),
    AdmissionRule(
        "formatted_string_order",
        (FormattedString,),
        frozenset(),
        frozenset({"format.string.fragments_once_in_order"}),
        _format_fragments,
    ),
    AdmissionRule(
        "print_values_semantics",
        (PrintValues,),
        frozenset(),
        frozenset(
            {"output.print.space_join_newline", "output.print.evaluate_before_write"}
        ),
        _print_values,
    ),
    AdmissionRule(
        "intrinsic_call_semantics",
        (IntrinsicCall,),
        frozenset({"definition"}),
        frozenset({"intrinsic.*", "call.arguments.left_to_right"}),
        _intrinsic_call,
    ),
    AdmissionRule(
        "integer_operator_semantics",
        (Arithmetic, IntegerUnary, AugAssign),
        frozenset(),
        frozenset({"integer.bitwise.unbounded", "integer.shift.python_counts"}),
        _integer_operator_semantics,
    ),
    AdmissionRule(
        "integer_true_division",
        (IntegerTrueDivision,),
        frozenset(),
        frozenset({"integer.true_division.python_float"}),
        _integer_true_division,
    ),
    AdmissionRule(
        "augmented_rebinding",
        (AugAssign,),
        frozenset({"mode"}),
        frozenset(
            {
                "assignment.augmented.target_once",
                "assignment.augmented.read_before_rhs",
                "assignment.augmented.rebind",
            }
        ),
        _augmented_rebinding,
    ),
    AdmissionRule(
        "ordered_comparison_chain",
        (ComparisonChain,),
        frozenset(),
        frozenset(
            {
                "comparison.chain.operands_once",
                "comparison.chain.short_circuit",
                "comparison.chain.left_to_right",
            }
        ),
        _comparison_chain,
    ),
    AdmissionRule(
        "ordered_operands",
        _ORDERED_BINARY,
        frozenset(),
        frozenset({"evaluation.operands.left_to_right"}),
        _ordered_operands,
    ),
    AdmissionRule(
        "unbound_call_order",
        (Call, FunctionValueCall),
        frozenset(),
        frozenset(
            {
                "call.arguments.left_to_right",
                "function_value.callee_before_arguments",
            }
        ),
        _unbound_call_order,
    ),
    AdmissionRule(
        "bound_arguments",
        _BOUND_CALLS,
        frozenset({"evaluation_order", "omitted_arguments"}),
        frozenset(
            {
                "call.arguments.bound",
                "call.arguments.left_to_right",
                "call.arguments.reordered",
                "call.defaults.omitted",
            }
        ),
        _bound_arguments,
    ),
    AdmissionRule(
        "method_dispatch",
        (MethodCall,),
        frozenset({"dispatch", "lookup_start"}),
        frozenset(
            {
                "method.dispatch.virtual",
                "method.dispatch.super",
                "method.lookup.lexical_base",
            }
        ),
        _method_dispatch,
    ),
    AdmissionRule(
        "class_receiver",
        (ClassMethodCall, ClassReceiverCreation),
        frozenset(),
        frozenset({"class_receiver.runtime_identity"}),
        _class_receiver,
    ),
    AdmissionRule(
        "for_control_flow",
        (For,),
        frozenset(),
        frozenset({"loop.for.break_continue", "loop.for.normal_completion_else"}),
        _for_control_flow,
    ),
    AdmissionRule(
        "with_context_management",
        (With,),
        frozenset(),
        frozenset({"context.with.enter_exit_exception"}),
        _with_context_management,
    ),
    AdmissionRule(
        "iteration_source",
        (For, IterationEntry),
        frozenset(),
        frozenset({"iteration.source.*"}),
        _iteration_source,
    ),
    AdmissionRule(
        "iteration_binding",
        (IterationEntry,),
        frozenset({"introduces_binding"}),
        frozenset({"iteration.binding.introduced"}),
        _iteration_binding,
    ),
    AdmissionRule(
        "for_iteration_binding",
        (For,),
        frozenset(),
        frozenset({"iteration.binding.introduced"}),
        _iteration_binding,
    ),
)


# Provider-owned explicit inventory. A new Language Construct must be reviewed here
# and in the independent canonical audit, even if it has no admission keys.
LANGUAGE_CONSTRUCT_NAMES: tuple[str, ...] = (
    "Absolute",
    "Arithmetic",
    "Assign",
    "AugAssign",
    "Block",
    "BooleanAggregate",
    "BooleanLiteral",
    "BooleanNot",
    "BooleanOperation",
    "Branch",
    "Break",
    "Call",
    "ClassDefinition",
    "ClassMethodCall",
    "ClassReceiverCreation",
    "ClassReference",
    "Comparison",
    "ComparisonChain",
    "ConditionalExpression",
    "ContextEntry",
    "Continue",
    "DictElement",
    "DictElementAssign",
    "DictEntry",
    "DictValue",
    "ExceptHandler",
    "ExpressionStatement",
    "Extremum",
    "FieldDefinition",
    "FieldInitialize",
    "FieldRead",
    "FieldWrite",
    "FloatingArithmetic",
    "FloatingComparison",
    "FloatingLiteral",
    "FloatingUnary",
    "For",
    "FormattedString",
    "FunctionCall",
    "FunctionDefinition",
    "FunctionValueCall",
    "Initialize",
    "IntrinsicCall",
    "InstanceCreation",
    "IntegerSum",
    "IntegerTrueDivision",
    "IntegerUnary",
    "IterationEntry",
    "LambdaValue",
    "Length",
    "ListElement",
    "ListElementAssign",
    "ListValue",
    "Literal",
    "MethodCall",
    "Membership",
    "NoneLiteral",
    "Parameter",
    "Pass",
    "PrintValues",
    "Program",
    "Raise",
    "Range",
    "Reference",
    "Return",
    "SliceValue",
    "StringComparison",
    "StringConcat",
    "StringContains",
    "StringElement",
    "StringRepeat",
    "Try",
    "TupleElement",
    "TupleValue",
    "UnpackAssign",
    "While",
    "With",
)

LANGUAGE_ADMISSION = AdmissionRegistry(
    AdmissionDeclaration(
        getattr(model, name),
        tuple(
            rule for rule in ADMISSION_RULES if getattr(model, name) in rule.constructs
        ),
    )
    for name in LANGUAGE_CONSTRUCT_NAMES
)


def required_contracts(node: Construct) -> frozenset[str]:
    """Required obligations under the default Language Construct catalog."""
    return LANGUAGE_ADMISSION.required_contracts(node)
