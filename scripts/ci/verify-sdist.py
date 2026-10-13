"""Check a source distribution's product docs/examples without extracting it."""

import sys
import hashlib
import tarfile
from pathlib import PurePosixPath

REQUIRED = {
    "scripts/ci/verify-runtime-sets.py",
    "scripts/ci/verify-visible.py",
    "scripts/ci/gate_support/runtime_plan.py",
    "scripts/ci/gate_support/entrypoints.py",
    "scripts/ci/gate_support/python_entrypoint.py",
    "scripts/ci/verify-native-model.py",
    "scripts/ci/verify-assemblies.py",
    "scripts/ci/verify-exports.py",
    "scripts/ci/verify-reverse-cut.py",
    "scripts/ci/verify-feature-depth.py",
    "scripts/ci/verify-drawing-save.py",
    "scripts/ci/verify-drawing-save-as.py",
    "scripts/ci/verify-host-continuation.py",
    "scripts/ci/verify-diameter-dimensions.py",
    "scripts/ci/verify-center-constraints.py",
    "scripts/ci/verify-rectangle-dimensions.py",
    "scripts/ci/verify-plane-geometry.py",
    "scripts/ci/gate_support/__init__.py",
    "scripts/ci/gate_support/model_checks.py",
    "scripts/ci/gate_support/model_native.py",
    "scripts/ci/gate_support/model_depth.py",
    "scripts/ci/gate_support/model_files.py",
    "scripts/ci/gate_support/driving_checks.py",
    "scripts/ci/gate_support/driving_diameter.py",
    "scripts/ci/gate_support/driving_rectangle.py",
    "scripts/ci/gate_support/driving_center.py",
    "scripts/ci/gate_support/driving_geometry.py",
    "README.md",
    "README.CN.md",
    "LICENSE",
    "pyproject.toml",
    "MANIFEST.in",
    "docs/architecture.md",
    "docs/roadmap.md",
    "docs/windows-ci.md",
    "docs/runtime-tests.md",
    "examples/model-plate.ps1",
    "scripts/ci/verify-installed.py",
    "scripts/ci/verify-invalid-requests.py",
    "scripts/ci/verify-modeling.py",
    "scripts/ci/verify-driving-dimensions.py",
    "scripts/ci/verify-toolbox.py",
    "scripts/ci/fixtures/rectangle-origin-bound.SLDPRT",
    "scripts/ci/fixtures/generate-origin-fixture.py",
    "scripts/ci/fixtures/README.md",
    "scripts/ci/verify-sdist.py",
    "scripts/ci/windows/smoke-solidworks.ps1",
    "scripts/ci/windows/equation-fixture-daemon.py",
    "scripts/ci/windows/install-winfsp.ps1",
    "scripts/ci/windows/start-external-host.ps1",
    "scripts/ci/windows/create-external-host.py",
    "src/swcli/skills/swcli/SKILL.md",
    "src/swcli/skills/swcli/references/usage.md",
}
FORBIDDEN_SUFFIXES = {".iso", ".msi", ".reg", ".sldprt", ".sldasm", ".slddrw"}
OWNED_FIXTURE = "scripts/ci/fixtures/rectangle-origin-bound.SLDPRT"
OWNED_FIXTURE_SHA256 = "0cea2c4681bb6fe98ea8aea8c72790742faf1df5b50df88b9932ca7b9f08ce98"


def verify_members(members, *, read_member=None):
    roots, files = set(), set()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise RuntimeError(f"unsafe source distribution path: {member.name}")
        roots.add(path.parts[0])
        if not (member.isfile() or member.isdir()):
            raise RuntimeError(f"unexpected source distribution entry: {member.name}")
        if member.isfile():
            relative = str(PurePosixPath(*path.parts[1:]))
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                if relative != OWNED_FIXTURE or read_member is None:
                    raise RuntimeError(
                        f"CAD/media/registry payload in source distribution: {member.name}"
                    )
                if relative in files or member.size > 65536:
                    raise RuntimeError("duplicate/oversized native rejection fixture")
                if hashlib.sha256(read_member(member)).hexdigest() != OWNED_FIXTURE_SHA256:
                    raise RuntimeError("native rejection fixture checksum mismatch")
            files.add(relative)
    if len(roots) != 1:
        raise RuntimeError("source distribution must have exactly one project root")
    missing = sorted(REQUIRED - files)
    if missing:
        raise RuntimeError(f"source distribution missing product files: {missing}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-sdist.py SOURCE.tar.gz")
    with tarfile.open(sys.argv[1], "r:gz") as archive:
        def read_member(member):
            with archive.extractfile(member) as source:
                return source.read(65537)
        verify_members(archive.getmembers(), read_member=read_member)
    print("SWCLI sources and owned test fixture verified; no other CAD/media payloads")


if __name__ == "__main__":
    main()
