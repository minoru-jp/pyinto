"""Contract for explicitly typed mapped objects and explicit operations."""

from shikumi_contrace import POST, kind, member, subject

from pyinto.contracts.boundaries.pipeline import FrontendBoundary


class ClassMappingContract:
    subject @= FrontendBoundary

    class parse:
        member @= FrontendBoundary.parse

        class ExplicitOperations:
            """Constructor/methods/property are registered domain Constructs."""

            kind @= POST

        class AliasRepresentation:
            """Alias initialization propagates declared mapped shape for typing."""

            kind @= POST

        class NoImplicitCleanup:
            """Cleanup emits only at its source position; never auto-inserted."""

            kind @= POST

        class StrictBoundary:
            """Unknown receivers, arguments and incompatible shapes fail."""

            kind @= POST
