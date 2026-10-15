"""Kinds: vocabulary that passes type and memory information to Targets.

Import words from one surface and one tier::

    from pyinto.kinds.datatypes.general import Wide, Unsigned, Size
    from pyinto.kinds.datatypes.detailed import Int, Null
    from pyinto.kinds.memory.general import Owned, Buffer, Memory
    from pyinto.kinds.memory.detailed import Pointer, Ref
    from pyinto.kinds.declarations.detailed import Interface, Implements

Surfaces: ``datatypes`` (what a value is), ``memory`` (where a value lives,
who owns it, and when it is released) and ``declarations`` (the character of a
declaration such as a class).

Tiers: ``general`` words are interpreted by every language Target, so source
written only with Python's built-in types and ``general`` words is portable.
``detailed`` words are choices close to particular languages; a Target may
reject the ones it does not support.

pyinto defines no meaning for any word. It records them in the Model as labels
and passes them to Targets. Except when ``__pyinto_runtime__`` is used, source
is not expected to run as Python; the words exist so the source still imports,
and the ``Pointer`` / ``Memory`` operations raise if they are ever executed.
"""
