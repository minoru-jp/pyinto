"""Generate C using the external memory Port adapter and Shikumi Target Pack."""

from pathlib import Path

from demo_memory_ports_pyinto import c_memory_bindings, interface_mapping_registry

from pyinto import PythonFrontend, realize

ROOT = Path(__file__).resolve().parent


def main() -> None:
    source = (ROOT / "application.py").read_text(encoding="utf-8")
    target = PythonFrontend(interface_mappings=interface_mapping_registry()).parse(
        source
    )
    (ROOT / "generated.c").write_text(
        realize(
            target,
            realizations=c_memory_bindings(),
            admission=interface_mapping_registry().admission,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
