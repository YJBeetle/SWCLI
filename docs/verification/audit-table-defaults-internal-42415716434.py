"""Audit original all-type internal run 42415716434; never public acceptance."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PIN = dict(run=42415716434, head='f1881a7421200e46028652538892c15a366f2ef8', artifact=13591813168,
           name='table-defaults-internal-42415716434-1',
           digest='7e1d8fcd8c1d8b26346024305c0f30a0c77536b2ea4ade06f3c694e382db9e8e',
           report='9e4c61044958cbe5ae6964820e8e800e87f003871ca419850e56c319dfd566cf',
           harness='3926c138fae2f4747ff53ecbd6608c9a61960d3e3a132a7eea2f51a6231d6af9',
           native='0ceb9245963abf13eeaef13162c3ef6318fbd405d16fa8096ee69260684d0127')
EXPECTED = {
    '1': {'all.use_template_settings': [[True, False], [False, False]],
          'bom.box_border': [[0, 1], [1, 1]], 'bom.grid_border': [[0, 1], [1, 1]]},
    '2': {'all.use_template_settings': [[True, False], [False, False]],
          'bom.box_border': [[0, 1], [1, 1]], 'bom.grid_border': [[0, 1], [1, 1]]},
    '3': {'all.use_template_settings': [[False, True], [True, True]],
          'bom.box_border': [[0, 1], [1, 1]], 'bom.grid_border': [[0, 1], [1, 1]],
          'general.box_border': [[0, 1], [1, 1]], 'general.grid_border': [[0, 1], [1, 1]]}}


def require(value, message):
    if not value:
        raise RuntimeError('42415716434 original audit: ' + message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guard_reads(calls):
    require({'IsOpenedReadOnly', 'IsOpenedViewOnly', 'GetTitle', 'GetPathName', 'Extension',
             'GetDocuments', 'ActiveDoc', 'GetSaveFlag', 'GetUpdateStamp'} <= set(calls),
            'mutation lacks target/peer/permission observation span')


def audit(evidence):
    run, artifact = load(evidence / 'completion-run.json'), load(evidence / 'artifact.json')
    require((run['id'], run['head_sha'], run['head_branch'], run['event'], run['status'], run['conclusion']) ==
            (PIN['run'], PIN['head'], 'codex/docprops-table-defaults', 'workflow_dispatch', 'completed', 'success'), 'run provenance')
    require((artifact['id'], artifact['name'], artifact['workflow_run']['id'], artifact['workflow_run']['head_sha'], artifact['expired']) ==
            (PIN['artifact'], PIN['name'], PIN['run'], PIN['head'], False), 'artifact provenance')
    require(digest(evidence / 'original.zip') == PIN['digest'] and artifact['digest'] == 'sha256:' + PIN['digest'], 'official ZIP digest')
    # These are the guard, comparison and harness sources actually exercised.
    paths = ['src/swcli/hosts/windows_document_tables.py', 'src/swcli/daemon/server.py',
             'scripts/ci/verify-table-defaults-calibration.py', 'scripts/ci/gate_support/table_defaults_geometry.py',
             'scripts/ci/prepare-annotation-fixtures.py', 'src/swcli/result_schemas.py']
    subprocess.run(['git', 'diff', '--exit-code', PIN['head'], '--', *paths], cwd=ROOT, check=True, capture_output=True)
    with tempfile.TemporaryDirectory(prefix='table-original-42415716434-') as temporary:
        original = Path(temporary)
        with zipfile.ZipFile(evidence / 'original.zip') as zipped:
            names = set()
            for entry in zipped.infolist():
                path = PurePosixPath(entry.filename)
                require(not path.is_absolute() and '..' not in path.parts and '\\' not in entry.filename
                        and not stat.S_ISLNK(entry.external_attr >> 16) and entry.filename not in names
                        and entry.file_size < 10_000_000, 'unsafe or duplicate ZIP member')
                names.add(entry.filename)
            expected_names = {'wrapper-result.json', 'worker.stdout.log', 'worker.native.stderr.jsonl',
                              'calibration/report.json', 'calibration/trace.jsonl', 'calibration/geometry-observations.jsonl'}
            expected_names |= {'calibration/' + prefix + '.' + suffix for prefix in ('annotations', 'table-defaults')
                               for suffix in ('SLDPRT', 'SLDASM', 'SLDDRW')}
            require(names == expected_names, 'unexpected or missing original files')
            zipped.extractall(original)
        spec = importlib.util.spec_from_file_location('_table_original_core', ROOT / 'scripts/ci/gate_support/table_defaults_evidence.py')
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)
        result = core.audit(original / 'calibration', original / 'worker.native.stderr.jsonl', report_sha256=PIN['report'])
        require(result['profiles'] == EXPECTED and result['document_types'] == [1, 2, 3], 'measured scope differs from manually reviewed scope')
        require(result['native_trace_sha256'] == PIN['native'] and result['harness_trace_sha256'] == PIN['harness'], 'trace hashes')
        require(load(original / 'wrapper-result.json') == dict(success=True, worker_exit_code=0, native_seconds=600, group_seconds=1800), 'wrapper/budget')
        report = load(original / 'calibration/report.json')
        rows = [json.loads(line) for line in (original / 'worker.native.stderr.jsonl').read_text(encoding='utf-8-sig').splitlines()
                if line.startswith('{')]
        rows = [row for row in rows if row.get('event') == 'swcli.native-call']
        blocks, current = [], None
        for row in rows:
            if row['phase'] != 'begin':
                continue
            if row['call'] == 'swconst.LoadTypeLib':
                current = []
                blocks.append(current)
            if current is not None:
                current.append(row)
        blocks = iter(block for block in blocks if any(row['call'].startswith('IModelDocExtension.GetUserPreference') for row in block))
        field_proofs = []
        for case in report['cases']:
            kind = case['document_type']
            fields = list(EXPECTED[str(kind)])
            cycle = ['IModelDocExtension.GetUserPreference' + ('Toggle' if field.startswith('all.') else 'Integer') for field in fields]
            require([r['call'] for r in next(blocks) if r['call'].startswith('IModelDocExtension.')] == cycle, 'original read order')
            initial = case['original']['document']
            require(initial['type'] == kind and initial['modified'] is False and initial['active'] is False
                    and initial['current'] is False and case['writable_open']['read_only'] is False, 'initial target is not clean/writable/background')
            for index, (field, changed, noop, conflict) in enumerate(zip(fields, case['writes'], case['noops'], case['conflicts'])):
                block = next(blocks)
                calls = [row['call'] for row in block]
                method = 'IModelDocExtension.SetUserPreference' + ('Toggle' if field.startswith('all.') else 'Integer')
                require([call for call in calls if call.startswith('IModelDocExtension.')] == cycle + [method] + cycle * 2, 'field setter/readback order')
                setter = calls.index(method)
                getter_end = max(i for i in range(setter) if calls[i].startswith('IModelDocExtension.GetUserPreference'))
                guard_reads(calls[getter_end + 1:setter])
                require(calls.count('IModelDoc2.SetSaveFlag') == int(index == 0), 'explicit dirty setter repeated/missing')
                if index == 0:
                    dirty = calls.index('IModelDoc2.SetSaveFlag')
                    read_end = max(i for i in range(dirty) if calls[i].startswith('IModelDocExtension.GetUserPreference'))
                    guard_reads(calls[read_end + 1:dirty])
                for request in (changed, noop):
                    doc = request['document']
                    require(all(doc[k] == initial[k] for k in ('document_id', 'title', 'path', 'type', 'update_stamp', 'active', 'current'))
                            and doc['modified'] is True, 'target identity/state drift')
                require(conflict['before'] == changed['options'], 'conflict observed another scalar state')
                for label in ('noop', 'conflict'):
                    calls_read = [row['call'] for row in next(blocks)]
                    require([c for c in calls_read if c.startswith('IModelDocExtension.')] == cycle
                            and 'IModelDoc2.SetSaveFlag' not in calls_read, label + ' mutated preferences/dirty')
                field_proofs.append(dict(document_type=kind, field=field, transition=EXPECTED[str(kind)][field],
                                         setter_sequence=block[setter]['sequence'], native_returned=changed['native_returned'],
                                         target=changed['document'], persisted=case['persisted']['options'][field]))
            require([row['call'] for row in next(blocks) if row['call'].startswith('IModelDocExtension.')] == cycle, 'persisted read order')
        require(next(blocks, None) is None, 'unassigned preference operation')
        part = report['cases'][0]
        observed = [json.loads(line) for line in (original / 'calibration/geometry-observations.jsonl').read_text().splitlines()]
        require(observed == part['geometry_checks'], 'JSONL/report raw geometry diverged')
        result.update(run=PIN, native_worker_pid=rows[0]['worker_pid'], native_host_pid=report['host']['process_id'],
                      native_group_seconds=rows[-1]['monotonic_seconds'] - rows[0]['monotonic_seconds'],
                      field_proofs=field_proofs, original_geometry_observations=observed,
                      original_files={str(p.relative_to(original)): digest(p) for p in original.rglob('*') if p.is_file()},
                      guard_evidence='Exact-head healthy-path guard reads plus successful adapter results; no native fault injection.',
                      public_acceptance=False)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.evidence.resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == '__main__':
    main()
