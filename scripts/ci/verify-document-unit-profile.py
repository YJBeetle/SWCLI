"""Public installed-CLI acceptance of units reads/noop/CAS/refusals.

Requires successful native read calibration fixtures and an already owned hidden
daemon. Does not authorize or attempt any changed native preference write.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath
import sys

from swcli.document_unit_profile import validate_snapshot, typed_key
from swcli.result_schemas import validate_operation_result

spec=importlib.util.spec_from_file_location('_unit_profile_public_base',Path(__file__).with_name('verify-modeling.py'))
modeling=importlib.util.module_from_spec(spec);spec.loader.exec_module(modeling)
spec=importlib.util.spec_from_file_location('_unit_profile_durable',Path(__file__).with_name('calibrate-document-unit-profile.py'))
evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)
require=modeling.require

class DurableGate(modeling.ModelingSmoke):
    def checkpoint(self,stage,*,event=None):
        self.record['stage']=stage
        evidence.durable(self.record_path,self.record)


def read(gate,document):
    result=gate.command('document','unit-profile',document=document)
    validate_operation_result('document.unit-profile',result)
    validate_snapshot(result['unit_profile'])
    gate.background(result,document)
    return result


def geometry(gate,document):
    result=gate.command('document','measure',document=document)
    validate_operation_result('document.measure',result)
    metrics=result['metrics']
    require(metrics['solid_body_count']==1,'public fixture must remain one solid')
    for key,value in (('volume_mm3',12000),('surface_area_mm2',3800)):
        require(math.isclose(metrics[key],value,rel_tol=1e-7,abs_tol=1e-5),'public analytic box mismatch: '+key)
    for axis,value in zip(('x','y','z'),(0,0,5)):
        require(math.isclose(metrics['centroid_mm'][axis],value,rel_tol=1e-7,abs_tol=1e-5),'public analytic centroid mismatch: '+axis)
    return metrics


def edit(gate,document,before,*,value,snapshot=None,stamp=None,session=None,lease=None,error=None):
    arguments=['document','unit-profile-set','linear.precision',str(value),'--if-snapshot',json.dumps(before['unit_profile'] if snapshot is None else snapshot,separators=(',',':')),'--if-update-stamp',before['document']['update_stamp'] if stamp is None else stamp]
    if session is None:
        result=gate.write(*arguments,document=document,expected_error=error)
    else:
        result=gate.command(*arguments,document=document,session=session,lease=lease,expected_error=error)
    if error not in ('DocumentLeaseConflict','DocumentUpdateConflict') or 'mutation' in result:
        require(result.get('mutation')==dict(attempted=False,may_have_changed=False),'public units test lacks a zero-mutation receipt')
    if error is None:
        validate_operation_result('document.unit-profile-set',result)
        require(result['changed'] is False and typed_key(result['unit_profile'])==typed_key(before['unit_profile']) and result['document']==before['document'],'same-value request changed complete profile or document state')
    return result


def run(gate,fixtures,prior_pids):
    report=json.loads((fixtures/'report.json').read_text())
    require(report.get('success') is True and report.get('profile')=='units-read-cas-v1' and len(report.get('cases',[]))==3 and all(c.get('success') is True for c in report['cases']),'successful native read calibration required before public acceptance')
    gate.record.update(profile='units-public-read-cas-v1',success=False,full_acceptance_eligible=False,changed_write_acceptance=False,calibration_source_commit=report['source_commit'],calibration_sha256=hashlib.sha256((fixtures/'report.json').read_bytes()).hexdigest(),unit_cases=[])
    host=gate.record['host']=gate.health()['host']
    require(host.get('owned_by_daemon') is True and host.get('visible') is False and host.get('shared_interactive') is False,'public units gate requires an independently owned hidden host')
    require(type(prior_pids) is list and all(type(pid) is int for pid in prior_pids) and host['process_id'] not in prior_pids,'public daemon attached to a preexisting native host')
    gate.require_empty()
    for expected,(kind,suffix) in zip(report['cases'],((1,'SLDPRT'),(2,'SLDASM'),(3,'SLDDRW'))):
        require(expected['document_type']==kind,'native fixture order/type mismatch')
        path=fixtures/('units.'+suffix)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        require(digest==expected['file_sha256'],'native fixture original hash mismatch')
        opened=gate.command('document','open',str(path))
        document=opened['document']['document_id']
        require(opened['api_errors']==opened['api_warnings']==0 and opened['document']['type']==kind and not opened['document']['modified'],'public fixture open failed')
        foreground=gate.create()
        baseline=gate.command('document','inspect',document=document)['document']
        gate.command('document','lease','acquire','--ttl-seconds',600,document=document)
        case=dict(document_type=kind,original_sha256=digest,open=opened,success=False);gate.record['unit_cases'].append(case)
        before=case['read']=read(gate,document)
        require(before['document']==baseline and typed_key(before['unit_profile'])==typed_key(expected['read']['unit_profile']),'public read differs from calibrated source or changed document state')
        if kind==1:case['geometry_before']=geometry(gate,document)
        source=before['unit_profile']['values']['linear.precision']['native_value']
        require(type(source) is int and 0<=source<=8,'native source precision outside bounded noop acceptance')
        value=0 if source!=0 else 8
        case['noop']=edit(gate,document,before,value=source)
        case['lease_refusal']=edit(gate,document,before,value=value,session=gate.session+'-contender',lease='l-not-owned',error='DocumentLeaseConflict')
        case['stamp_refusal']=edit(gate,document,before,value=value,stamp=baseline['update_stamp']+1,error='DocumentUpdateConflict')
        wrong=deepcopy(before['unit_profile']);wrong['linkage']['swUnitsTimeUnits']+=1
        case['cas_refusal']=edit(gate,document,before,value=value,snapshot=wrong,error='DocumentUnitProfileConflict')
        error='UnitProfileCalibrationRequired' if before['unit_profile']['values']['system']['native_value']==4 else 'ValueError'
        case['closed_domain_refusal']=edit(gate,document,before,value=value,error=error)
        after=case['after_refusal']=read(gate,document)
        require(after['document']==baseline and typed_key(after['unit_profile'])==typed_key(before['unit_profile']),'refusal changed state or complete profile')
        copy=gate.directory/('public-units.'+suffix)
        saved=case['save_copy']=gate.write('document','save-as',str(copy),document=document)
        require(saved['api_saved'] is True and saved['save_errors']==0 and saved['save_warnings'] is None and saved['document']['modified'] is False and PureWindowsPath(saved['document']['path'])==PureWindowsPath(str(copy)) and copy.is_file(),'public saved copy failed')
        copy_digest=case['copy_sha256']=hashlib.sha256(copy.read_bytes()).hexdigest()
        gate.close(document)
        reopened=case['reopen']=gate.command('document','open',str(copy),'--read-only')
        fresh=reopened['document']['document_id']
        require(fresh!=document and reopened['read_only'] is True and reopened['api_errors']==reopened['api_warnings']==0 and reopened['document']['modified'] is False,'public readonly reopen failed')
        reopened_foreground=gate.create()
        observed=case['readonly_read']=read(gate,fresh)
        require(typed_key(observed['unit_profile'])==typed_key(before['unit_profile']),'public saved/reopened complete unit profile differs')
        gate.command('document','lease','acquire','--ttl-seconds',600,document=fresh)
        case['readonly_refusal']=edit(gate,fresh,observed,value=value,error='ValueError')
        final=read(gate,fresh)
        require(final['document']==observed['document'] and typed_key(final['unit_profile'])==typed_key(observed['unit_profile']) and hashlib.sha256(copy.read_bytes()).hexdigest()==copy_digest and hashlib.sha256(path.read_bytes()).hexdigest()==digest,'readonly public verification modified profile/state/files')
        if kind==1:
            case['geometry_reopened']=geometry(gate,fresh)
            require(case['geometry_reopened']==case['geometry_before'],'public units sequence changed geometric measurements')
        gate.close(fresh);gate.close(reopened_foreground);gate.close(foreground);gate.require_empty(after_case=suffix)
        case['success']=True;gate.checkpoint('unit-profile-'+suffix+'-verified')
    require(gate.health()['host']==host,'public CLI acceptance replaced its host')
    gate.record.update(success=True,state='completed')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--fixture-dir',type=Path,required=True)
    parser.add_argument('--endpoint',required=True)
    parser.add_argument('--prior-pids',type=Path,required=True)
    args=parser.parse_args(argv)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    gate=DurableGate(directory=args.output_dir.resolve(),host_directory=str(args.output_dir.resolve()),endpoint=args.endpoint,request_timeout_seconds=600)
    gate.record_path=args.output_dir/'public-unit-profile.json'
    gate.checkpoint('initializing')
    failure=None
    try:run(gate,args.fixture_dir.resolve(),json.loads(args.prior_pids.read_text()))
    except BaseException as error:
        failure=error
        gate.record.update(success=False,state='failed',error=dict(type=type(error).__name__,message=str(error)))
    finally:
        try:gate.cleanup()
        except BaseException as error:
            gate.record['cleanup_errors'].append(dict(type=type(error).__name__,message=str(error)))
            if failure is None:failure=error
        if gate.record['cleanup_errors']:gate.record.update(success=False,state='failed')
        try:gate.checkpoint('public-unit-profile-final')
        except BaseException as error:
            if failure is None:failure=error
    if failure is not None:raise failure
    require(not gate.record['cleanup_errors'],'public units cleanup failed')

if __name__=='__main__':main()
