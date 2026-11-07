"""Public finite changed-write acceptance; never derives or enables a write domain."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath

from swcli import document_unit_profile as catalog
from swcli.result_schemas import validate_operation_result

spec=importlib.util.spec_from_file_location('_unit_write_public_base',Path(__file__).with_name('verify-document-unit-profile.py'))
public=importlib.util.module_from_spec(spec);spec.loader.exec_module(public)
require=public.require


def domain(before, field, value):
    return (before['document_type'],catalog.fingerprint(before),field,catalog.target(field,value))


def validate_step(step,kind):
    require(step.get('success') is True,'incomplete native write step')
    before=catalog.validate_snapshot(step['before']);after=catalog.validate_snapshot(step['after'])
    field,value=step['field'],step['value']
    key=domain(before,field,value)
    require(before['document_type']==after['document_type']==kind
            and before['values'][field]['native_value']!=key[-1]
            and key[1]==step['before_fingerprint']
            and catalog.fingerprint(after)==step['after_fingerprint']
            and key in catalog.CALIBRATED_UNIT_WRITES,
            'public write source/target/type has no manually reviewed exact domain')
    if field=='system':
        catalog.require_system_source(before,key[-1])
        catalog.verify_system_after(before,after,key[-1],catalog.calibrated_system_result(key))
    else:
        catalog.require_scalar_source(before,field)
        catalog.verify_scalar_after(before,after,field,key[-1])
    require(step['result'].get('ok') is True and step['result'].get('native_return_value') is True
            and step['result'].get('changed') is True
            and step['result'].get('mutation')==dict(attempted=True,may_have_changed=True)
            and catalog.typed_key(step['result']['before'])==catalog.typed_key(before)
            and catalog.typed_key(step['result']['unit_profile'])==catalog.typed_key(after)
            and catalog.typed_key(step['readonly_profile'])==catalog.typed_key(after),
            'calibration write receipt/persistence differs from its reviewed transition')
    return key


def require_complete_case(case):
    initial=catalog.validate_snapshot(case['initial_profile'])
    source=initial['values']['system']['native_value']
    require(source in catalog.SYSTEMS.values(),'unknown native initial system')
    preparation=[] if source==4 else [4] if source==5 else [5,4]
    scalar_expected={(field,catalog.target(field,value)) for field in catalog.FIELDS if field!='system'
                     for value in catalog.FIELDS[field].get('targets',tuple(range(9)))}
    scalar_seen=[];system_seen=[];prior=initial;phase='preparation';prepared=[]
    for step in case['write_steps']:
        require(catalog.typed_key(step['before'])==catalog.typed_key(prior),'native step source chain drifted')
        role=step['role'];field=step['field'];target=catalog.target(field,step['value'])
        if role=='explicit-custom-preparation':
            require(phase=='preparation' and field=='system','unexpected Custom preparation phase')
            prepared.append(target)
        elif role=='scalar':
            require(phase in ('preparation','scalar') and field!='system','unexpected scalar phase')
            phase='scalar';scalar_seen.append((field,target))
        elif role=='system-spoke':
            require(phase in ('scalar','system') and field=='system','unexpected system phase')
            phase='system';system_seen.append((step['before']['values']['system']['native_value'],target))
        else:raise RuntimeError('unexpected native write role')
        prior=step['after']
    require(prepared==preparation,'observed initial system preparation is missing or normalized away')
    require(len(scalar_seen)==len(scalar_expected) and set(scalar_seen)==scalar_expected,'native scalar candidates are missing/duplicated')
    spokes={(5,code) for code in (1,2,3,4)}|{(code,5) for code in (1,2,3,4)}
    require(len(system_seen)==8 and set(system_seen)==spokes,'native system directions are missing/duplicated')


def file_in_fixture(fixtures,relative,digest):
    path=(fixtures/relative).resolve()
    require(path.is_relative_to(fixtures.resolve()) and path.is_file(), 'native fixture path escapes or is missing')
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'native write fixture hash mismatch')
    return path


def edit(gate,document,before,field,value,*,changed=False,after=None,error=None,stamp=None,snapshot=None,session=None):
    args=['document','unit-profile-set',field,str(value),'--if-snapshot',json.dumps(before['unit_profile'] if snapshot is None else snapshot,separators=(',',':')),
          '--if-update-stamp',before['document']['update_stamp'] if stamp is None else stamp]
    if session is None:result=gate.write(*args,document=document,expected_error=error)
    else:result=gate.command(*args,document=document,session=session,lease=gate.leases[document],expected_error=error)
    if error is not None:
        if error not in ('DocumentLeaseConflict','DocumentUpdateConflict') or 'mutation' in result:
            require(result.get('mutation')==dict(attempted=False,may_have_changed=False),'refused unit write lacks zero-mutation receipt')
        return result
    validate_operation_result('document.unit-profile-set',result)
    require(result['changed'] is changed
            and result['mutation']==dict(attempted=changed,may_have_changed=changed)
            and catalog.typed_key(result['before'])==catalog.typed_key(before['unit_profile']),
            'public unit write/noop changed flag or source differs')
    if changed:
        require(result.get('native_return_value') is True
                and catalog.typed_key(result['unit_profile'])==catalog.typed_key(after)
                and result['document']['modified'] is True
                and {k:v for k,v in result['document'].items() if k not in ('update_stamp','modified')}
                    =={k:v for k,v in before['document'].items() if k not in ('update_stamp','modified')},
                'public changed write differs from calibrated result or identity/context')
    else:
        require(result['document']==before['document']
                and catalog.typed_key(result['unit_profile'])==catalog.typed_key(before['unit_profile']),
                'public noop changed exact state/profile')
    gate.background(result,document)
    return result


def uncalibrated_custom_target(before):
    if before['values']['system']['native_value']!=4:return None
    for field in catalog.FIELDS:
        if field=='system':continue
        for value in catalog.FIELDS[field].get('targets',tuple(range(9))):
            if (catalog.target(field,value)!=before['values'][field]['native_value']
                    and domain(before,field,value) not in catalog.CALIBRATED_UNIT_WRITES):
                return field,value
    raise RuntimeError('finite custom fixture unexpectedly has no closed changed-write target')


def run(gate,fixtures,prior_pids):
    gate.record.update(profile='units-public-writes-v1',success=False,full_acceptance_eligible=False,
                       changed_write_acceptance=False,changed_write_attempted=True,unit_cases=[])
    # Capture ownership before evidence preflight so a preflight failure still
    # leaves the wrapper enough proof to stop this exact owned host once.
    host=gate.record['host']=gate.health()['host'];gate.checkpoint('unit-write-owned-host')
    require(host.get('owned_by_daemon') is True and host.get('visible') is False and host.get('shared_interactive') is False,
            'public unit writes require own hidden unshared host')
    require(type(prior_pids) is list and all(type(pid) is int for pid in prior_pids)
            and host['process_id'] not in prior_pids,'public host existed before this run')
    report=json.loads((fixtures/'report.json').read_text())
    require(report.get('success') is True and report.get('profile')=='units-write-calibration-v1'
            and [c['document_type'] for c in report['cases']]==[1,2,3]
            and all(c.get('success') is True and c.get('write_diagnostic_success') is True for c in report['cases']),
            'successful three-type finite native write calibration required')
    # Validate every planned step and file BEFORE opening/creating any public CAD fixture.
    planned=[]
    for case in report['cases']:
        require_complete_case(case)
        for step in case['write_steps']:
            key=validate_step(step,case['document_type'])
            source=file_in_fixture(fixtures,step['source_file'],step['source_sha256'])
            file_in_fixture(fixtures,step['target_file'],step['target_sha256'])
            planned.append((key,step,source))
    gate.record.update(calibration_source_commit=report['source_commit'],
        calibration_sha256=hashlib.sha256((fixtures/'report.json').read_bytes()).hexdigest())
    gate.require_empty()
    for index,(key,expected,path) in enumerate(planned):
        case=dict(document_type=key[0],domain=list(key),success=False,source_sha256=expected['source_sha256'])
        gate.record['unit_cases'].append(case);gate.checkpoint('unit-write-source-preflight')
        opened=case['open']=gate.command('document','open',str(path))
        document=opened['document']['document_id'];foreground=gate.create()
        require(opened['api_errors']==opened['api_warnings']==0 and opened['document']['type']==key[0]
                and not opened['document']['modified'],'public write source did not open cleanly')
        gate.command('document','lease','acquire','--ttl-seconds',600,document=document)
        before=case['read']=public.read(gate,document)
        require(catalog.typed_key(before['unit_profile'])==catalog.typed_key(expected['before']),
                'public source differs from independently calibrated complete profile')
        if key[0]==1:case['geometry_before']=public.geometry(gate,document)
        field,value=expected['field'],expected['value']
        same=before['unit_profile']['values'][field]['value']
        case['noop']=edit(gate,document,before,field,same)
        case['lease_refusal']=edit(gate,document,before,field,value,error='DocumentLeaseConflict',session=gate.session+'-contender')
        case['stamp_refusal']=edit(gate,document,before,field,value,error='DocumentUpdateConflict',stamp=before['document']['update_stamp']+1)
        wrong=deepcopy(before['unit_profile']);wrong['linkage']['swUnitsTimeUnits']+=-1 if wrong['linkage']['swUnitsTimeUnits']==2147483647 else 1
        case['cas_refusal']=edit(gate,document,before,field,value,error='DocumentUnitProfileConflict',snapshot=wrong)
        closed=uncalibrated_custom_target(before['unit_profile'])
        if closed is not None:
            case['custom_closed_refusal']=edit(gate,document,before,*closed,error='UnitProfileCalibrationRequired')
        observed=public.read(gate,document)
        require(observed['document']==before['document'] and catalog.typed_key(observed['unit_profile'])==catalog.typed_key(before['unit_profile']),
                'public pre-write refusal/noop changed exact state/profile')
        case['write']=edit(gate,document,before,field,value,changed=True,after=expected['after'])
        observed=case['after_write']=public.read(gate,document)
        require(observed['document']==case['write']['document'] and catalog.typed_key(observed['unit_profile'])==catalog.typed_key(expected['after']),
                'public changed result differs on guarded reread')
        if key[0]==1:
            case['geometry_after_write']=public.geometry(gate,document)
            public.evidence.record_exact_geometry(case['geometry_before'],case['geometry_after_write'],case,'comparison_after_write',lambda:gate.checkpoint('unit-write-geometry'),'public unit write changed geometry')
        copy=gate.directory/('public-write-%03d.%s'%(index+1,path.suffix[1:]))
        saved=case['save']=gate.write('document','save-as',str(copy),document=document)
        require(saved['api_saved'] is True and saved['save_errors']==0 and saved['save_warnings'] is None
                and saved['document']['modified'] is False and PureWindowsPath(saved['document']['path'])==PureWindowsPath(str(copy)),
                'public changed copy save failed')
        digest=case['saved_sha256']=hashlib.sha256(copy.read_bytes()).hexdigest()
        gate.close(document)
        reopened=case['reopen']=gate.command('document','open',str(copy),'--read-only')
        fresh=reopened['document']['document_id'];reopened_front=gate.create()
        require(fresh!=document and reopened['read_only'] is True and reopened['api_errors']==reopened['api_warnings']==0
                and reopened['document']['modified'] is False,'public write copy readonly reopen failed')
        readonly=case['readonly_read']=public.read(gate,fresh)
        require(catalog.typed_key(readonly['unit_profile'])==catalog.typed_key(expected['after']),
                'public changed profile did not persist exactly')
        gate.command('document','lease','acquire','--ttl-seconds',600,document=fresh)
        case['readonly_refusal']=edit(gate,fresh,readonly,field,value,error='ValueError')
        final=case['final_read']=public.read(gate,fresh)
        require(final['document']==readonly['document'] and catalog.typed_key(final['unit_profile'])==catalog.typed_key(readonly['unit_profile'])
                and hashlib.sha256(copy.read_bytes()).hexdigest()==digest
                and hashlib.sha256(path.read_bytes()).hexdigest()==expected['source_sha256'],
                'readonly public write verification changed state/profile/native bytes')
        if key[0]==1:
            case['geometry_readonly']=public.geometry(gate,fresh)
            public.evidence.record_exact_geometry(case['geometry_before'],case['geometry_readonly'],case,'comparison_readonly',lambda:gate.checkpoint('unit-write-readonly-geometry'),'public unit write reopen changed geometry')
        gate.close(fresh);gate.close(reopened_front);gate.close(foreground);gate.require_empty(after_case='unit-write-%03d'%index)
        case['success']=True;gate.checkpoint('unit-write-verified')
    require(gate.health()['host']==host,'public unit writes replaced native host')
    gate.record.update(success=True,state='completed',changed_write_acceptance=True)


if __name__=='__main__':public.main(run_profile=run)
