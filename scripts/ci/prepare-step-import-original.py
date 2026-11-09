"""Authenticate one immutable STEP import diagnostic before private inputs/CAD.

Only GitHub metadata and the fixed public evidence ZIP are read. No CAD imports,
export, profile change, retries or original report/path rewrites occur here.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
import zipfile

REPOSITORY = 'YJBeetle/SWCLI'
REPOSITORY_ID = 1377028326
BRANCH = 'codex/swcli-step-export-options'
REF = 'refs/heads/' + BRANCH
WORKFLOW = '.github/workflows/ci.yml'
WORKFLOW_ID = 362005755
SOURCE_RUN = 42413805736
SOURCE_HEAD = '060f26178b4deabc330ef0959b9ec0f1704159cf'
ARTIFACT_ID = 13591430613
ARTIFACT_NAME = 'swcli-windows-hosted-42413805736-1'
ZIP_SHA256 = 'de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7'
REPORT_MEMBER = 'swcli-native-smoke/step-public-readback/source-public-report.json'
ORIGINAL_TEMP = PureWindowsPath(r'D:\a\_temp')
ORIGINAL_DIRECTORY = ORIGINAL_TEMP / 'swcli-native-smoke' / 'step-public'
OUTPUTS = (
    ('ap203-solid-surface.step', '1e740ec1d6cb9e155fcf2e935547ab9ff327f419c4bd0fda0f85952863926ec6', 'ap203', 'solid-surface', 'cli'),
    ('ap203-wireframe.step', '3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90', 'ap203', 'wireframe', 'cli'),
    ('ap203-wireframe-sketches.step', '0790eaaac423cdefef5b3ff71ec6d9e7884d7be33dc214cc1e1419f9dd393e67', 'ap203', 'wireframe-sketches', 'cli'),
    ('ap214-solid-surface.step', '065010d99cdf0a1f12cfee78f625d4bd396602343c47290838ee83bc6ee24e92', 'ap214', 'solid-surface', 'cli'),
    ('ap214-wireframe.step', 'a82720b6349fa2a7c489afb308e2400f4b41652bc81db34d09fa412deb59a587', 'ap214', 'wireframe', 'cli'),
    ('ap214-wireframe-sketches.step', '364e73eac37b4a4f5b7e975c8dc687ffa1dda2fb465217fe6e46876cb914107f', 'ap214', 'wireframe-sketches', 'cli'),
    ('sdk-ap214-solid-surface.STP', '55660dec147231b3900dda0843f0958af9c7434852bb3fba4c8f6f6b10749411', 'ap214', 'solid-surface', 'sdk'),
    ('mcp-ap203-wireframe.step', '46413fb734e36185374ac50f4402ba14952afc5aa8fa287bcda026755f001c5d', 'ap203', 'wireframe', 'mcp'),
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def current_context(env, expected_head, checkout_head):
    require(re.fullmatch('[0-9a-f]{40}', expected_head or '') is not None, 'Expected diagnostic head must be a full SHA')
    require(env.get('GITHUB_REPOSITORY') == REPOSITORY and env.get('GITHUB_REPOSITORY_ID') == str(REPOSITORY_ID), 'Diagnostic repository differs')
    require(env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and env.get('GITHUB_REF') == REF, 'Diagnostic requires its exact manual branch')
    require(env.get('GITHUB_SHA') == checkout_head == expected_head and env.get('DIAGNOSTIC_WORKFLOW_SHA') == expected_head,
            'Diagnostic checkout/run/workflow SHA differs from reviewed head')
    require(env.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + WORKFLOW + '@' + REF, 'Diagnostic workflow/ref differs')
    require(env.get('GITHUB_RUN_ATTEMPT') == '1' and re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID', '')) is not None,
            'Diagnostic requires one original run attempt, never a rerun')
    require(PureWindowsPath(env.get('RUNNER_TEMP', '')) == ORIGINAL_TEMP, 'Runner temp differs from immutable original file paths')
    require(not env.get('GH_HOST') or env['GH_HOST'] == 'github.com', 'Unexpected GitHub API host')
    event = json.loads(Path(env['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    inputs = event.get('inputs', {})
    require(inputs.get('native_step_import_diagnostic') in (True, 'true')
            and inputs.get('native_step_import_head') == expected_head
            and all(inputs.get(key, False) in (False, 'false') for key in
                    ('native_full', 'native_step_targeted', 'native_step_public_targeted')),
            'Diagnostic profile is not exclusive or head differs')
    return {'run_id': int(env['GITHUB_RUN_ID']), 'run_attempt': 1, 'head_sha': expected_head, 'ref': REF,
            'event': 'workflow_dispatch', 'repository': REPOSITORY, 'workflow': WORKFLOW,
            'full_acceptance_eligible': False, 'production_public_acceptance': False}


def validate_run(run, *, run_id, head, source=False):
    require(run.get('id') == run_id and run.get('event') == 'workflow_dispatch'
            and run.get('path') == WORKFLOW and run.get('workflow_id') == WORKFLOW_ID
            and run.get('head_sha') == head and run.get('head_branch') == BRANCH
            and run.get('run_attempt') == 1, 'GitHub workflow run identity differs')
    for field in ('repository', 'head_repository'):
        require(run.get(field, {}).get('id') == REPOSITORY_ID and run.get(field, {}).get('full_name') == REPOSITORY,
                'GitHub workflow repository differs')
    if source:
        require(run.get('status') == 'completed' and run.get('conclusion') == 'failure', 'Fixed source failure is not original/completed')


def validate_artifact(artifact):
    require(artifact.get('id') == ARTIFACT_ID and artifact.get('name') == ARTIFACT_NAME
            and artifact.get('expired') is False and artifact.get('digest') == 'sha256:' + ZIP_SHA256,
            'GitHub original artifact identity/digest differs')
    run = artifact.get('workflow_run', {})
    require(run.get('id') == SOURCE_RUN and run.get('head_sha') == SOURCE_HEAD and run.get('head_branch') == BRANCH
            and run.get('repository_id') == run.get('head_repository_id') == REPOSITORY_ID,
            'GitHub artifact source differs')


def validate_zip(raw):
    require(digest(raw) == ZIP_SHA256, 'Original ZIP SHA256 differs')
    require(len(raw) < 32 * 1024 * 1024, 'Original ZIP exceeds evidence bound')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(len(infos) <= 512 and sum(x.file_size for x in infos) <= 32 * 1024 * 1024, 'Original ZIP content exceeds bound')
        seen = set()
        for info in infos:
            path = PurePosixPath(info.filename)
            require(not path.is_absolute() and all(x not in ('', '.', '..') for x in info.filename.rstrip('/').split('/'))
                    and '\\' not in info.filename and ':' not in info.filename and not stat.S_ISLNK(info.external_attr >> 16),
                    'Unsafe original ZIP member')
            require(info.filename.casefold() not in seen, 'Duplicate original ZIP member')
            seen.add(info.filename.casefold())
        report_bytes = archive.read(REPORT_MEMBER)
        report = json.loads(report_bytes.decode('utf-8'))
        require(report.get('success') is True and report.get('source_commit') == SOURCE_HEAD
                and len(report.get('outputs', [])) == 8, 'Original public receipt source/group differs')
        files = []
        for row, (name, sha, protocol, geometry, surface) in zip(report['outputs'], OUTPUTS):
            require(PureWindowsPath(row.get('path', '')) == ORIGINAL_DIRECTORY / name
                    and row.get('sha256') == sha and row.get('protocol') == protocol
                    and row.get('geometry') == geometry and row.get('surface') == surface,
                    'Original output receipt identity differs: ' + name)
            data = archive.read('swcli-native-smoke/step-public/' + name)
            require(digest(data) == sha, 'Original STEP file SHA256 differs: ' + name)
            files.append((row, data))
    return report_bytes, files


def plain_path(path):
    """Reject symlinks and Windows reparse points in every existing ancestor."""
    path = Path(path)
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'Restoration path contains a link/reparse point')


def restore_files(files, *, target=lambda row: Path(row['path'])):
    # Validate every target before the first directory/file mutation.
    planned = [(target(row), row, raw) for row, raw in files]
    for path, row, raw in planned:
        plain_path(path)
        require(digest(raw) == row['sha256'], 'Restoration input SHA256 differs')
        if path.exists():
            require(path.is_file() and digest(path.read_bytes()) == row['sha256'], 'Refusing to overwrite different existing STEP bytes')
    for path, row, raw in planned:
        path.parent.mkdir(parents=True, exist_ok=True)
        plain_path(path)
        try:
            with path.open('xb') as stream:
                stream.write(raw)
        except FileExistsError:
            require(path.is_file() and digest(path.read_bytes()) == row['sha256'], 'STEP target changed during restoration')
    verify_files(files, target=target)


def verify_files(files, *, target=lambda row: Path(row['path'])):
    for row, raw in files:
        path = target(row)
        plain_path(path)
        require(path.is_file() and digest(path.read_bytes()) == row['sha256'], 'Restored STEP SHA256 differs')


class GitHub:
    def api(self, path, *, binary=False):
        command = ['gh', 'api', '--hostname', 'github.com', 'repos/' + REPOSITORY + '/' + path]
        if binary:
            command += ['-H', 'Accept: application/octet-stream']
        response = subprocess.run(command, capture_output=True, timeout=60)
        # Never surface stderr, authorization, or signed download URLs.
        require(response.returncode == 0, 'GitHub evidence request failed: ' + path)
        return response.stdout if binary else json.loads(response.stdout)


def prepare(output, context, api):
    output = Path(output)
    plain_path(output)
    output.mkdir()  # A fresh run receipt; never replace an older attempt.
    run = api.api('actions/runs/' + str(context['run_id']))
    validate_run(run, run_id=context['run_id'], head=context['head_sha'])
    source = api.api('actions/runs/' + str(SOURCE_RUN))
    validate_run(source, run_id=SOURCE_RUN, head=SOURCE_HEAD, source=True)
    artifact = api.api('actions/artifacts/' + str(ARTIFACT_ID))
    validate_artifact(artifact)
    for name, value in (('diagnostic-run.json', run), ('source-run.json', source), ('source-artifact.json', artifact)):
        (output / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    raw = api.api('actions/artifacts/' + str(ARTIFACT_ID) + '/zip', binary=True)
    with (output / 'original.zip').open('xb') as stream:
        stream.write(raw)
    require(len(raw) == artifact.get('size_in_bytes'), 'Original ZIP byte size differs from GitHub')
    report, files = validate_zip(raw)
    (output / 'source-public-report.json').write_bytes(report)
    restore_files(files)
    context.update(source_run=SOURCE_RUN, source_head=SOURCE_HEAD, artifact_id=ARTIFACT_ID,
                   zip_sha256=ZIP_SHA256, report_sha256=digest(report), outputs=[row for row, _ in files],
                   verified_before_private_inputs=True)
    (output / 'context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    return context


def verify(output, context):
    output = Path(output)
    plain_path(output)
    saved = json.loads((output / 'context.json').read_text(encoding='utf-8'))
    require(all(saved.get(key) == value for key, value in context.items()), 'Prepared diagnostic context differs')
    for name, source in (('diagnostic-run.json', False), ('source-run.json', True)):
        validate_run(json.loads((output / name).read_text(encoding='utf-8')),
                     run_id=SOURCE_RUN if source else context['run_id'], head=SOURCE_HEAD if source else context['head_sha'], source=source)
    artifact = json.loads((output / 'source-artifact.json').read_text(encoding='utf-8'))
    validate_artifact(artifact)
    raw = (output / 'original.zip').read_bytes()
    require(len(raw) == artifact.get('size_in_bytes'), 'Retained ZIP byte size differs')
    report, files = validate_zip(raw)
    require((output / 'source-public-report.json').read_bytes() == report, 'Original report bytes changed')
    require(saved.get('zip_sha256') == ZIP_SHA256 and saved.get('report_sha256') == digest(report)
            and saved.get('source_run') == SOURCE_RUN and saved.get('source_head') == SOURCE_HEAD
            and saved.get('artifact_id') == ARTIFACT_ID and saved.get('outputs') == [row for row, _ in files]
            and saved.get('verified_before_private_inputs') is True, 'Prepared original receipt differs')
    verify_files(files)
    return saved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'verify'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args(argv)
    checkout = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    context = current_context(os.environ, args.expected_head, checkout)
    if args.mode == 'prepare':
        prepare(args.output_dir, context, GitHub())
    else:
        verify(args.output_dir, context)
    print('Verified immutable original8 STEP files; diagnostic only, no production acceptance')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
