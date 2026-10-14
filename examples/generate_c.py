"""Render a Python file through Constructs to a compilable C file.

Usage: python examples/generate_c.py examples/hello.py /tmp/hello.c
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pyinto import PythonFrontend, realize
from tests.support.c_realizer import c_bindings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    program = PythonFrontend().parse(args.input.read_text(encoding="utf-8"))
    args.output.write_text(
        realize(program, realizations=c_bindings()), encoding="utf-8"
    )
    print(f"Generated {args.output}")


if __name__ == "__main__":
    main()
