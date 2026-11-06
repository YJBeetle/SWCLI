"""Validate the pinned internal run/artifact before a public acceptance host starts."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

from swcli.document_table_profiles import INTERNAL_PROOF, PROFILES

spec = importlib.util.spec_from_file_location('_table_internal_auditor', Path(__file__).with_name('gate_support') / 'table_defaults_evidence.py')
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


def require(condition, message):
    if not condition:
        raise RuntimeError('table proof preflight: ' + message)


def proof():
    required = {'run_id', 'head', 'artifact_id', 'artifact_name', 'artifact_digest', 'report_sha256', 'native_trace_sha256', 'harness_trace_sha256'}
    require(required <= INTERNAL_PROOF.keys(), 'no independently audited internal evidence is pinned')
    require(all(type(INTERNAL_PROOF[key]) is int and INTERNAL_PROOF[key] > 0 for key in ('run_id', 'artifact_id')), 'invalid pinned run/artifact ID')
    require(re.fullmatch('[0-9a-f]{40}', INTERNAL_PROOF['head']) is not None, 'invalid pinned head')
    require(re.fullmatch('sha256:[0-9a-f]{64}', INTERNAL_PROOF['artifact_digest']) is not None, 'invalid pinned artifact digest')
    require(all(re.fullmatch('[0-9a-f]{64}', INTERNAL_PROOF[key]) is not None for key in
                ('report_sha256', 'native_trace_sha256', 'harness_trace_sha256')), 'invalid pinned report/trace digest')
    require(re.fullmatch('[a-zA-Z0-9-]+', INTERNAL_PROOF['artifact_name']) is not None, 'invalid pinned artifact name')
    return INTERNAL_PROOF


def api(path):
    result = subprocess.run(['gh', 'api', path], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(result.stdout)


def check_remote(env_output):
    pinned = proof()
    run = api('/repos/YJBeetle/SWCLI/actions/runs/' + str(pinned['run_id']))
    require(run['head_sha'] == pinned['head'] and run['conclusion'] == 'success'
            and run['event'] == 'workflow_dispatch' and run['head_branch'] == 'codex/docprops-table-defaults', 'internal run provenance mismatch')
    artifact = api('/repos/YJBeetle/SWCLI/actions/artifacts/' + str(pinned['artifact_id']))
    require(artifact['name'] == pinned['artifact_name'] and artifact['digest'] == pinned['artifact_digest']
            and artifact['expired'] is False and artifact['workflow_run']['id'] == pinned['run_id'], 'original artifact provenance/digest mismatch')
    if env_output:
        with Path(env_output).open('a', encoding='utf-8') as stream:
            for name, key in (('TABLE_INTERNAL_RUN', 'run_id'), ('TABLE_INTERNAL_HEAD', 'head'),
                              ('TABLE_INTERNAL_ARTIFACT_NAME', 'artifact_name'), ('TABLE_INTERNAL_REPORT_SHA256', 'report_sha256')):
                stream.write(name + '=' + str(pinned[key]) + '\n')
    print(json.dumps(dict(success=True, run_id=pinned['run_id'], head=pinned['head'], artifact_digest=pinned['artifact_digest'])))


def check_local(directory):
    pinned = proof()
    result = auditor.audit(directory / 'calibration', directory / 'worker.native.stderr.jsonl', report_sha256=pinned['report_sha256'])
    expected_profiles = {(result['revision'], int(kind)): {field: [tuple(pair) for pair in transitions]
        for field, transitions in fields.items()} for kind, fields in result['profiles'].items()}
    require(PROFILES == expected_profiles, 'runtime transitions differ from independently proved internal scope')
    require(result['native_trace_sha256'] == pinned['native_trace_sha256']
            and result['harness_trace_sha256'] == pinned['harness_trace_sha256'], 'original trace digest mismatch')
    (directory / 'independent-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(success=True, report_sha256=pinned['report_sha256'], native_setter_calls=result['native_setter_calls'])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('remote', 'local'))
    parser.add_argument('--env-output', type=Path)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args(argv)
    if args.mode == 'remote':
        check_remote(args.env_output)
    else:
        require(args.directory is not None, 'local proof directory is required')
        check_local(args.directory)


if __name__ == '__main__':
    main()
