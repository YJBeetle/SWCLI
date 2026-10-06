"""Check a source distribution's product docs/examples without extracting it."""

import sys
import tarfile
from pathlib import PurePosixPath

REQUIRED = {
    "README.md",
    "README.CN.md",
    "LICENSE",
    "pyproject.toml",
    "MANIFEST.in",
    "docs/architecture.md",
    "docs/roadmap.md",
    "docs/windows-ci.md",
    "examples/model-plate.ps1",
    "scripts/ci/verify-installed.py",
    "scripts/ci/verify-invalid-requests.py",
    "scripts/ci/verify-sdist.py",
    "scripts/ci/windows/smoke-solidworks.ps1",
    "scripts/ci/windows/start-manual-host.ps1",
    "src/swcli/skills/swcli/SKILL.md",
    "src/swcli/skills/swcli/references/usage.md",
}
FORBIDDEN_SUFFIXES = {".iso", ".msi", ".reg", ".sldprt", ".sldasm", ".slddrw"}


def verify_members(members):
    roots, files = set(), set()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise RuntimeError(f"unsafe source distribution path: {member.name}")
        roots.add(path.parts[0])
        if not (member.isfile() or member.isdir()):
            raise RuntimeError(f"unexpected source distribution entry: {member.name}")
        if member.isfile():
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                raise RuntimeError(
                    f"CAD/media/registry payload in source distribution: {member.name}"
                )
            files.add(str(PurePosixPath(*path.parts[1:])))
    if len(roots) != 1:
        raise RuntimeError("source distribution must have exactly one project root")
    missing = sorted(REQUIRED - files)
    if missing:
        raise RuntimeError(f"source distribution missing product files: {missing}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-sdist.py SOURCE.tar.gz")
    with tarfile.open(sys.argv[1], "r:gz") as archive:
        verify_members(archive.getmembers())
    print("SWCLI source docs, examples and skill verified; no CAD/media payloads")


if __name__ == "__main__":
    main()
