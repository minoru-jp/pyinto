"""Explicit shikumi-contrace pytest integration."""

# The adapter is deliberately outside src/pyinto and is loaded explicitly.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "port_demo"))

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "examples" / "memory_port_demo")
)

pytest_plugins = ["shikumi_contrace.pytest"]
