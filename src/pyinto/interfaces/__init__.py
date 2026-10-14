"""Target-facing public namespaces for Host-owned Model Interfaces.

These namespaces re-export existing Construct identities. Importing them does
not register or enable a Target Realization.
"""

from . import builtins, language

__all__ = ["builtins", "language"]
