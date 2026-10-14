"""Explicitly select the external adapter to generate C from application.py."""

from pathlib import Path

from demo_ports_pyinto import c_device_bindings, interface_mapping_registry

from pyinto import PythonFrontend, realize

EXAMPLE = Path(__file__).resolve().parent


def main() -> None:
    source = (EXAMPLE / "application.py").read_text(encoding="utf-8")
    program = PythonFrontend(interface_mappings=interface_mapping_registry()).parse(
        source
    )
    (EXAMPLE / "generated.c").write_text(
        realize(
            program,
            realizations=c_device_bindings(),
            admission=interface_mapping_registry().admission,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
