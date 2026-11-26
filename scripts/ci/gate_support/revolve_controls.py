"""Preregistered refusal and post-creation failure controls for the 90-degree case."""
from copy import deepcopy
import json

from .revolve_direction import CASE, PLANES, case_name, finish_run, require, require_native_ok, validate_reopened
from swcli.revolve_geometry import sector_expectation, verify_sector_metrics

REFUSALS = (
    ('public-closed-angle', 'RevolveNotCalibrated'),
    ('public-stale-stamp', 'DocumentUpdateConflict'),
    ('public-wrong-lease', 'DocumentLeaseConflict'),
    ('public-missing-sketch', 'SketchNotFound'),
    ('private-stale-profile', 'RevolveProfileConflict'),
    ('private-read-only', 'DocumentReadOnly'),
    ('private-existing-solid', 'UnsupportedRevolveBodyScope'),
    ('private-offset-plane', 'UnsupportedRevolvePlane'),
    ('private-reversed-axis', 'RevolveAxisMismatch'),
)
PARTIAL = 'partial-observation-failure'
INJECTED_MESSAGE = 'injected 90-degree definition observation failure after native creation'
ZERO_MUTATION = dict(attempted=False, creation_returned=False, may_have_changed=False)
PARTIAL_MUTATION = dict(attempted=True, creation_returned=True, may_have_changed=True)


def control_plan():
    return [name for name, _ in REFUSALS] + [PARTIAL]


def verify_refusal(row, expected_error):
    before = row['before']
    require(before['foreground_same'] is True and before['editing'] is False and before['selected'] == 0,
            "refusal fixture is not the exact active, cleared, non-editing part")
    require(before['read_only'] is (row['name'] == 'private-read-only')
            and before['body_count'] == (1 if row['name'] == 'private-existing-solid' else 0),
            "refusal fixture does not match the preregistered read-only/body scope")
    require(before == row['after'], "refusal changed live document or saved bytes")
    require(row['feature_handle_retained'] is False, "refusal returned a created feature")
    require(row['receipt']['ok'] is False, "expected refusal unexpectedly succeeded")
    require(row['receipt']['error']['type'] == expected_error,
            row['receipt']['error'].get('message', "unexpected refusal error"))
    if row['name'] in ('public-stale-stamp', 'public-wrong-lease', 'public-missing-sketch'):
        require(row['dispatcher_exception'] is True, "dispatcher guard did not precede candidate routing")
    else:
        require(row['receipt']['mutation'] == ZERO_MUTATION, "refusal mutation flags are not all false")
        require(not row['receipt'].get('cleanup_errors'), "refusal cleanup failed")


def require_clean_control_save(saved, stage):
    receipt = saved['save']
    require_native_ok(receipt, stage)
    require(receipt.get('save_attempted') is True and receipt.get('api_saved') is True,
            f"{stage} lacks a successful native SaveAs3 call")
    for key in ('save_errors', 'save_warnings'):
        value = receipt.get(key)
        require(type(value) is int and value == 0, f"{stage} returned {key}={value!r}")
    require(saved['file_size_bytes'] > 0, f"{stage} produced an empty native file")


def verify_partial_receipt(partial):
    created = partial['creation']
    require(created['ok'] is False and partial['feature_handle_retained'] is True,
            "injected observation failure lost the exact feature handle or unexpectedly passed")
    require(created['error'] == dict(type='RuntimeError', message=INJECTED_MESSAGE),
            "post-creation first failure differs from the preregistered injection")
    require(created['mutation'] == PARTIAL_MUTATION and not created['cleanup_errors'],
            "post-creation mutation receipt is incomplete or cleanup failed")


def verify_control_trace(path):
    calls = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if '"event": "swcli.native-call"' in line:
                calls.append(json.loads(line))
    refusal_names = {name for name, _ in REFUSALS}
    for name in refusal_names | {case_name(CASE)}:
        phases = [event['phase'] for event in calls if event['request_id'] == name and event['stage'] == 'operation']
        require(phases == ['begin', 'end'], f"incomplete native trace for {name}")
    require(not any(event['request_id'] in refusal_names and event['call'] in ('Sketch.Select2', 'Axis.Select4')
                    for event in calls), 'a refusal reached native revolve selection')
    creations = [(event['request_id'], event['phase']) for event in calls if event['call'] == 'FeatureRevolve2']
    require(creations == [(case_name(CASE), 'begin'), (case_name(CASE), 'end')],
            'controls must trace exactly one native creation in the partial fault case')
    injection = [(event['phase'],event.get('exception_type')) for event in calls
                 if event['request_id'] == case_name(CASE) and event['call'] == 'read-definition']
    require(injection == [('begin', None), ('error', 'RuntimeError')],
            'partial fault must trace the preregistered read-definition exception')


def run_controls(backend, evidence, source_commit):
    report = dict(success=False, profile='internal-revolve-direction-controls-v1', source_commit=source_commit,
        public_acceptance=False, full_acceptance_eligible=False, public_write_gate='calibrated-scope-only', matrix_enabled=False,
        planned_controls=control_plan(), controls=[], native_timeout_seconds=600, group_timeout_seconds=1800,
        case=deepcopy(CASE), cleanup_errors=[], evidence_errors=[])
    backend.call = evidence.call
    active = None

    def observe(row, key, operation):
        def invoke():
            row[key] = operation()
            return row[key]
        value = evidence.call(key, invoke)
        evidence.save(report)
        return value

    def refuse(row, expected_error):
        name = row['name']
        row['fixture'] = {}
        evidence.call('fixture', lambda: backend.prepare_refusal(name, deepcopy(CASE), row['fixture']))
        evidence.save(report)
        observe(row, 'before', backend.snapshot)
        evidence.call('request', lambda: backend.refusal(name, deepcopy(CASE), row))
        evidence.save(report)
        observe(row, 'after', backend.snapshot)
        verify_refusal(row, expected_error)
        evidence.call('close-fixture', backend.close)

    def partial(row):
        case = deepcopy(CASE)
        fixture = observe(row, 'fixture', lambda: backend.fixture(case))
        evidence.call('injected-observation-failure', lambda: backend.create_partial(case, row))
        evidence.save(report)
        verify_partial_receipt(row)
        expected = sector_expectation(case['bounds_mm'], PLANES['front'], 90, rotation_sign=-1)
        preserved = observe(row, 'preserved', backend.preserved_partial)
        require(preserved['exact_handle_matches'] is True and preserved['body_count'] == 1
                and preserved['diagnostics']['healthy'] is True and preserved['diagnostics']['truncated'] is False,
                "partial live model lost the exact feature or healthy body")
        require_native_ok(preserved['measurement'], 'partial live measurement')
        verify_sector_metrics(preserved['measurement']['metrics'], expected)
        saved = observe(row, 'saved', lambda: backend.save(case, filename='partial-observation-failure.SLDPRT'))
        require_clean_control_save(saved, 'partial save')
        evidence.call('close-before-reopen', backend.close)
        row['reopened'] = {}
        evidence.call('reopen-read-only', lambda: backend.reopen(saved, row['creation'], case, row['reopened']))
        evidence.save(report)
        validate_reopened(row['reopened'], saved, row['creation'], case, expected, fixture['configuration'])
        evidence.call('close-read-only', backend.close)

    try:
        evidence.save(report)
        observe(report, 'host', backend.start)
        for name, expected in (*REFUSALS, (PARTIAL, None)):
            active = dict(name=name, success=False)
            report['controls'].append(active)
            evidence.save(report)
            if name == PARTIAL:
                evidence.call(name, lambda: partial(active))
            else:
                evidence.call(name, lambda: refuse(active, expected))
            active['success'] = True
            evidence.save(report)
        report['success'] = True
    except BaseException as error:
        report['failure'] = dict(type=getattr(error,'code',type(error).__name__),message=str(error),
            boundary_evidence_error=getattr(error,'boundary_evidence_error',None))
        if active is not None:
            report['failed_control'] = active['name']
    finally:
        finish_run(backend, evidence, report)
    return report
