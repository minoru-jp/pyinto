"""Explicit shikumi-contrace pytest integration."""

# The adapter is deliberately outside src/pyinto and is loaded explicitly.
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "examples" / "mapping_demo")
)

pytest_plugins = ["shikumi_contrace.pytest"]
