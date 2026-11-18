"""Immutable fixtures and finite PUBLIC readonly cases; no CAD or network calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
from zipfile import ZipFile

ARTIFACT_ID = 13535673155
ARTIFACT_RUN = 42279916240
ARTIFACT_HEAD = 'ac9e54f9e533c60ae6af49476ca71aa94b9b0fe2'
ZIP_SHA = '5d5a85844241e6db86d2074e832659340c3c30a7564b65aa0089db581d4095c7'
ZIP_SIZE = 733282
PREFIX = 'swcli-native-smoke/assembly-mates-calibration/native/'
FILES = {
    'coincident-aligned.SLDASM': 'b535588ae3ff2e7656178cea139e974542b3fa1eb82aba2da2b8ee2c6459a081',
    'coincident-aligned-component.SLDPRT': '7a2867363b3e6022916cf039c0ddfab9f60df4dcf2e18064dac9a66dd8f629d8',
    'concentric-aligned-component.SLDPRT': '9b6d73c3a85a5ae7df9bf0b24bdded7f6eb7bf760033b9921f5c7ce3f01bdf66',
}
NAMES = ['coincident-aligned-component-1', 'coincident-aligned-component-2']
HANDLE_PATTERN_REFUSAL = 'target_ids[0] must match ^at-[0-9a-f]{32}$'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def durable(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write('\n'); stream.flush()
        import os
        os.fsync(stream.fileno())


def verify_metadata(metadata, *, now=None):
    require(type(metadata) is dict and type(metadata.get('id')) is int and metadata['id'] == ARTIFACT_ID,
            'unexpected fixed fixture artifact ID')
    require(metadata.get('name') == 'swcli-assembly-mates-42279916240-1'
            and type(metadata.get('size_in_bytes')) is int and metadata['size_in_bytes'] == ZIP_SIZE
            and metadata.get('digest') == 'sha256:' + ZIP_SHA and metadata.get('expired') is False,
            'artifact digest/size/name/expiry flag differs')
    run = metadata.get('workflow_run', {})
    require(run.get('id') == ARTIFACT_RUN and run.get('head_sha') == ARTIFACT_HEAD
            and run.get('head_branch') == 'codex/swcli-assembly-mates', 'artifact provenance differs')
    expires = datetime.fromisoformat(metadata['expires_at'].replace('Z', '+00:00'))
    require((now or datetime.now(timezone.utc)) < expires, 'fixed artifact has expired; stop before native access')


def verify_zip(path):
    require(Path(path).is_file() and Path(path).stat().st_size == ZIP_SIZE and digest(path) == ZIP_SHA,
            'raw original internal ZIP bytes differ')
    with ZipFile(path) as archive:
        names = set()
        for entry in archive.infolist():
            name = entry.filename
            pure = PurePosixPath(name)
            require(not pure.is_absolute() and '..' not in pure.parts and '\\' not in name and ':' not in name
                    and name not in names and not stat.S_ISLNK(entry.external_attr >> 16), 'unsafe/duplicate ZIP member')
            names.add(name)
        result = {}
        for name, expected in FILES.items():
            entry = archive.getinfo(PREFIX + name)
            require(0 < entry.file_size <= 1024*1024, 'fixed fixture size exceeds bound')
            data = archive.read(entry)
            require(hashlib.sha256(data).hexdigest() == expected, 'fixed fixture bytes differ: ' + name)
            result[name] = data
    return result


def extract_fixed(path, target):
    values = verify_zip(path)
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    for name, data in values.items():
        with (target/name).open('xb') as stream:
            stream.write(data);stream.flush()
            import os
            os.fsync(stream.fileno())
        (target/name).chmod(0o444)
    return {name: digest(target/name) for name in FILES}


def cases():
    # Five positive complete passes (30 native owner reads), never per-face retry.
    return [
        ('p1-cli-list', 'cli', 'assembly.targets.list', 'success', 6),
        ('p1-sdk-validate', 'sdk', 'assembly.targets.validate', 'success', 6),
        ('p1-mcp-subset', 'mcp', 'assembly.targets.validate', 'success', 6),
        ('p1-wrong-kind', 'cli', 'assembly.targets.validate', 'ValueError', 0),
        ('p1-reference-hash-as-handle', 'cli', 'assembly.targets.validate', 'ValueError', 0),
        ('p1-cross-document', 'sdk', 'assembly.targets.validate', 'AssemblyTargetNotFound', 0),
        ('p1-cross-session', 'mcp', 'assembly.targets.validate', 'AssemblyTargetNotFound', 0),
        ('p1-expired-lease', 'sdk', 'assembly.targets.validate', 'DocumentLeaseNotFound', 0),
        ('p1-background', 'cli', 'assembly.targets.validate', 'AssemblyNotActive', 0),
        ('p1-reopened-list', 'mcp', 'assembly.targets.list', 'success', 6),
        ('p1-old-snapshot-reopened', 'sdk', 'assembly.targets.validate', 'AssemblyTargetNotFound', 0),
        ('p1-old-target-new-snapshot', 'cli', 'assembly.targets.validate', 'AssemblyTargetNotFound', 0),
        ('p1-wrong-stamp', 'mcp', 'assembly.targets.validate', 'DocumentUpdateConflict', 0),
        ('p1-stale-does-not-revive', 'sdk', 'assembly.targets.validate', 'AssemblyTargetStale', 0),
        ('p2-new-worker-list', 'sdk', 'assembly.targets.list', 'success', 6),
        ('p2-prior-worker-snapshot', 'mcp', 'assembly.targets.validate', 'AssemblyTargetNotFound', 0),
        ('p2-prior-worker-target', 'cli', 'assembly.targets.validate', 'AssemblyTargetNotFound', 0),
    ]


def execution_plan():
    return dict(schema='swcli.assembly-targets.public-readonly-once.v1',
        authorized_to_execute=False, public_native_acceptance=False,
        phases=2, daemon_launches=2, owned_native_hosts=2,
        phase_boundary='Two separately predeclared public daemon lifetimes, never recovery/retry; same host within each phase; each held exit strict0; total group1800',
        native_seconds=600, group_seconds=1800, outer_seconds=1840,
        fixture_artifact_id=ARTIFACT_ID, fixture_run=ARTIFACT_RUN, fixture_head=ARTIFACT_HEAD,
        internal_zip_sha256=ZIP_SHA, fixture_files=FILES, components=NAMES,
        positive_complete_census_passes=5, expected_native_owner_reads=30,
        cases=[dict(id=i, transport=t, operation=o, expected=e, owner_reads=n) for i,t,o,e,n in cases()],
        portable_only=['unknown initial IsSame invalidates every session',
                       'same full value/raw ref but different live native face/body/source identity',
                       'ambiguous native bijection/reference collisions',
                       'mid-request lease expiry and descriptor/retirement secondary failure preserve first error'],
        native_coverage_limits=['No private fault injection is permitted in a pure public readonly gate',
            'Cross-worker refusal follows explicit close/shutdown and proves combined lifetime scope, not an isolated worker-generation causal effect',
            'Reopen compares actual old/new reference hashes; matching hashes never revive old public handles'],
        forbidden=['CreateMate','Save','SaveAs','Select','ActivateDoc','Rebuild','private fixture construction','marking-jig files','CAD process termination'],
        raw_receipts='CLI stdout/stderr + parsed SDK/MCP presentation + exact proxy request/response bytes; fsync intent before one forwarding attempt',
        failure_policy='Persist first error immediately; no next business request; no native recovery; unknown outcome skips CAD cleanup and remains resource-uncertain for coordinator',
        final_document_inventory='After planned assembly and isolated closes, list once. If the catalog is empty, the source ID and path are absent. If only the original clean source remains, close that exact ID once with discard=false and require a second empty list. Any other inventory or close failure stops the phase.',
        lifecycle='Read OS inventory before each phase; public readonly open and document inventory, public close/discard=false; public daemon.serve once per phase; hold OS handle without terminate rights; public shutdown once with proven empty catalog; wait only remaining group budget')
