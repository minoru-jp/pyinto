"""Small executable Python function, not a model of the C device implementation."""

from __future__ import annotations

from typing import Any

_UNSET = object()


def is_ready(*, _force: Any = _UNSET) -> bool:
    """Return a controllable Python-only result for exercising application paths.

    _force controls this Python call only; pyinto deliberately discards the
    literal keyword when realizing a registered call in another language.
    """
    if _force is not _UNSET:
        return _force  # type: ignore[no-any-return]
    return False
