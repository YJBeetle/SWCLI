"""Verify the installed product resources and portable protocol without COM."""

import json
import os
from pathlib import Path
import sysconfig
import subprocess
import sys
from importlib.metadata import distribution
from importlib.resources import files

from jsonschema import Draft202012Validator

from swcli import __version__
from swcli.operation_schemas import operation_result_schemas, operation_schemas
from swcli.protocol import SCHEMA_NAMES, load_schema


def console_entrypoint(installed, scripts_directory=None):
    entries = [ep for ep in installed.entry_points if ep.group == "console_scripts"]
    if (len(entries) != 1 or entries[0].name != "swcli"
            or entries[0].value != "swcli.cli:main"):
        raise RuntimeError("installed SWCLI must expose only the swcli console command")
    directory = Path(scripts_directory or sysconfig.get_path("scripts"))
    command = directory / ("swcli.exe" if sys.platform == "win32" else "swcli")
    if not command.is_file() or not os.access(command, os.X_OK):
        raise RuntimeError("installed swcli console executable is missing")
    return command


def verify_console_version(command, installed_version):
    result = subprocess.run([str(command), "version", "--json"], capture_output=True,
                            encoding="utf-8", check=True)
    if json.loads(result.stdout)["client_version"] != installed_version:
        raise RuntimeError("swcli console executable does not use the installed distribution")


def main():
    installed = distribution("swcli")
    installed_version = installed.version
    verify_console_version(console_entrypoint(installed), installed_version)
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
    if "# Agent usage guide" not in guide or "swcli capabilities --json" not in guide:
        raise RuntimeError("installed skill usage guide is missing or incomplete")
    api_guide = skill.joinpath("references").joinpath("solidworks-api.md")
    if ("references/solidworks-api.md" not in instructions
            or "](solidworks-api.md)" not in guide
            or not api_guide.read_text(encoding="utf-8").startswith("# Official SOLIDWORKS API workflow\n")):
        raise RuntimeError("installed skill is missing its linked native API guide")
    mcp_guide = skill.joinpath("references").joinpath("mcp.md")
    if "references/mcp.md" not in instructions or "swcli_execute" not in mcp_guide.read_text(encoding="utf-8"):
        raise RuntimeError("installed skill is missing its linked MCP guide")
    print("Installed SWCLI CLI, schemas and product skill verified (no COM activation)")


if __name__ == "__main__":
    main()
