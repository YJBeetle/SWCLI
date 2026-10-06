"""Verify the installed product resources and portable protocol without COM."""

import json
import subprocess
import sys
from importlib.metadata import version
from importlib.resources import files

from jsonschema import Draft202012Validator

from swcli import __version__
from swcli.operation_schemas import operation_result_schemas, operation_schemas
from swcli.protocol import SCHEMA_NAMES, load_schema


def main():
    installed_version = version("swcli")
    if __version__ != installed_version:
        raise RuntimeError(
            "imported SWCLI does not match installed distribution metadata"
        )
    result = subprocess.run(
        [sys.executable, "-I", "-m", "swcli", "version", "--json"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    if json.loads(result.stdout)["client_version"] != installed_version:
        raise RuntimeError("isolated CLI does not use the installed SWCLI distribution")
    for name in SCHEMA_NAMES:
        Draft202012Validator.check_schema(load_schema(name))
    for schemas in (operation_schemas(), operation_result_schemas()):
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)
    skill = files("swcli").joinpath("skills").joinpath("swcli")
    instructions = skill.joinpath("SKILL.md").read_text(encoding="utf-8")
    guide = (
        skill.joinpath("references").joinpath("usage.md").read_text(encoding="utf-8")
    )
    if (
        not instructions.startswith("---\nname: swcli\n")
        or "references/usage.md" not in instructions
    ):
        raise RuntimeError(
            "installed product skill is missing its metadata or usage link"
        )
    if "# Agent usage guide" not in guide or "sw-cli capabilities --json" not in guide:
        raise RuntimeError("installed skill usage guide is missing or incomplete")
    print("Installed SWCLI CLI, schemas and product skill verified (no COM activation)")


if __name__ == "__main__":
    main()
