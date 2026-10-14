"""Contract for explicitly typed instance Ports and explicit operations."""

from shikumi_contrace import POST, kind, member, subject

from pyinto.contracts.ports.pipeline import FrontendPort


class MemoryPortContract:
    subject @= FrontendPort

    class parse:
        member @= FrontendPort.parse

        class PythonPort:
            """Port runs as independent Python; C layout is chosen by Binding."""

            kind @= POST

        class ExplicitOperations:
            """Constructor/assign/value/release are registered domain Constructs."""

            kind @= POST

        class AliasRepresentation:
            """Alias initialization propagates declared Port shape for C typing."""

            kind @= POST

        class NoImplicitCleanup:
            """release() emits only at its source position; never auto-inserted."""

            kind @= POST

        class StrictBoundary:
            """Unknown receivers and incompatible/unrepresentable shapes fail."""

            kind @= POST
