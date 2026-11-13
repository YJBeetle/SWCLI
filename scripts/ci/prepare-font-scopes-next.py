"""Build/verify an offline source bundle; never install or run a native host."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

SCOPES = ('dimensions', 'tables')
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(repo, *arguments, data=None):
    return subprocess.run(['git', '-C', str(repo), *arguments], input=data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def object_hash(kind, data):
    return hashlib.sha1(kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def safe_path(name):
    path = PurePosixPath(name)
    require(type(name) is str and name and not path.is_absolute() and str(path) == name
            and not any(part in ('', '.', '..') for part in path.parts)
            and '\\' not in name and ':' not in name and not any(ord(c) < 32 for c in name),
            'unsafe source path')
    return path


def tree_hash(files):
    root = {}
    for row in files:
        parts = safe_path(row['path']).parts
        node = root
        for name in parts[:-1]:
            child = node.setdefault(name, {})
            require(type(child) is dict, 'source file/directory conflict')
            node = child
        require(parts[-1] not in node, 'duplicate source path')
        node[parts[-1]] = (row['mode'], row['git_blob'])
    def digest(node):
        entries = []
        for name, value in node.items():
            folder = type(value) is dict
            mode, oid = ('40000', digest(value)) if folder else value
            entries.append((name.encode('utf-8') + (b'/' if folder else b''),
                mode.encode() + b' ' + name.encode('utf-8') + b'\0' + bytes.fromhex(oid)))
        return object_hash('tree', b''.join(value for _, value in sorted(entries)))
    return digest(root)


def plan(head):
    return dict(evidence_kind='offline-next-preparation', native_executed=False,
        public_acceptance=False, inheritance_acceptance=False, public_new_scopes_enabled=False,
        runtime='native-windows', solidworks_revision='33.5.0', document_types=[1,2,3],
        fields=['typeface','height_mm','height_points','bold','italic','underline','strikeout'],
        expected_cases_per_group=3, expected_changed_writes_per_group=21,
        expected_same_values_per_group=21, expected_saved_files_per_group=6,
        table_read_witness_types=['bom','general','hole','revision','title_block'],
        native_timeout_seconds=600, group_timeout_seconds=1800,
        retry_count=0, host_restart_count=0, automatic_rollback=False,
        offline_gate=['python', '-I', 'scripts/ci/verify-font-scopes-next-offline.py', '--source-head', head],
        groups=[dict(scope=scope, command=['python', '-I', 'scripts/ci/run-font-scopes-calibration.py',
            '--profile', 'internal', '--scope', scope, '--source-head', head,
            '--output-dir', '<fresh-evidence-' + scope + '>', '--swconst', '<registered-swconst.tlb>',
            '--drawing-template', '<installed-GB.drwdot>']) for scope in SCOPES],
        required_evidence=['watchdog.json', 'worker.stdout.log', 'worker.stderr.log',
            'native/report.json', 'native/trace.jsonl', 'native/*.SLD*', 'native/linked-fonts-*.jsonl'],
        execution_authorization='not granted by this bundle; root scheduling required',
        dependencies='source only; dependency wheels and SOLIDWORKS runtime are not bundled')


def snapshot(repo, head):
    require(re.fullmatch(r'[0-9a-f]{40}', head) is not None, 'exact source head required')
    require(git(repo, 'rev-parse', 'HEAD').decode().strip() == head, 'source head differs from checkout')
    require(not git(repo, 'status', '--porcelain', '--untracked-files=normal'), 'source checkout must be clean')
    files = []
    for record in git(repo, 'ls-tree', '-rz', '--full-tree', head).split(b'\0'):
        if not record:
            continue
        metadata, raw_path = record.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        name = raw_path.decode('utf-8')
        safe_path(name)
        require(mode in ('100644', '100755') and kind == 'blob', 'symlinks/submodules are not bundled')
        files.append(dict(path=name, mode=mode, git_blob=oid))
    files.sort(key=lambda row: row['path'].encode('utf-8'))
    objects = sorted({row['git_blob'] for row in files})
    raw = io.BytesIO(git(repo, 'cat-file', '--batch', data=('\n'.join(objects) + '\n').encode()))
    blobs = {}
    for expected in objects:
        oid, kind, size = raw.readline().decode().split()
        data = raw.read(int(size))
        require(oid == expected and kind == 'blob' and raw.read(1) == b'\n', 'invalid git blob batch')
        require(object_hash('blob', data) == oid, 'git blob digest mismatch')
        blobs[oid] = data
    require(raw.read() == b'', 'unexpected git batch data')
    commit = git(repo, 'cat-file', 'commit', head)
    require(object_hash('commit', commit) == head, 'commit digest mismatch')
    require(commit.splitlines()[0] == ('tree ' + tree_hash(files)).encode(), 'source tree differs from commit')
    return files, blobs, commit


def build(repo, head, output):
    files, blobs, commit = snapshot(repo, head)
    required = {'pyproject.toml', 'scripts/ci/run-font-scopes-calibration.py',
                'scripts/ci/verify-font-scopes-calibration.py', 'scripts/ci/verify-font-scopes-next-offline.py'}
    require(required <= {row['path'] for row in files}, 'source snapshot lacks next gate entry points')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    archive = output / ('font-scopes-next-source-' + head[:12] + '.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_STORED) as bundle:
        for row in files:
            data = blobs[row['git_blob']]
            row.update(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            item = zipfile.ZipInfo('source/' + row['path'], FIXED_TIME)
            item.create_system = 3
            item.external_attr = int(row['mode'], 8) << 16
            item.compress_type = zipfile.ZIP_STORED
            bundle.writestr(item, data)
    manifest = dict(format_version=1, source_head=head,
        commit_base64=base64.b64encode(commit).decode(), source_archive=archive.name,
        source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        files=files, plan=plan(head))
    (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    verify(output, head)
    return manifest


def verify(output, head):
    require(re.fullmatch(r'[0-9a-f]{40}', head) is not None, 'exact expected head required')
    output = Path(output)
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    require(set(manifest) == {'format_version', 'source_head', 'commit_base64', 'source_archive',
        'source_archive_sha256', 'files', 'plan'}, 'unexpected source manifest structure')
    require(manifest['format_version'] == 1 and manifest['source_head'] == head, 'source manifest head/version differs')
    require(manifest['plan'] == plan(head), 'source plan broadens the closed preparation profile')
    commit = base64.b64decode(manifest['commit_base64'], validate=True)
    require(object_hash('commit', commit) == head, 'commit is not the expected source head')
    filename = 'font-scopes-next-source-' + head[:12] + '.zip'
    require(manifest['source_archive'] == filename, 'unexpected source archive path')
    archive = output / filename
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['source_archive_sha256'], 'source ZIP digest mismatch')
    files = manifest['files']
    with zipfile.ZipFile(archive) as bundle:
        require(len(bundle.infolist()) == len(files) and len({r['path'] for r in files}) == len(files),
                'source ZIP has duplicate, missing or extra entries')
        require(set(bundle.namelist()) == {'source/' + r['path'] for r in files}, 'source ZIP paths differ')
        for row in files:
            require(set(row) == {'path', 'mode', 'git_blob', 'size_bytes', 'sha256'}, 'unexpected source file metadata')
            safe_path(row['path'])
            require(row['mode'] in ('100644', '100755'), 'unexpected source file mode')
            item = bundle.getinfo('source/' + row['path'])
            require(item.date_time == FIXED_TIME and item.compress_type == zipfile.ZIP_STORED
                    and item.create_system == 3 and item.external_attr >> 16 == int(row['mode'], 8),
                    'source ZIP metadata differs')
            require(item.file_size == row['size_bytes'], 'source file size mismatch')
            data = bundle.read(item)
            require(hashlib.sha256(data).hexdigest() == row['sha256']
                    and object_hash('blob', data) == row['git_blob'], 'source file digest mismatch')
    require(commit.splitlines()[0] == ('tree ' + tree_hash(files)).encode(), 'source files do not match the expected commit tree')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    pack = commands.add_parser('build')
    pack.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    pack.add_argument('--head', required=True)
    pack.add_argument('--output-dir', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--head', required=True)
    check.add_argument('--package-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = build(args.repo_root, args.head, args.output_dir) if args.action == 'build' else verify(args.package_dir, args.head)
    print(json.dumps(dict(source_head=manifest['source_head'], files=len(manifest['files']),
        source_archive_sha256=manifest['source_archive_sha256'], native_executed=False,
        public_acceptance=False, inheritance_acceptance=False), sort_keys=True))


if __name__ == '__main__':
    main()
