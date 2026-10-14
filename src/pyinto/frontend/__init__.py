"""Python AST normalization; syntax adapters are kept separate from the Model."""

from .parser import PythonFrontend, UnsupportedPython

__all__ = ["PythonFrontend", "UnsupportedPython"]
