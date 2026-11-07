"""Bounded public standard CLI/daemon + SDK/MCP proof after audited native proof.

Standard kind groups and existing font/display profile groups each retain
independent 1800-second budgets. Explicit batch scope covers all five groups.
One owned hidden daemon is retained across the groups. No API retry or restart.
Absent committed native success proof or exact whitelist => fail before startup.
"""
import argparse
import asyncio
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / 'docs/calibration/docprops-performance-windows.json'
REPOSITORY = 'YJBeetle/SWCLI'
WORKFLOW_ID = 362005755


def checked(ok, message):
    if not ok:
        raise RuntimeError(message)


def load_script(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def finite_transitions():
    return {(kind, source, target, 'drafting-defaults-v1') for kind in (1, 2, 3)
            for named in range(1, 7) for source, target in ((7, named), (named, 7))}


def verified_proof(path=PROOF):
    checked(path.is_file(), 'committed independently audited native success proof missing; public gate remains closed')
    proof = read_json(path)
    checked(proof.get('native_group_complete') is True and proof.get('completed_transitions') == 36
            and proof.get('full_acceptance_eligible') is False, 'internal success proof incomplete')
    checked(type(proof.get('host_revision')) is str and proof['host_revision'], 'tested native host revision missing')
    checked(all(type(row) in (list, tuple) and len(row) == 4
                and all(type(value) is int for value in row[:3]) and row[3] == 'drafting-defaults-v1'
                for row in proof['transitions']), 'transition scope must retain exact typed values')
    checked({tuple(row) for row in proof['transitions']} == finite_transitions()
            and len(proof['transitions']) == 36, 'proof does not cover the exact finite transition set')
    from swcli.document_drafting_standard import CALIBRATED_DRAFTING_TRANSITIONS, CALIBRATED_DRAFTING_WINDOWS_REVISIONS
    checked(set(CALIBRATED_DRAFTING_TRANSITIONS) == finite_transitions()
            and len(CALIBRATED_DRAFTING_TRANSITIONS) == 36, 'exact audited public whitelist is not installed')
    checked(tuple(CALIBRATED_DRAFTING_WINDOWS_REVISIONS) == (proof['host_revision'],),
            'public native Windows revision scope differs from audited host')
    return proof


def gh_json(route):
    return json.loads(subprocess.check_output(['gh', 'api', 'repos/' + REPOSITORY + '/' + route]))


def validate_dependency(proof):
    run = gh_json('actions/runs/' + str(proof['run_id']))
    checked(run['status'] == 'completed' and run['conclusion'] == 'success'
            and run['event'] == 'workflow_dispatch' and run['workflow_id'] == WORKFLOW_ID
            and run['head_sha'] == proof['source_head'] and run['run_attempt'] == proof['run_attempt'] == 1
            and run['head_branch'] == 'codex/docprops-calibration-performance', 'native provenance run/head/scope mismatch')
    artifacts = gh_json('actions/runs/' + str(proof['run_id']) + '/artifacts')['artifacts']
    matches = [row for row in artifacts if row['id'] == proof['artifact_id']]
    checked(len(matches) == 1, 'exact native artifact ID missing/ambiguous')
    artifact = matches[0]
    checked(sum(row['name'] == artifact['name'] for row in artifacts) == 1, 'native artifact name is ambiguous')
    checked(artifact['expired'] is False and artifact['digest'] == 'sha256:' + proof['artifact_sha256']
            and artifact['workflow_run']['head_sha'] == proof['source_head']
            and artifact['name'] == f"swcli-docprops-performance-{proof['run_id']}-1", 'native artifact digest/head differs')
    return {'run_id': run['id'], 'source_head': run['head_sha'], 'artifact_id': artifact['id'],
            'artifact_name': artifact['name'], 'artifact_digest': artifact['digest'], 'run_attempt': 1}


def prepare_fixtures(raw, destination, proof):
    auditor = load_script('_public_docprops_native_audit', 'scripts/dev/audit-document-properties-calibration.py')
    result = auditor.audit(raw, proof['source_head'])
    checked(result['native_group_complete'] and result['manifest_sha256'] == proof['manifest_sha256']
            and result['source_hashes'] == proof['source_hashes'], 'downloaded native originals do not match committed independent proof')
    report = read_json(raw / 'standards-36/report.json')
    driver = read_json(raw / 'standards-36-driver/driver.json')
    original_root = PureWindowsPath(driver['output'])
    destination.mkdir(parents=True, exist_ok=False)
    fixtures = []
    for case in report['cases']:
        suffix = {'part': 'SLDPRT', 'assembly': 'SLDASM', 'drawing': 'SLDDRW'}[case['kind']]
        baseline = case['baseline']
        relative = PureWindowsPath(baseline['path']).relative_to(original_root)
        source = (raw / 'standards-36' / Path(*relative.parts)).resolve()
        checked((raw / 'standards-36').resolve() in source.parents, 'native baseline escapes artifact')
        checked(source.is_file() and source.suffix.upper() == '.' + suffix
                and hashlib.sha256(source.read_bytes()).hexdigest() == baseline['sha256'], 'native baseline bytes/type differ')
        target = destination / ('annotations.' + suffix)
        shutil.copyfile(source, target)
        checked(hashlib.sha256(target.read_bytes()).hexdigest() == baseline['sha256'], 'fixture copy differs')
        fixtures.append({'kind': case['kind'], 'path': str(target), 'sha256': baseline['sha256']})
    return {'native_audit': result, 'fixtures': fixtures}


def contract_probe(gate, trace, profile, document, before):
    """One typed SDK read + one MCP read per kind; neither starts/writes CAD."""
    from swcli.sdk import Client
    from swcli.result_schemas import validate_operation_result
    names = {'standards': ('drafting-standard', 'drafting_standard', 'drafting-standard-set', 'expected_snapshot', ('standard','observed_defaults','document')),
             'fonts': ('annotation-font','annotation_font','annotation-font-set','expected_font',('font','native_font','document')),
             'display': ('display-options','display_options','display-option-set','expected_value',('options','document'))}
    read_name, sdk_name, set_name, cas_name, keys = names[profile]
    if profile == 'standards':
        checked(before['standard'] == {'value': 'gb', 'native_value': 7}, 'audited GB baseline was not retained before public writes')
    client = Client(endpoint=gate.endpoint, session_id=gate.session + '-sdk-contract', timeout_seconds=600)
    capabilities = client.daemon.capabilities(include_schemas=True, operation='document.' + set_name).require_result()
    schema = capabilities['operation_schemas']['document.' + set_name]
    checked({'value', cas_name} <= set(schema['required']), 'installed writer CAS schema missing')
    response = getattr(client.document, sdk_name)(document_id=document, expected_update_stamp=before['document']['update_stamp'])
    sdk = {**response.require_result(), 'request_id': response.request_id}

    async def mcp_read():
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        env = dict(os.environ)
        env.pop('SWCLI_CLIENT_WORKSPACE', None)
        params = StdioServerParameters(command=sys.executable,
            args=['-I', '-m', 'swcli', '--endpoint', gate.endpoint, '--request-timeout', '600', 'mcp', 'serve'], env=env)
        with (gate.directory / 'mcp-contract.stderr.log').open('w', encoding='utf-8') as errors:
            async with stdio_client(params, errlog=errors) as streams:
                async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=600)) as session:
                    initialized = await session.initialize()
                    checked(initialized.serverInfo.name == 'swcli', 'unexpected MCP server')
                    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                    checked('execute' in tools and 'document_id' in tools['execute'].inputSchema['properties'],
                            'MCP execute document context schema missing')
                    result = await session.call_tool('execute', {'operation': 'document.' + read_name, 'parameters': {},
                        'session_id': gate.session + '-mcp-contract', 'document_id': document,
                        'expected_update_stamp': before['document']['update_stamp']})
                    checked(not result.isError and result.structuredContent['success'] is True, 'MCP standard read failed')
                    checked(json.loads(result.content[0].text) == result.structuredContent, 'MCP text/structured contract differs')
                    return {**result.structuredContent['result'], 'request_id': result.structuredContent['request_id']}

    mcp_result = asyncio.run(mcp_read())
    proofs = []
    for name, result in (('sdk', sdk), ('mcp', mcp_result)):
        validate_operation_result('document.' + read_name,
                                  {key: value for key, value in result.items() if key != 'request_id'})
        checked(result['ok'] is True and canonical({key: result[key] for key in keys})
                == canonical({key: before[key] for key in keys}),
                name + ' read differs from public CLI snapshot/state')
        gate.record['events'].append({'command': [name, 'document', read_name], 'result': result})
        proof = trace.verify(gate, profile)
        gate.background(result, document)
        proofs.append({'transport': name, 'response': result, 'native_trace': proof})
    gate.record.setdefault('sdk_mcp_contracts', []).append({'document_id': document, 'proofs': proofs})
    gate.checkpoint('sdk-mcp-contracts-verified')


def gate_group(output, fixtures, native_trace, kind, host_revision, profile="standards"):
    gate_module = load_script('_public_docprops_preference_gate', 'scripts/ci/verify-document-preferences.py')
    kinds = tuple(row for row in gate_module.KINDS if kind is None or row[1] == kind)
    output.mkdir(parents=True, exist_ok=False)
    gate = gate_module.support.AnnotationSmoke(directory=output, host_directory=str(output),
                                              endpoint=gate_module.support.modeling.DEFAULT_ENDPOINT)
    gate.record_path = output / ('document-preferences-' + profile + '.json')
    with gate.record_path.open('x', encoding='utf-8') as stream:
        json.dump(gate.record, stream)
    trace = gate_module.PreferenceTrace(native_trace)
    try:
        checked(gate.health()['host']['revision'] == host_revision, 'public host revision differs from audited native host')
        gate_module.run(gate, fixtures, trace, profile, kinds=kinds, contract_probe=contract_probe)
    except BaseException as error:
        gate.record.update(state='failed', success=False, error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        gate.cleanup()
        if gate.record['cleanup_errors'] or gate.checkpoint_error is not None:
            gate.record.update(state='failed', success=False)
        gate.record['native_trace_snapshot'] = trace.snapshot()
        gate.checkpoint('public-standard-kind-final')
    checked(gate.record['success'] is True and not gate.record['cleanup_errors'] and gate.checkpoint_error is None,
            'public standard kind/cleanup incomplete')


def run_public(output, fixtures, expected_head, scope="standards"):
    output.mkdir(parents=True, exist_ok=False)
    record = {'success': False, 'source_head': expected_head, 'full_acceptance_eligible': False,
              'scope': scope + ': explicit independent 1800-second groups',
              'groups': [], 'cleanup_errors': [], 'native_timeout_seconds': 600, 'group_timeout_seconds': 1800}
    stdout_path, stderr_path = output / 'daemon.stdout.log', output / 'daemon.stderr.log'
    daemon = None
    with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
        try:
            env = dict(os.environ, SWCLI_TRACE_NATIVE_CALLS='1')
            daemon = subprocess.Popen([sys.executable, '-I', '-m', 'swcli', 'daemon', 'serve', '--startup-timeout', '120'],
                                      stdout=stdout, stderr=stderr, env=env)
            record['daemon_python_pid'] = daemon.pid
            deadline = time.monotonic() + 180
            while True:
                checked(daemon.poll() is None, 'owned public daemon exited before ready')
                if b'"action": "daemon.serve"' in stdout_path.read_bytes(): break
                checked(time.monotonic() < deadline, 'owned public daemon readiness deadline exceeded')
                time.sleep(.2)
            anchor_host = None
            plan = []
            if scope in ('standards','batch'): plan += [('standards', kind, 'kind-' + str(kind)) for kind in (1,2,3)]
            if scope in ('fonts-display','batch'): plan += [('fonts', None, 'fonts'), ('display', None, 'display')]
            for profile, kind, label in plan:
                group = {'profile': profile, 'document_type': kind, 'timeout_seconds': 1800, 'success': False}
                record['groups'].append(group)
                with (output / (label + '.stdout.log')).open('wb') as go, (output / (label + '.stderr.log')).open('wb') as ge:
                    command = [sys.executable, '-I', str(Path(__file__)), '--expected-head', expected_head, '--run-gate',
                               '--output-dir', str(output / label), '--fixture-dir', str(fixtures),
                               '--native-trace', str(stderr_path), '--profile', profile]
                    if kind is not None: command += ['--kind', str(kind)]
                    result = subprocess.run(command, stdout=go, stderr=ge, timeout=1800)
                checked(result.returncode == 0, f'public kind {kind} failed; first failure stops the remaining kinds')
                evidence = read_json(output / label / ('document-preferences-' + profile + '.json'))
                cases = evidence['preference_cases']
                checked(evidence['success'] is True and len(cases) == (1 if kind is not None else 3)
                        and len(evidence.get('sdk_mcp_contracts', [])) == len(cases), 'public cases/contracts incomplete')
                for case in cases:
                    expected = 12 if profile == 'standards' else 7 if profile == 'fonts' else 5 if case['document_type'] == 3 else 10
                    checked(len(case['writes']) == expected and len(case['saved_copies']) == (expected if profile != 'display' else 1),
                            'public field/save coverage incomplete')
                if anchor_host is None:
                    anchor_host = evidence['host']
                checked(evidence['host'] == evidence['host_after'] == anchor_host and daemon.poll() is None,
                        'owned daemon/host changed across public groups')
                group['success'] = True
            record['success'] = True
        except BaseException as error:
            record['failure'] = {'type': type(error).__name__, 'message': str(error)}
        finally:
            if daemon is not None and daemon.poll() is None:
                try:
                    with (output / 'daemon-stop.stdout.log').open('wb') as so, (output / 'daemon-stop.stderr.log').open('wb') as se:
                        stopped = subprocess.run([sys.executable, '-I', '-m', 'swcli', '--request-timeout', '600', 'daemon', 'stop', '--json'],
                                                 stdout=so, stderr=se, timeout=610)
                    checked(stopped.returncode == 0 and daemon.wait(timeout=30) == 0, 'owned public daemon shutdown incomplete')
                except BaseException as error:
                    record['cleanup_errors'].append({'type': type(error).__name__, 'message': str(error)})
            elif daemon is not None:
                record['cleanup_errors'].append({'type': 'UnexpectedDaemonExit', 'exit_code': daemon.poll()})
            record['success'] = record['success'] and not record['cleanup_errors']
            (output / 'public-report.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    return 0 if record['success'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--check-dependency', action='store_true')
    parser.add_argument('--run-gate', action='store_true')
    parser.add_argument('--artifact-root', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--fixture-dir', type=Path)
    parser.add_argument('--native-trace', type=Path)
    parser.add_argument('--scope', choices=('standards','fonts-display','batch'), default='standards')
    parser.add_argument('--profile', choices=('standards','fonts','display'), default='standards')
    parser.add_argument('--kind', type=int, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    owner = load_script('_public_docprops_source_context', 'scripts/ci/verify-document-properties-calibration.py')
    context = owner.source_context(args.expected_head)
    proof = verified_proof()
    if args.run_gate:
        checked(args.output_dir and args.fixture_dir and args.native_trace and (args.kind or args.profile != 'standards'), 'explicit gate inputs required')
        gate_group(args.output_dir, args.fixture_dir, args.native_trace, args.kind, proof['host_revision'], args.profile)
        return 0
    dependency = validate_dependency(proof)
    if args.check_dependency:
        if os.environ.get('GITHUB_OUTPUT'):
            with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as stream:
                stream.write(f"run_id={dependency['run_id']}\nartifact_name={dependency['artifact_name']}\n")
        print(json.dumps(dependency))
        return 0
    checked(args.artifact_root and args.output_dir, 'verified native artifact and new output required')
    fixtures = args.output_dir.with_name(args.output_dir.name + '-fixtures')
    workspace = Path(r'C:\Workspace').resolve()
    checked(workspace in args.output_dir.resolve().parents, 'public output must be below C:\\Workspace')
    prepared = prepare_fixtures(args.artifact_root, fixtures, proof)
    (fixtures / 'provenance.json').write_text(json.dumps({'public_context': context, 'dependency': dependency, **prepared}, indent=2)+'\n', encoding='utf-8')
    code = run_public(args.output_dir, fixtures, args.expected_head, args.scope)
    (args.output_dir / 'fixture-provenance.json').write_text(json.dumps(prepared, indent=2)+'\n', encoding='utf-8')
    (args.output_dir / 'context.json').write_text(json.dumps({'public_context': context, 'dependency': dependency,
        'native_proof_sha256': hashlib.sha256(PROOF.read_bytes()).hexdigest()}, indent=2)+'\n', encoding='utf-8')
    files = [{'path': p.relative_to(args.output_dir).as_posix(), 'bytes': p.stat().st_size,
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(args.output_dir.rglob('*')) if p.is_file()]
    (args.output_dir / 'manifest.json').write_text(json.dumps({'source_head': args.expected_head, 'files': files,
        'group_design': args.scope + ': independent 1800-second public groups, no internal group substitution',
        'full_acceptance_eligible': False}, indent=2)+'\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
