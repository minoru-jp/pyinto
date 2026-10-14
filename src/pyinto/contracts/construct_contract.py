"""Contracts for explicit typing and late, recursive Template/Slot realization."""

from shikumi_contrace import INV, POST, kind, member, subject

from pyinto.contracts.ports.pipeline import CompositionPort, FrontendPort


class FrontendContract:
    subject @= FrontendPort

    class parse:
        member @= FrontendPort.parse

        class TypedNames:
            """Every variable definition requires an annotation; reassignment uses it."""

            kind @= POST

        class TargetNeutral:
            """Normalization preserves Construct children without Python AST nodes."""

            kind @= POST

        class WhileStructure:
            """While preserves a condition Construct and ordered body/else Blocks."""

            kind @= POST

        class ForStructure:
            """For preserves iteration entry, typed target and ordered body/else Blocks."""

            kind @= POST

        class WithStructure:
            """With preserves ordered context entries and body Block."""

            kind @= POST

        class RejectsUnknown:
            """Unknown syntax and unregistered operations fail without inference."""

            kind @= POST


class ConstructContract:
    subject @= CompositionPort

    class PureStructure:
        """Constructs expose named child positions; none owns target output logic."""

        kind @= INV

    class LateComposition:
        """Nested templates connect by Slots before final text emission."""

        kind @= INV

    class WhileRealization:
        """While entry and body are composed by each target, with no core loop logic."""

        kind @= INV

    class ForRealization:
        """For is interpreted by Target Bindings, not a universal core loop lowering."""

        kind @= INV

    class WithRealization:
        """With context protocol is target-specific; no implicit core cleanup."""

        kind @= INV

    class BindingValidation:
        """Shikumi rejects unknown holes, ambiguous roles and duplicate recipes."""

        kind @= INV

    class TargetIsolation:
        """A target pack can be exchanged without modifying the Construct tree."""

        kind @= INV

    class source:
        member @= CompositionPort.source

        class Compiles:
            """Supported normalized operations produce runnable standalone C."""

            kind @= POST
