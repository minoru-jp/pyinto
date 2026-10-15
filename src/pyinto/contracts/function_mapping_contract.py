"""Contract for independent, explicitly mapped functions."""

from shikumi_contrace import POST, kind, member, subject

from pyinto.contracts.boundaries.pipeline import FrontendBoundary


class FunctionMappingContract:
    subject @= FrontendBoundary

    class parse:
        member @= FrontendBoundary.parse

        class ExplicitMapping:
            """Only explicit imported registered calls map to domain Constructs."""

            kind @= POST

        class PythonExecution:
            """The mapped function runs as ordinary Python independent of the target implementation."""

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
