"""Offline independent audit of the exact new Windows ZIP. No COM/product imports."""
import argparse
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import zipfile

RUN=42361728509
HEAD='577309005a858c11543b5def253dca36e5d0c598'
ARTIFACT=13571025062
DIGEST='92c718be6f704c350075ce4de8fbce5e621d81de40e77ae5b915d95d8e882e6c'
PREFIX='swcli-native-smoke/'
CAL=PREFIX+'units-calibration/'
PUB=PREFIX+'units-public-acceptance/'
FIELDS={'system','linear.unit','linear.precision','angular.unit','angular.precision','mass_properties.length_unit','mass_properties.mass_unit','mass_properties.volume_unit','mass_properties.precision'}
NATIVE={'length_unit','fraction_base','fraction_value','significant_digits','round_to_fraction'}
TOGGLES={'swUnitsLinearRoundToNearestFraction','swUnitsLinearFeetAndInchesFormat','swUnitsDualLinearRoundToNearestFraction','swUnitsDualLinearFeetAndInchesFormat'}
LINKAGE=TOGGLES|{'swUnitsLinearDecimalDisplay','swUnitsLinearFractionDenominator','swUnitsDualLinear','swUnitsDualLinearDecimalDisplay','swUnitsDualLinearDecimalPlaces','swUnitsDualLinearFractionDenominator','swUnitsForce','swUnitsForceDecimalPlaces','swUnitsEnergyUnits','swUnitsEnergyDecimalPlaces','swUnitsPowerUnits','swUnitsPowerDecimalPlaces','swUnitsTimeUnits','swUnitsTimeDecimalPlaces','swUnitsDecimalRounding'}
SYSTEM={'cgs':1,'mks':2,'ips':3,'custom':4,'mmgs':5}
LENGTH=dict(zip(('mm','cm','m','inch','feet','feet_inches','angstrom','nm','micron','mil','microinch'),range(11)))
ANGLE={'degrees':0,'degrees_minutes':1,'degrees_minutes_seconds':2,'radians':3}
MASS={'mg':1,'g':2,'kg':3,'lb':4}
VOLUME=dict(zip(('angstrom3','nm3','micron3','mm3','cm3','m3','microinch3','mil3','inch3','feet3','microliter','milliliter','centiliter','deciliter','liter','hectoliter','us_fluid_ounce','us_pint','us_gallon','imperial_gallon','imperial_yard3'),range(1,22)))
ENUMS={'system':SYSTEM,'linear.unit':LENGTH,'angular.unit':ANGLE,'mass_properties.length_unit':LENGTH,'mass_properties.mass_unit':MASS,'mass_properties.volume_unit':VOLUME}


def check(ok,message):
    if not ok:raise AssertionError(message)


def pairs(rows):
    result={}
    for key,value in rows:
        check(key not in result,'duplicate JSON key: '+key);result[key]=value
    return result


def loads(raw):
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:check(False,'nonfinite JSON: '+v))


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def same(a,b):return canonical(a)==canonical(b)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def integer(v,lo,hi):return type(v) is int and lo<=v<=hi


def profile(p,kind):
    check(set(p)=={'profile','document_type','values','native_units','linkage'},'incomplete profile')
    check(p['profile']=='document-units-v1' and type(p['document_type']) is int and p['document_type']==kind,'profile type')
    check(set(p['values'])==FIELDS and set(p['native_units'])==NATIVE and set(p['linkage'])==LINKAGE,'profile field coverage')
    for field,row in p['values'].items():
        check(set(row)=={'value','native_value'} and integer(row['native_value'],-2**31,2**31-1),'native row')
        raw=row['native_value']
        expected=next((name for name,code in ENUMS[field].items() if code==raw),'other') if field in ENUMS else raw if 0<=raw<=8 else 'other'
        check(same(row['value'],expected),'enum/precision observation differs: '+field)
    check(all(integer(v,-32768,32767) for v in p['native_units'].values()),'five short values')
    check(p['native_units']['length_unit']==p['values']['linear.unit']['native_value'] and p['native_units']['significant_digits']==p['values']['linear.precision']['native_value'],'GetUnits/primary display linkage')
    for key,value in p['linkage'].items():
        check(type(value) is bool if key in TOGGLES else integer(value,-2**31,2**31-1),'linkage native type')


def geometry(before,after):
    for m in (before,after):
        check(set(m)=={'solid_body_count','volume_mm3','surface_area_mm2','centroid_mm'},'metrics shape')
        check(type(m['solid_body_count']) is int and m['solid_body_count']==1,'body count')
        check(set(m['centroid_mm'])==set('xyz'),'centroid axes')
        for key,expected in (('volume_mm3',12000),('surface_area_mm2',3800)):
            value=m[key];check(type(value) in (int,float) and math.isfinite(value) and math.isclose(value,expected,rel_tol=1e-7,abs_tol=1e-5),'analytic '+key)
        for axis,expected in zip('xyz',(0,0,5)):
            value=m['centroid_mm'][axis];check(type(value) in (int,float) and math.isfinite(value) and math.isclose(value,expected,rel_tol=1e-7,abs_tol=1e-5),'analytic centroid '+axis)
    check(before['volume_mm3']==after['volume_mm3'] and before['surface_area_mm2']==after['surface_area_mm2'],'V/S must be exact')
    check(all(abs(after['centroid_mm'][a]-before['centroid_mm'][a])<=1e-12 for a in 'xyz'),'centroid absolute bound')


def geometry_record(before,after,record):
    geometry(before,after)
    check(record['centroid_absolute_limit_mm']==1e-12 and record['accepted_under_units_centroid_bound'] is True,'approved bound receipt')
    check(record['exact_equal'] is (before==after),'raw equality was relabeled')
    left={**{k:before[k] for k in ('solid_body_count','volume_mm3','surface_area_mm2')},**{'centroid_mm.'+k:v for k,v in before['centroid_mm'].items()}}
    right={**{k:after[k] for k in ('solid_body_count','volume_mm3','surface_area_mm2')},**{'centroid_mm.'+k:v for k,v in after['centroid_mm'].items()}}
    expected={k:dict(before=v,after=right[k],before_hex=float(v).hex(),after_hex=float(right[k]).hex(),delta=right[k]-v) for k,v in left.items() if v!=right[k]}
    check(same(record['differences'],expected),'raw hex/delta differs')


def zero(result):check(same(result['mutation'],dict(attempted=False,may_have_changed=False)),'nonzero/missing mutation')

def trace_audit(items,public=False):
    starts={};ends={};errors=[];workers=set()
    for e in items:
        key=(e['request_id'],e['sequence']) if public else e['sequence']
        clock=e['monotonic_seconds'] if public else e['monotonic']
        if public:workers.add(e['worker_pid'])
        if e['phase']=='begin':check(key not in starts,'duplicate native begin');starts[key]=clock
        else:
            check(key not in ends,'duplicate native terminal');ends[key]=clock
            if e['phase']=='error':
                check(public and e['stage']=='operation' and e['exception_type'] in ('DocumentLeaseConflict','DocumentUpdateConflict'),'unexpected native/API error')
                errors.append(e['exception_type'])
    check(starts.keys()==ends.keys() and starts,'unbalanced native trace')
    spans=[ends[k]-v for k,v in starts.items()]
    check(min(spans)>=0 and max(spans)<=600,'native 600s budget')
    group=max(ends.values())-min(starts.values());check(group<=1800,'group 1800s budget')
    if public:check(len(workers)==1 and Counter(errors)==Counter(DocumentLeaseConflict=3,DocumentUpdateConflict=3),'worker replacement or unexpected error count')
    return dict(boundaries=len(starts),max_call_seconds=max(spans),group_seconds=group,expected_context_errors=Counter(errors))


def audit(archive,metadata,repo):
    run=loads((metadata/'run-completed.json').read_bytes());jobs=loads((metadata/'jobs-completed.json').read_bytes())['jobs'];artifacts=loads((metadata/'artifacts.json').read_bytes())['artifacts']
    check(run['id']==RUN and run['head_sha']==HEAD and run['status']=='completed' and run['conclusion']=='success' and run['event']=='workflow_dispatch','wrong/incomplete run')
    check(run['repository']['full_name']=='YJBeetle/SWCLI' and run['head_branch']=='codex/docprops-units-expanded','repository/ref')
    for name in ('Build wheel','Windows / Python 3.9','Windows / Python 3.14','Validate manual units routing before private native setup','Public units read/CAS acceptance'):
        job=next(j for j in jobs if j['name']==name);check(job['run_id']==RUN and job['run_attempt']==run['run_attempt']==1 and job['head_sha']==HEAD and job['conclusion']=='success','job source/outcome: '+name)
    check(next(j for j in jobs if j['name']=='Publish original verified version-tag artifacts')['conclusion']=='skipped','unexpected publication')
    job=next(j for j in jobs if j['name']=='Public units read/CAS acceptance');steps={s['name']:s['conclusion'] for s in job['steps']}
    for name in ('Calibrate bounded document unit profile','Verify public document unit profile CLI','Remove private test inputs and stop services','Upload SWCLI-generated smoke evidence'):check(steps[name]=='success','native/public step incomplete')
    for name in ('Prepare property fixtures for public CLI verification','Prepare annotation fixtures for public CLI verification','Run real SOLIDWORKS modeling and export smoke test'):check(steps[name]=='skipped','wrong native profile')
    a=next(a for a in artifacts if a['id']==ARTIFACT)
    check(a['name']==f'swcli-windows-hosted-{RUN}-1' and a['workflow_run']['id']==RUN and a['workflow_run']['head_sha']==HEAD,'stale artifact')
    check(a['digest']=='sha256:'+DIGEST and sha(archive.read_bytes())==DIGEST and archive.stat().st_size==a['size_in_bytes'],'official ZIP digest/size')
    with zipfile.ZipFile(archive) as z:
        check(len(z.namelist())==len(set(z.namelist())),'duplicate ZIP members');files={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
    cal=loads(files[CAL+'report.json']);host=loads(files[PUB+'host-report.json']);cli=loads(files[PUB+'cli/public-unit-profile.json'])
    check(cal['source_commit']==host['source_commit']==cli['calibration_source_commit']==HEAD,'report source linkage')
    check(cli['calibration_sha256']==sha(files[CAL+'report.json']),'public used another calibration')
    for r in (cal,host,cli):check(r['success'] is True and not r.get('failure') and not r.get('error') and r['cleanup_errors']==[],'report failed/cleanup error')
    check(cal['profile']=='units-read-cas-v1' and cli['profile']=='units-public-read-cas-v1' and cli['state']=='completed','profile completion')
    check(cal['write_acceptance_eligible'] is False and cli['changed_write_acceptance'] is False and cal['full_acceptance_eligible'] is False and cli['full_acceptance_eligible'] is False,'coverage overstated')
    check([c['document_type'] for c in cal['cases']]==[1,2,3] and [c['document_type'] for c in cli['unit_cases']]==[1,2,3],'three-type coverage')
    check(type(cal['host_pid']) is int and cal['host_pid'] not in cal['pids_before'],'internal host not new')
    h=cli['host'];check(h['owned_by_daemon'] is True and h['visible'] is False and h['shared_interactive'] is False,'public ownership')
    check(type(h['process_id']) is int and h['process_id'] not in host['pids_before'] and host['owned_native_pid']==h['process_id'] and host['owned_native_exit_confirmed'] is True,'owned process exit unproved')
    check(sorted(host['pids_before'])==sorted(host['pids_after']) and host['stop_exit_code']==0 and host['public_exit_code']==0 and host['duration_seconds']<=1800,'host lifecycle')
    stop=loads(files[PUB+'stop.stdout']);check(stop['success'] is True and stop['result']['stopping'] is True,'shutdown receipt')
    events=cli['events'];check(len(events)==98,'unexpected CLI event coverage');error_counts=Counter()
    for e in events:
        check(e['state']=='completed' and 0<e['request_timeout_seconds']<=600,'CLI event failed/budget')
        raw=loads(e['stdout']);check(same(raw,e['result']),'original stdout differs from event result')
        if e['returncode']==0:check(raw.get('ok') is True or raw.get('success') is True,'false success stdout')
        else:check(raw.get('ok') is False,'error envelope');error_counts[raw['error']['type']]+=1
    check(error_counts==Counter(DocumentLeaseConflict=3,DocumentUpdateConflict=3,DocumentUnitProfileConflict=3,ValueError=6),'missing/unexpected public refusals')
    for e in (events[0],events[-1]):check(same(e['result']['result']['host'],h),'host replaced during public cases')
    cases=[]
    for native,public,suffix in zip(cal['cases'],cli['unit_cases'],('SLDPRT','SLDASM','SLDDRW')):
        kind=native['document_type'];check(type(kind) is int and same(public['document_type'],kind),'case kind type');check(native['success'] is True and public['success'] is True,'case incomplete')
        base=native['read']['unit_profile'];profile(base,kind)
        for key in ('after_refusal','reopened_profile'):profile(native[key]['unit_profile'],kind);check(same(native[key]['unit_profile'],base),'native profile drift')
        check(same(native['read']['document'],native['after_refusal']['document']),'native state drift')
        zero(native['noop']);zero(native['refused']);zero(native['readonly_refusal']);check(native['noop']['changed'] is False and native['noop']['ok'] is True,'native noop')
        check(same(native['noop']['before'],base) and same(native['noop']['unit_profile'],base) and same(native['noop']['document'],native['read']['document']),'native noop changed values/state')
        check(native['reopen']['ok'] is True and native['reopen']['read_only'] is True and native['reopen']['api_errors']==native['reopen']['api_warnings']==0,'native readonly reopen')
        check(native['refused']['ok'] is False and native['refused']['error']['type'] in ('ValueError','UnitProfileCalibrationRequired'),'unexpected native refusal')
        digest=sha(files[CAL+'units.'+suffix]);check(digest==native['file_sha256']==public['original_sha256'],'native source bytes differ')
        copy_digest=sha(files[PUB+'cli/public-units.'+suffix]);check(copy_digest==public['copy_sha256'],'public copy bytes differ')
        initial=public['read'];profile(initial['unit_profile'],kind);check(same(initial['unit_profile'],base),'public vs native profile differs')
        for key in ('read','after_refusal','readonly_read'):
            result=public[key];profile(result['unit_profile'],kind);check(result['ok'] is True and same(result['unit_profile'],base),'public complete profile drift')
            check(result['document']['active'] is False and result['document']['current'] is False and result['document']['modified'] is False and result['document']['type']==kind,'public target state/selection')
        noop=public['noop'];zero(noop);check(noop['field']=='linear.precision' and noop['ok'] is True and noop['changed'] is False and same(noop['before'],base) and same(noop['unit_profile'],base) and same(noop['document'],initial['document']),'public noop changed state/profile')
        check(same(public['after_refusal']['document'],initial['document']),'refusal changed document state/identity')
        expected={'lease_refusal':'DocumentLeaseConflict','stamp_refusal':'DocumentUpdateConflict','cas_refusal':'DocumentUnitProfileConflict','closed_domain_refusal':native['refused']['error']['type'],'readonly_refusal':'ValueError'}
        for key,error in expected.items():
            r=public[key];check(r['ok'] is False and r['error']['type']==error,'refusal class: '+key)
            if key not in ('lease_refusal','stamp_refusal') or 'mutation' in r:zero(r)
        saved=public['save_copy'];reopened=public['reopen'];fresh=public['readonly_read']['document']
        check(saved['api_saved'] is True and saved['save_errors']==0 and saved['save_warnings'] is None and saved['document']['modified'] is False,'save-copy failure')
        check(reopened['read_only'] is True and reopened['api_errors']==reopened['api_warnings']==0 and fresh['document_id']!=initial['document']['document_id'],'readonly fresh identity')
        check(same(public['readonly_refusal']['document'],fresh),'readonly refusal changed state')
        reads=[e['result'] for e in events if e['result'].get('action')=='document.unit-profile' and e['result'].get('document',{}).get('document_id')==fresh['document_id']]
        check(len(reads)==2 and same(reads[-1]['document'],fresh) and same(reads[-1]['unit_profile'],base),'post-readonly-refusal drift')
        contender=[e for e in events if e['result'].get('action')=='document.unit-profile-set' and e['result'].get('error',{}).get('type')=='DocumentLeaseConflict' and initial['document']['document_id'] in e['command']]
        check(len(contender)==1,'lease probe coverage');token=contender[0]['command'][contender[0]['command'].index('--lease')+1]
        check(re.fullmatch(r'l-[0-9a-hjkmnp-tv-z]{12}',token) is not None,'invalid lease probe token')
        owners=[e['result']['lease'] for e in events if e['result'].get('lease',{}).get('document_id')==initial['document']['document_id'] and 'acquire' in e['command']]
        check(len(owners)==1 and owners[0]['lease_id']==token,'probe token was not the acquired owner token')
        contender_session=contender[0]['command'][contender[0]['command'].index('--session')+1]
        check(contender_session!=owners[0]['session_id'] and contender_session.endswith('-contender'),'probe did not test another session')

        if kind==1:
            geometry_record(native['geometry_before'],native['geometry_after_refusal'],native['comparison_after_refusal'])
            geometry_record(native['geometry_before'],native['geometry_reopened'],native['comparison_reopened'])
            geometry_record(public['geometry_before'],public['geometry_reopened'],public['comparison_reopened'])
        cases.append(dict(document_type=kind,source_system=base['values']['system'],source_native_units=base['native_units'],source_sha256=digest,copy_sha256=copy_digest,public_noop_precision=base['values']['linear.precision']['native_value'],refusals=expected))
    native_trace=[loads(line) for line in files[CAL+'trace.jsonl'].splitlines() if line.strip()]
    pub_trace=[]
    for line in files[PUB+'daemon.stderr'].splitlines():
        try:e=loads(line)
        except (ValueError,AssertionError):continue
        if e.get('event')=='swcli.native-call':pub_trace.append(e)
    traces=dict(internal=trace_audit(native_trace),public=trace_audit(pub_trace,True))
    check(not any('SetUserPreferenceInteger' in e.get('call','') for e in native_trace+pub_trace),'unexpected preference setter executed')
    git=lambda *args:subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    for base in ((HEAD,'HEAD'),('HEAD',)):
        subprocess.run(['git','-C',str(repo),'diff','--quiet',*base,'--','src','scripts/ci','.github'],check=True)
    check(not git('ls-files','--others','--exclude-standard','--','src','scripts/ci','.github'),'untracked operational source')
    source=git('show',HEAD+':src/swcli/document_unit_profile.py');tree=ast.parse(source)
    domain=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CALIBRATED_UNIT_WRITES' for t in n.targets))
    check(ast.literal_eval(domain)==(),'changed-write domain was enabled')
    return dict(audit_success=True,run_id=RUN,run_url=run['html_url'],verified_head=HEAD,artifact_id=ARTIFACT,official_zip_sha256=DIGEST,report_sha256=sha(files[CAL+'report.json']),public_report_sha256=sha(files[PUB+'cli/public-unit-profile.json']),host_report_sha256=sha(files[PUB+'host-report.json']),cases=cases,cli_events=len(events),expected_cli_errors=error_counts,native_trace=traces,owned_native_pid=h['process_id'],owned_native_exit_confirmed=True,public_group_seconds=host['duration_seconds'],source_unchanged_from_verified_head=True,source_tree=git('rev-parse',HEAD+':src'),coverage='three native Windows fixtures: nine-field read/raw5/linkage, precision noop, lease/stamp/CAS/closed-domain/readonly refusals, save/reopen and owned lifecycle',not_accepted=['changed preference writes','scalar/system switching','Wine/macOS/Linux native behavior','native injection of partial-write failure paths','full functional/release gate'])


def self_test():
    base=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.,y=0.,z=5.))
    tests=0
    for axis in 'xy':
        after=deepcopy(base);after['centroid_mm'][axis]=1e-12;geometry(base,after);tests+=1
        after['centroid_mm'][axis]=math.nextafter(1e-12,math.inf)
        try:geometry(base,after)
        except AssertionError:tests+=1
        else:raise AssertionError('audit accepted over-bound centroid')
    for field in ('volume_mm3','surface_area_mm2'):
        after=deepcopy(base);after[field]=math.nextafter(after[field],math.inf)
        try:geometry(base,after)
        except AssertionError:tests+=1
        else:raise AssertionError('audit accepted V/S ULP')
    for value in (float('nan'),float('inf'),-float('inf')):
        after=deepcopy(base);after['centroid_mm']['z']=value
        try:geometry(base,after)
        except AssertionError:tests+=1
        else:raise AssertionError('audit accepted nonfinite')
    after=deepcopy(base);after['solid_body_count']=2
    try:geometry(base,after)
    except AssertionError:tests+=1
    else:raise AssertionError('audit accepted changed body count')
    return tests


def main():
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--metadata-dir',type=Path,required=True)
    parser.add_argument('--repo-root',type=Path,default=root);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=audit(args.archive,args.metadata_dir,args.repo_root);result['audit_negative_and_boundary_checks']=self_test()
    text=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(text)
    print(text,end='')

if __name__=='__main__':main()
