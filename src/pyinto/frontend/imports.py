"""Parse-local resolution of explicit imports for types, decorators, and interface mappings.

This layer binds registered names only. It never evaluates imported source and
never turns a decorator into a Model Construct by guessing its meaning.
"""

from __future__ import annotations

import ast

from pyinto.interface_mapping import InterfaceMappingRegistry

from .context import NameState
from .decorators import DecoratorRegistry
from .errors import reject


class ImportNormalizer:
    def __init__(
        self,
        names: NameState,
        interface_mappings: InterfaceMappingRegistry,
        decorators: DecoratorRegistry,
    ) -> None:
        self._names = names
        self._interface_mappings = interface_mappings
        self._decorators = decorators

    def _reserve(self, local: str, node: ast.stmt) -> None:
        if (
            local in {"print", "range"}
            or local in self._names.type_aliases
            or local in self._names.callable_aliases
            or local in self._names.interface_aliases
            or local in self._names.module_aliases
            or local in self._decorators.imported_names
        ):
            raise reject(node, f"Duplicate or reserved import alias: {local!r}")

    def accept(self, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not self._interface_mappings.has_namespace(alias.name):
                    raise reject(
                        node, f"Unregistered interface mapping module: {alias.name!r}"
                    )
                # Python binds the root for `import package.module`, but the
                # complete module for `import package.module as local`.
                local = alias.asname or alias.name.split(".", 1)[0]
                source = alias.name if alias.asname else local
                # Repeated submodule imports legitimately bind the same root:
                # `import pkg.alpha; import pkg.beta` binds `pkg` both times.
                if self._names.module_aliases.get(local) == source:
                    self._names.module_import_paths[local].add(alias.name)
                    continue
                self._reserve(local, node)
                self._names.module_aliases[local] = source
                self._names.module_import_paths[local] = {alias.name}
            return
        if node.level or not node.module:
            raise reject(
                node, "Only explicit absolute interface mapping imports are supported"
            )
        if node.module == "typing":
            for alias in node.names:
                if alias.name not in {"Any", "Callable"}:
                    raise reject(
                        node, "Only typing.Any / Callable imports are supported"
                    )
                local = alias.asname or alias.name
                if (
                    local in self._names.interface_aliases
                    or local in self._names.module_aliases
                    or local in self._names.type_aliases
                    or local in self._names.callable_aliases
                    or local in {"print", "range"}
                ):
                    raise reject(node, "Conflicting type import")
                if alias.name == "Callable":
                    self._names.callable_aliases.add(local)
                else:
                    self._names.type_aliases.add(local)
            return
        for alias in node.names:
            source = f"{node.module}.{alias.name}"
            local = alias.asname or alias.name
            self._reserve(local, node)
            if self._decorators.bind_import(source, local):
                continue
            if (
                self._interface_mappings.get(source) is not None
                or self._interface_mappings.get_class(source) is not None
            ):
                self._names.interface_aliases[local] = source
            elif self._interface_mappings.has_namespace(source):
                self._names.module_aliases[local] = source
                self._names.module_import_paths[local] = {source}
            else:
                raise reject(node, f"Unregistered interface mapping import: {source!r}")
