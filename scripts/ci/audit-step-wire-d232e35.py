"""Offline audit of the immutable d232e35 wire diagnostic. No CAD/VM/network."""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HEAD = 'd232e35fabdd2d89fecd8b2f4b90b9485d7425e3'
REPORT_SHA = '4e8332dd621a389268e92ecb4cac317acb77a930b314c0b396662f9eaa10ee4e'
ZIP_SHA = 'de52dbe3ca79c0a032ce6b488a2477859796c209234ee58e1bb5b43afff9707e'
FAILURE = 'reference-curve profile unexpectedly produced sketch geometry'
NAMES = ('swMultiCAD_Enable3DInterconnect', 'swImportSolidSurface', 'swImportFreeCurves',
         'swImportNeutral_SolidandSurface', 'swImportNeutral_FreeCurvesAndPoints',
         'swImportStepConfigData', 'swImportCurvePreference', 'swImportNeutral_CurvesAndPointsOption')
BEFORE = dict(zip(NAMES, (True, True, False, True, False, False, 0, 0)))
GENERAL = {**BEFORE, NAMES[0]: False, NAMES[2]: True, NAMES[6]: 1}
CANDIDATE = {**GENERAL, NAMES[4]: True}
OWNED = [NAMES[i] for i in (0, 2, 6, 4)]


def checked(value, message):
    if not value:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(bundle, source_zip, input_file):
    report_raw = (bundle / 'report.json').read_bytes()
    checked(sha(report_raw) == REPORT_SHA, 'Original report digest differs')
    r = json.loads(report_raw)
    pre = json.loads((bundle / 'preflight.json').read_text())
    checked(r['success'] is False and len(r['cases']) == 1, 'Original result/plan differs')
    checked(not r['production_public_acceptance'] and not r['full_acceptance_eligible'], 'Acceptance falsely claimed')
    checked(r['diagnostic_case'] == 'step-wire-import-once' and r['max_loadfile4'] == 1, 'Diagnostic identity differs')
    checked(r['host'] == dict(process_id=2568, revision='33.5.0', visible=False), 'Host differs')
    checked(r['pywin32'] == '312' and r['cleanup_errors'] == [] and r['nohost_before'] == r['remaining_native_pids'] == [], 'Runtime/cleanup differs')
    c = r['cases'][0]
    checked(not c['success'] and c['first_error']['message'] == r['failure']['message'] == FAILURE, 'First error differs')
    checked(c['load_return'] == dict(state='returned', document_returned=True, errors=0, arg_string='r',
            import_data='same factory object', possible_document_mutation=True, python_type='win32com.client.CDispatch'), 'Native return differs')
    checked(c['IImportStepData.QueryInterface'] == dict(status='observed', value=True), 'QI differs')
    checked(c['MapConfigurationData'] == dict(status='observed', value=False), 'Map getter differs')
    checked(c['imported-document-type']['value'] == 1 and c['owned-import-count']['value'] == 1, 'Part/catalog differs')
    checked(r['input'] == r['input_final'] == pre['input'] == c['input_before'], 'Input metadata checkpoints differ')
    checked(r['input']['sha256'] == sha(input_file.read_bytes()) == '3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90', 'Actual input bytes differ')
    checked(r['input']['readonly'] and r['input']['metadata']['attributes'] == 33 and r['input']['metadata']['size'] == 10595, 'Input readonly/size differs')
    checked(r['constants']['swImportNeutralCurvesAndPointsOptions_As3DCurves'] == 1 and
            r['constants']['swImportNeutralCurvesAndPointsOptions_AsSketches'] == 0, 'Installed enums differ')
    checked(r['constants']['step_interface'] == dict(name='IImportStepData', iid='{AD749A73-9AA2-4A3E-BCA5-8FC012114BB0}', wrapper='IUnknown'), 'Interface differs')
    for name, digest in {'swconst.tlb':'95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6',
                         'sldworks.tlb':'585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159'}.items():
        checked(r['libraries'][name]['sha256'] == digest, 'Installed library digest differs')
    checked(sha(source_zip.read_bytes()) == ZIP_SHA, 'Source archive differs')
    archive = subprocess.run(['git','archive','--format=zip',HEAD], cwd=ROOT, capture_output=True, check=True).stdout
    with zipfile.ZipFile(source_zip) as actual, zipfile.ZipFile(io.BytesIO(archive)) as expected:
        members = {x.filename:actual.read(x) for x in actual.infolist() if not x.is_dir()}
        checked(len(members) == 184 and len(members) == len([x for x in actual.infolist() if not x.is_dir()]), 'Runtime member count/duplicates differ')
        checked(all(value == expected.read(name) for name,value in members.items()), 'Runtime member differs from reviewed commit')
        for name,digest in r['code'].items():
            checked(sha(members[name.replace('\\','/')]) == digest, 'Loaded code hash differs')
    g = c['geometry'];raw = g['raw_observation']
    checked(g['status'] == 'unavailable' and g['value'] is None and raw['complete'] is False, 'Failed geometry promoted')
    features = raw['feature_inventory'];ids = [x['feature_id'] for x in features]
    checked(len(features) == 18 and len(set(ids)) == 18, 'Feature inventory differs')
    sketches = [x for x in features if x['kind'] == '3DProfileFeature']
    checked([x['feature_id'] for x in sketches] == raw['representation_mismatches'] == [17,18], 'Representation differs')
    checked([len(x['lengths_mm']) for x in sketches] == [6,6], 'Sketch segment grouping differs')
    checked(not any(x['lengths_mm'] for x in features if x not in sketches), 'Unexpected non-sketch geometry')
    lengths = sorted(v for x in sketches for v in x['lengths_mm'])
    checked(raw['segment_count'] == len(lengths) == 12 and lengths == raw['lengths_mm'], 'Partial count/vector differs')
    checked(all(math.isfinite(v) and math.isclose(v,w,rel_tol=0,abs_tol=1e-9) for v,w in zip(lengths,[10]*4+[30]*4+[40]*4)), 'Analytic partial vector differs')
    checked(math.isclose(sum(lengths),320,rel_tol=1e-7,abs_tol=1e-5) and sum(lengths) == raw['total_length_mm'], 'Partial length differs')
    p = c['preferences']
    checked(p['snapshot'] == p['after'] == BEFORE and p['ci_general_readback'] == GENERAL and p['candidate_readback'] == CANDIDATE, 'Profile/restore differs')
    checked(p['restored'] is True and p['restore_errors'] == [], 'Preference cleanup failed')
    checked([x['name'] for x in p['writes']] == OWNED and [x['name'] for x in p['restore']] == OWNED[::-1], 'Owned writes/restore order differs')
    for row in p['writes'] + p['restore']:
        checked(row['status'] == 'verified' and row['possible_mutation'], 'Setter/readback not verified')
        checked(row['returned'] is (True if row['name'] == NAMES[6] else None), 'Setter native return differs')
    expected = dict(BEFORE);wi = 0
    for stage in p['stages']:
        checked(stage['status'] == 'observed', 'Unknown preference stage')
        if stage['label'] == 'readback-after-set':
            row = p['writes'][wi];expected[row['name']] = row['requested'];wi += 1
            checked(row['readback'] == expected, 'Setter full readback differs')
        if stage['label'] == 'verify-full-original-restored':expected = dict(BEFORE)
        checked(stage['values'] == expected, 'Full-vector CAS stage differs')
    checked(wi == 4 and len(p['reads']) == 128 and all(x['status'] == 'observed' for x in p['reads']), 'Read journal differs')
    for row in p['restore']:
        checked(row['original'] == row['readback'] == BEFORE[row['name']] and row['current'] == row['requested'] == CANDIDATE[row['name']], 'Owned restore CAS differs')
    counts = {};sequences = {};errors = {}
    for filename in ('trace.jsonl','observation-trace.jsonl'):
        rows = [json.loads(line) for line in (bundle/filename).read_text().splitlines()]
        stack = [];begins = Counter();bad = [];sequence = []
        for row in rows:
            if row['phase'] == 'begin':
                stack.append(row['call']);begins[row['call']] += 1;sequence.append(row['call'])
            else:
                checked(row['phase'] in ('end','error') and stack and stack.pop() == row['call'], 'Trace pairing differs')
                if row['phase'] == 'error':bad.append(row)
        checked(not stack, 'Incomplete trace')
        counts[filename] = dict(begins);errors[filename] = bad;sequences[filename] = sequence
    main = counts['trace.jsonl'];obs = counts['observation-trace.jsonl'];seq = sequences['trace.jsonl']
    checked(errors['trace.jsonl'] == [dict(call='read-imported-wireframe',phase='error',error=FAILURE)] and errors['observation-trace.jsonl'] == [], 'Trace first error differs')
    for name in ('acquire-owned-host','GetImportFileData','IImportStepData.QueryInterface','MapConfigurationData','LoadFile4','read-imported-wireframe','CloseDoc','ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'):
        checked(main[name] == 1, 'Call count differs: '+name)
    checked(seq[-5:] == ['CloseDoc','ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'], 'Owned cleanup order differs')
    checked(obs['GetSketchSegments'] == 2 and obs['GetLength'] == 12, 'Native sketch read counts differ')
    checked([x.removeprefix('set-owned-option.') for x in seq if x.startswith('set-owned-option.')] == OWNED, 'Trace setters differ')
    checked([x.removeprefix('restore-owned-option.') for x in seq if x.startswith('restore-owned-option.')] == OWNED[::-1], 'Trace restores differ')
    for prefix in ('OpenDoc','New','Save','Select','ClearSelection','Export','SetUserPreference','GetImportFileData','LoadFile4'):
        for filename,sequence in sequences.items():
            allowed = {'GetImportFileData','LoadFile4'} if filename == 'trace.jsonl' else set()
            checked(not any(x.startswith(prefix) and x not in allowed for x in sequence), 'Unexpected API: '+prefix)
    checked(not any((bundle/name).exists() for name in ('timeout.json','partial-acquisition-trace.jsonl','partial-acquire-first-failure.json')), 'Timeout/partial activation present')
    return dict(source_commit=HEAD,report_sha256=REPORT_SHA,source_archive_sha256=ZIP_SHA,
        source_archive_scope='184 selected runtime files, all equal reviewed commit; not whole repository',
        original_files_sha256={x.name:sha(x.read_bytes()) for x in sorted(bundle.iterdir()) if x.is_file()},
        host=r['host'],python=r['python'],pywin32=r['pywin32'],libraries=r['libraries'],input=r['input'],
        input_metadata_checkpoints_identical=True,first_error=FAILURE,load_return=c['load_return'],
        geometry_status='unavailable',geometry_value=None,raw_feature_count=18,raw_sketch_ids=[17,18],
        raw_sketch_segment_counts=[6,6],raw_lengths_mm=lengths,raw_total_length_mm=sum(lengths),
        strict_representation_passed=False,preferences_before=BEFORE,ci_general=GENERAL,candidate=CANDIDATE,
        owned_write_order=OWNED,owned_restore_order=OWNED[::-1],full_original_restored=True,
        call_counts=counts,cleanup_errors=[],nohost_before=[],remaining_native_pids=[],
        native_acceptance=False,causal_fix_or_precedence_proven=False,
        limitation='Local result cannot causally explain old hosted CI None/errors1; no same-environment baseline replay')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--source-zip',type=Path,required=True)
    parser.add_argument('--input-file',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = audit(args.bundle,args.source_zip,args.input_file)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Offline original audit PASS; native diagnostic FAILED on representation; no acceptance/causal claim')


if __name__ == '__main__':
    main()
