"""Runtime stand-ins for kind words. They carry no behavior."""

from __future__ import annotations

from typing import NoReturn


class Word:
    """A vocabulary word usable in annotations."""

    __slots__ = ("_module", "_name")

    def __init__(self, module: str, name: str) -> None:
        self._module = module
        self._name = name

    def __repr__(self) -> str:
        return f"{self._module}.{self._name}"


class Applied:
    """A word written with arguments, such as ``Int[32]``."""

    __slots__ = ("_arguments", "_word")

    def __init__(self, word: Word, arguments: tuple[object, ...]) -> None:
        self._word = word
        self._arguments = arguments

    def __repr__(self) -> str:
        return f"{self._word!r}[{', '.join(map(repr, self._arguments))}]"


class GenericWord(Word):
    """A word that takes arguments in square brackets."""

    __slots__ = ()

    def __getitem__(self, arguments: object) -> Applied:
        if not isinstance(arguments, tuple):
            arguments = (arguments,)
        return Applied(self, arguments)


def conversion_only(operation: str) -> NoReturn:
    raise RuntimeError(
        f"{operation} is pyinto kinds vocabulary for conversion only; "
        "it has no Python behavior"
    )
