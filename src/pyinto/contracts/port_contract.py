"""Contract for independent, explicitly mapped function Ports."""

from shikumi_contrace import POST, kind, member, subject

from pyinto.contracts.ports.pipeline import FrontendPort


class PortContract:
    subject @= FrontendPort

    class parse:
        member @= FrontendPort.parse

        class ExplicitMapping:
            """Only explicit imported registered calls map to domain Constructs."""

            kind @= POST

        class PythonExecution:
            """Port runs as ordinary Python independent of the target implementation."""

            kind @= POST

        class ForceErasure:
            """_force is a restricted Python-only literal, absent from Target output."""

            kind @= POST

        class StrictBoundary:
            """Unsupported imports, expressions and dynamic options are rejected."""

            kind @= POST

        class NativeBinding:
            """Device calls render by explicit native Target Pack declarations."""

            kind @= POST
