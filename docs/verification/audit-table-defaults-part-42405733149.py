"""Offline verification of the failed strict part pre-write control original."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

RUN = 42405733149
HEAD = '6396034fe941b28d90ced2b941ae0d6c26907be9'
ARTIFACT = 13588160547
ZIP_SHA256 = '3a1d78b525c62488eb75d82324dd9551d8700333d74f0e2a623850e586876d92'
FAILURE = 'table fixture exact geometry comparison failed at before-first-table-write'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def audit(evidence):
    run = json.loads((evidence / 'run.json').read_text())
    artifact = json.loads((evidence / 'artifact.json').read_text())
    require((run['id'], run['head_sha'], run['head_branch'], run['event'], run['status'], run['conclusion']) ==
            (RUN, HEAD, 'codex/docprops-table-defaults', 'workflow_dispatch', 'completed', 'failure'), 'wrong run/head/outcome')
    require((artifact['id'], artifact['name'], artifact['workflow_run']['id'], artifact['digest']) ==
            (ARTIFACT, 'table-defaults-internal-42405733149-1', RUN, 'sha256:' + ZIP_SHA256), 'wrong official artifact')
    original = evidence / 'original.zip'
    require(sha256(original.read_bytes()) == ZIP_SHA256, 'original ZIP digest mismatch')
    with zipfile.ZipFile(original) as archive:
        names = archive.namelist()
        expected = {'calibration/annotations.SLDPRT', 'calibration/geometry-observations.jsonl',
                    'calibration/report.json', 'calibration/trace.jsonl', 'worker.native.stderr.jsonl',
                    'worker.stdout.log', 'wrapper-result.json'}
        require(set(names) == expected and len(names) == len(expected), 'original file plan differs')
        files = {name: archive.read(name) for name in names}
    report = json.loads(files['calibration/report.json'])
    require(report['success'] is False and report['full_acceptance_eligible'] is False
            and report['requested_document_types'] == [1] and len(report['cases']) == 1
            and report['cleanup_errors'] == [] and report['failure']['type'] == 'RuntimeError'
            and report['failure']['message'] == FAILURE, 'wrong first failure or incomplete cleanup')
    case = report['cases'][0]
    require(case['document_type'] == 1 and case['success'] is False and case['writes'] == [], 'candidate setter was entered')
    measurement = case['geometry_before_table_write_measurement']
    require(measurement['ok'] is True and measurement['method'] == 'native-body-mass-properties'
            and len(measurement['bodies']) == 1 and case['geometry_before_table_write_context_unchanged'] is True,
            'measurement/context failed before exact comparison')
    require(case['geometry_before_table_write_context']['state'] == [1, 163, False, 'Default']
            and case['geometry_before_table_write_context']['foreground_state'] == [1, 159, False, 'Default'],
            'unexpected target/foreground context')
    before, after = case['geometry_reopened'], measurement['metrics']
    observations = [json.loads(line) for line in files['calibration/geometry-observations.jsonl'].decode().splitlines()]
    require(observations == case['geometry_checks'] == [dict(field='before-first-table-write',
            before=before, after=after, exact_equal=False)], 'original exact operands differ')
    require(before != after and before['volume_mm3'] == after['volume_mm3'] == 11999.999999999998
            and before['surface_area_mm2'] == after['surface_area_mm2'] == 3799.9999999999995
            and before['solid_body_count'] == after['solid_body_count'] == 1, 'unexpected count/volume/area')
    require(before['centroid_mm'] == dict(x=-7.058607893785837e-16, y=6.286572655403011e-16, z=5.0)
            and after['centroid_mm'] == dict(x=-7.058607893785837e-16, y=8.271806125530278e-16, z=5.0),
            'unexpected exact centroid values')
    require(sha256(files['calibration/annotations.SLDPRT']) == case['file_sha256'], 'original fixture hash changed')
    stages = [json.loads(line) for line in files['calibration/trace.jsonl'].decode().splitlines()]
    failures = [row for row in stages if row['phase'] == 'error']
    require(failures == [dict(call='verify-part-before-first-table-write', phase='error', error=FAILURE)], 'first stage differs')
    require(not any(row['call'].startswith('internal-table-write:') for row in stages), 'candidate table write stage was entered')
    stage_counts = Counter(row['call'] for row in stages if row['phase'] == 'begin')
    require(stage_counts['acquire-owned-host'] == stage_counts['ExitApp'] == stage_counts['WaitForOwnedProcess'] == 1,
            'owned host lifecycle repeated or incomplete')
    require(any(row['call'] == 'WaitForOwnedProcess' and row['phase'] == 'end' for row in stages), 'owned process exit not confirmed')
    rows = [json.loads(line) for line in files['worker.native.stderr.jsonl'].decode().splitlines()]
    rows = [row for row in rows if row.get('event') == 'swcli.native-call']
    workers = {row['worker_pid'] for row in rows}
    require(len(workers) == 1 and all(row['request_id'] == 'table-defaults-calibration'
            and row['operation'] == 'internal.table-defaults' for row in rows), 'native ownership differs')
    stack, sequence = [], 0
    for row in rows:
        if row['phase'] == 'begin':
            require(row['sequence'] == sequence, 'native begin repeated/reordered')
            sequence += 1
            stack.append(row)
        else:
            require(row['phase'] == 'end' and stack, 'native call failed or has no matching begin')
            begin = stack.pop()
            require((begin['sequence'], begin['call']) == (row['sequence'], row['call']), 'native pair mismatch')
            require(0 <= row['monotonic_seconds'] - begin['monotonic_seconds'] <= 600, 'native call exceeded bound')
    require(not stack and rows[-1]['sequence'] == 0, 'native operation incomplete')
    counts = Counter(row['call'] for row in rows if row['phase'] == 'begin')
    setters = sum(value for name, value in counts.items() if name.startswith('IModelDocExtension.SetUserPreference'))
    getters = sum(value for name, value in counts.items() if name.startswith('IModelDocExtension.GetUserPreference'))
    require(setters == 0 and getters == 3 and counts['IModelDoc2.SetSaveFlag'] == 0, 'table/dirty count differs')
    globals_set = [(index, row['call']) for index, row in enumerate(rows)
                   if row['phase'] == 'begin' and row['call'].startswith(('SldWorks.SetUserPreference', 'ISldWorks.SetUserPreference'))]
    first_read = next(index for index, row in enumerate(rows)
                      if row['phase'] == 'begin' and row['call'].startswith('IModelDocExtension.GetUserPreference'))
    require(len(globals_set) == 2 and all(index < first_read and name == 'SldWorks.SetUserPreferenceToggle(swSketchInference)'
                                        for index, name in globals_set), 'unexpected global preference writes')
    wrapper = json.loads(files['wrapper-result.json'].decode('utf-8-sig'))
    require(wrapper == dict(success=False, worker_exit_code=1, native_seconds=600, group_seconds=1800), 'wrong wrapper exit receipt')
    return dict(audit_passed=True, calibration_success=False, blocked=True, run=RUN, head=HEAD, artifact_id=ARTIFACT,
                original_zip=str(original.resolve()), zip_sha256=ZIP_SHA256, failure_phase='before-first-table-write',
                table_setters=setters, table_getters=getters, explicit_dirty_setters=0, fixture_sketch_inference_setters=2,
                geometry_created=case['geometry'], geometry_readonly=before, geometry_writable_before_first_setter=after,
                centroid_y_delta_mm=after['centroid_mm']['y'] - before['centroid_mm']['y'],
                context_unchanged=True, native_api_errors=0, owned_cleanup_completed=True,
                original_file_sha256={name: sha256(content) for name, content in sorted(files.items())})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.evidence), indent=2))
