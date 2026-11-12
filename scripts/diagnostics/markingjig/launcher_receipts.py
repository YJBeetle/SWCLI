"""OS-only private-launcher receipts. No COM, VM control, or native work at import.
Independent postchecks preserve a candidate's fatal error and attempt every check once.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import traceback


def single_case(report):
    cases=report['cases']
    if type(cases) is not list or len(cases)>1 or (cases and type(cases[0]) is not dict):
        raise RuntimeError('unexpected diagnostic case structure')
    return cases[0] if cases else None


def postchecks(record, steps, persist=lambda _:None):
    errors=record.setdefault('secondary_errors',[])
    def failed(stage,error):
        errors.append(dict(stage=stage,type=type(error).__name__,error=str(error),
                           traceback=''.join(traceback.format_exception(type(error),error,error.__traceback__))))
    for stage,function in steps:
        try:function()
        except BaseException as error:failed(stage,error)
        finally:
            # The child native failure is authoritative when it is available.
            # Neither cleanup nor persistence errors replace it or first_error.
            record['primary_failure']=deepcopy(record.get('candidate_failure') or record.get('first_error'))
            try:persist(record)
            except BaseException as error:failed('persist-after-'+stage,error)
    return not errors


def read_native_report(record,path):
    path=Path(path)
    if not path.exists():
        record['native_report_available']=False
        return None
    raw=path.read_bytes();report=json.loads(raw)
    record.update(native_report_available=True,native_report_sha256=hashlib.sha256(raw).hexdigest(),
                  native_report_success=report.get('success'),candidate_failure=deepcopy(report.get('failure')),
                  native_report_case_count=len(report['cases']) if type(report.get('cases')) is list else None)
    # Store the original child report, without inventing a case or success state.
    return report


def capture_post_inputs(record,working,phases):
    if working is None:raise RuntimeError('working copy not prepared; post-input raw proof unavailable')
    frame=record['private_source_after_owned_cleanup_frame']={}
    phases.capture_frame(working,'after-candidate-worker-return',frame)


def compare_post_inputs(record,report,phases):
    after=record['private_source_after_owned_cleanup_frame']
    if after.get('complete') is not True:raise RuntimeError('incomplete post-input raw frame')
    for name,before in record['private_source_before'].items():
        current=after['stable'][name]
        if (current['sha256'],current['size_bytes'])!=(before['sha256'],before['size_bytes']):
            raise RuntimeError('whole-window private content changed: '+name)
        for channel in ('path_before','handle_before','handle_after','path_after'):
            if any(current[channel][k]!=before[channel][k] for k in ('st_dev','st_ino')):
                raise RuntimeError('whole-window private identity changed: '+name)
    baseline=record['private_source_pre_CAD_frame']
    case=single_case(report) if report is not None else None
    frames=case.get('file_phases',{}).get('frames',[]) if case is not None else []
    complete=[row for row in frames if row.get('complete') and 'stable' in row and 'raw' in row]
    if complete:baseline=complete[-1]
    record['postcleanup_comparison_baseline_label']=baseline['label']
    record['postcleanup_raw_changes']=phases.changes(phases.PhaseGuard.metadata(baseline),phases.PhaseGuard.metadata(after))
    record['postcleanup_stability_changes']=phases.changes(phases.PhaseGuard.metadata(baseline,projected=True),phases.PhaseGuard.metadata(after,projected=True))
    if record['postcleanup_stability_changes']:raise RuntimeError('private metadata changed after candidate worker return')
    record['private_source_postcleanup_proof_complete']=True


def input_hash_postcheck(record,selected,digest):
    hashes=record['copy_hashes_after']={};sizes=record['copy_sizes_after']={};errors=[];mismatches=[]
    copies=record['copies']
    for row in copies:
        name=row['name'];path=Path(row['destination'])
        try:
            hashes[name]=digest(path);sizes[name]=path.stat().st_size
            if (hashes[name],sizes[name])!=(row['sha256'],row['size_bytes']):mismatches.append(name)
        except BaseException as error:errors.append(dict(name=name,type=type(error).__name__,error=str(error)))
    missing=sorted(set(selected)-set(hashes))
    record.update(copy_hash_errors=errors,copy_hash_mismatches=mismatches,copy_hash_missing_names=missing,
                  copy_hash_postcheck_complete=bool(selected) and not errors and not mismatches and not missing and len(copies)==len(selected)==len(hashes))
    if not record['copy_hash_postcheck_complete']:raise RuntimeError('private input hash postcheck incomplete or changed')


def code_hash_postcheck(record,code,expected,digest):
    hashes=record['code_hashes_after']={};errors=[];mismatches=[]
    for name,pinned in expected.items():
        try:
            hashes[name]=digest(Path(code)/name)
            if hashes[name]!=pinned:mismatches.append(name)
        except BaseException as error:errors.append(dict(name=name,type=type(error).__name__,error=str(error)))
    record.update(code_hash_errors=errors,code_hash_mismatches=mismatches,
                  code_hash_postcheck_complete=bool(expected) and not errors and not mismatches and len(hashes)==len(expected))
    if not record['code_hash_postcheck_complete']:raise RuntimeError('candidate code hash postcheck incomplete or changed')


def launcher_success(record):
    return (record.get('candidate_exit')==0 and record.get('first_error') is None
            and record.get('candidate_failure') is None and record.get('native_report_success') is True
            and record.get('native_report_case_count')==1 and not record.get('secondary_errors')
            and not record.get('cleanup_errors') and record.get('native_pids_after')==[]
            and record.get('native_pids_after_postcleanup_OS')==[]
            and record.get('private_source_postcleanup_proof_complete') is True
            and record.get('copy_hash_postcheck_complete') is True
            and record.get('code_hash_postcheck_complete') is True)
