"""Pinned ORIGINAL native-write ZIP audit. Stdlib only; no product/gate/CAD imports."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

RUN=42414478796
HEAD='68b05c98e0a13000b4ac06002163d01820fba7b7'
ARTIFACT=13591264000
ZIP_SHA='fdf66026e457ff035652acb0fde3d4929b8b0cadde41f0dbc2ca855ebf43e4f0'
PREFIX='swcli-native-smoke/units-write-calibration/'
SYSTEM={'cgs':1,'mks':2,'ips':3,'custom':4,'mmgs':5}
LENGTH=dict(zip(('mm','cm','m','inch','feet','feet_inches','angstrom','nm','micron','mil','microinch'),range(11)))
ANGLE={'degrees':0,'degrees_minutes':1,'degrees_minutes_seconds':2,'radians':3}
MASS={'mg':1,'g':2,'kg':3,'lb':4}
VOLUME=dict(zip(('angstrom3','nm3','micron3','mm3','cm3','m3','microinch3','mil3','inch3','feet3','microliter','milliliter','centiliter','deciliter','liter','hectoliter','us_fluid_ounce','us_pint','us_gallon','imperial_gallon','imperial_yard3'),range(1,22)))
FIELDS={'system':SYSTEM,'linear.unit':LENGTH,'linear.precision':None,'angular.unit':ANGLE,'angular.precision':None,'mass_properties.length_unit':LENGTH,'mass_properties.mass_unit':MASS,'mass_properties.volume_unit':VOLUME,'mass_properties.precision':None}
TARGETS={'linear.unit':('mm','inch'),'angular.unit':('degrees','radians'),'mass_properties.length_unit':('mm','m'),'mass_properties.mass_unit':('g','kg'),'mass_properties.volume_unit':('mm3','m3')}
RAW=('length_unit','fraction_base','fraction_value','significant_digits','round_to_fraction')
LINKAGE={'swUnitsLinearDecimalDisplay':int,'swUnitsLinearFractionDenominator':int,'swUnitsLinearRoundToNearestFraction':bool,'swUnitsLinearFeetAndInchesFormat':bool,'swUnitsDualLinear':int,'swUnitsDualLinearDecimalDisplay':int,'swUnitsDualLinearDecimalPlaces':int,'swUnitsDualLinearFractionDenominator':int,'swUnitsDualLinearRoundToNearestFraction':bool,'swUnitsDualLinearFeetAndInchesFormat':bool,'swUnitsForce':int,'swUnitsForceDecimalPlaces':int,'swUnitsEnergyUnits':int,'swUnitsEnergyDecimalPlaces':int,'swUnitsPowerUnits':int,'swUnitsPowerDecimalPlaces':int,'swUnitsTimeUnits':int,'swUnitsTimeDecimalPlaces':int,'swUnitsDecimalRounding':int}


def require(ok,message):
    if not ok:raise ValueError(message)


def typed(v):
    if type(v) is dict:return dict,tuple(sorted((k,typed(x)) for k,x in v.items()))
    if type(v) is list:return list,tuple(typed(x) for x in v)
    return type(v),v


def fingerprint(v):
    require(set(v)=={'profile','document_type','values','native_units','linkage'} and v['profile']=='document-units-v1','profile shape/version')
    require(type(v['document_type']) is int and v['document_type'] in (1,2,3),'document kind')
    require(set(v['values'])==set(FIELDS) and set(v['native_units'])==set(RAW) and set(v['linkage'])==set(LINKAGE),'nine/raw5/linkage19 completeness')
    for f,enum in FIELDS.items():
        row=v['values'][f];raw=row['native_value'];require(set(row)=={'value','native_value'} and type(raw) is int and -(2**31)<=raw<2**31,'raw preference type')
        expected=next((k for k,x in enum.items() if x==raw),'other') if enum else raw if 0<=raw<=8 else 'other'
        require(typed(row['value'])==typed(expected) and expected!='other','unknown/noncanonical native preference')
    require(all(type(x) is int and -32768<=x<=32767 for x in v['native_units'].values()),'GetUnits exact shorts')
    require(all(type(v['linkage'][k]) is t and (t is bool or -(2**31)<=v['linkage'][k]<2**31) for k,t in LINKAGE.items()),'linkage canonical types')
    return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def geometry(before,after,comparison):
    require(set(before)==set(after)=={'solid_body_count','volume_mm3','surface_area_mm2','centroid_mm'},'geometry shape')
    require(type(after['solid_body_count']) is int and after['solid_body_count']==before['solid_body_count']==1,'body count')
    for k in ('volume_mm3','surface_area_mm2'):
        require(type(before[k]) in (float,int) and type(after[k]) in (float,int) and math.isfinite(before[k]) and math.isfinite(after[k]) and after[k]==before[k],'V/S must stay exact')
    require(set(before['centroid_mm'])==set(after['centroid_mm'])==set('xyz'),'centroid shape')
    for k in 'xyz':
        require(type(before['centroid_mm'][k]) in (int,float) and type(after['centroid_mm'][k]) in (int,float) and math.isfinite(before['centroid_mm'][k]) and math.isfinite(after['centroid_mm'][k]) and abs(after['centroid_mm'][k]-before['centroid_mm'][k])<=1e-12,'centroid absolute bound')
    flat=lambda m:{**{k:m[k] for k in ('solid_body_count','volume_mm3','surface_area_mm2')},**{'centroid_mm.'+k:v for k,v in m['centroid_mm'].items()}}
    a,b=flat(before),flat(after);diff={k:dict(before=a[k],after=b[k],before_hex=float(a[k]).hex(),after_hex=float(b[k]).hex(),delta=b[k]-a[k]) for k in a if a[k]!=b[k]}
    require(comparison['exact_equal'] is (before==after) and typed(comparison['differences'])==typed(diff),'raw/delta/hex/exact flags')
    require(comparison['centroid_absolute_limit_mm']==1e-12 and comparison['accepted_under_units_centroid_bound'] is True,'geometry approval bound')


def audit(archive,metadata,repo):
    raw=archive.read_bytes();require(hashlib.sha256(raw).hexdigest()==ZIP_SHA,'official ZIP digest')
    a=json.loads((metadata/'artifact.json').read_bytes());r=json.loads((metadata/'run-completed.json').read_bytes());jobs=json.loads((metadata/'jobs-completed.json').read_bytes())
    require(a['id']==ARTIFACT and a['digest']=='sha256:'+ZIP_SHA and a['size_in_bytes']==len(raw),'artifact metadata')
    require(a['workflow_run']['id']==r['id']==RUN and a['workflow_run']['head_sha']==r['head_sha']==HEAD and r['conclusion']=='success','run/head')
    require(all(j['conclusion']=='success' for j in jobs['jobs'] if j['name'] in ('Build wheel','Windows / Python 3.9','Windows / Python 3.14','Private finite units write calibration','Validate manual units routing before private native setup')),'prerequisite/native jobs')
    with zipfile.ZipFile(archive) as z:
        report_bytes=z.read(PREFIX+'report.json');p=json.loads(report_bytes)
        require(p['source_commit']==HEAD and p['success'] is True and p['profile']=='units-write-calibration-v1' and p['public_write_domain_count']==0,'internal source/scope')
        require(p['write_acceptance_eligible'] is False and p['full_acceptance_eligible'] is False,'internal is not public/full')
        require(p['revision']=='33.5.0' and typed(p['budgets'])==typed(dict(native_seconds=600,group_seconds=1800)) and 0<p['duration_seconds']<=1800,'revision/budgets')
        require(p['cleanup_errors']==[] and 'failure' not in p and p['owned_native_exit_confirmed'] is True,'native cleanup')
        require(type(p['host_pid']) is int and p['host_pid']>0 and p['host_pid'] not in p['pids_before'] and p['pids_before']==p['pids_after'],'owned process inventory')
        require(PREFIX+'watchdog.json' not in z.namelist(),'watchdog failure present')
        rows=[json.loads(line) for line in z.read(PREFIX+'trace.jsonl').decode().splitlines()];stack=[];durations=[];counts=Counter()
        for row in rows:
            if row['phase']=='begin':stack.append(row);counts[row['call']]+=1
            else:
                require(row['phase']=='end' and stack and stack[-1]['sequence']==row['sequence'],'native error/incomplete/nesting')
                start=stack.pop();elapsed=row['monotonic']-start['monotonic'];require(0<=elapsed<=600,'native budget');durations.append(elapsed)
        require(not stack and rows[-1]['monotonic']-rows[0]['monotonic']<=p['duration_seconds']<=1800,'complete trace/group')
        for name in ('DispatchEx','ExitApp.owned-once','wait-owned-process','inventory-processes-before','inventory-processes-after'):
            require(counts[name]==1,'unexpected host lifecycle: '+name)
        require(counts['document-unit-profile.IModelDocExtension.SetUserPreferenceInteger']==139,'unit setter count')
        source_forms={}
        for label,path in dict(calibration='scripts/ci/calibrate-document-unit-profile.py',write_harness='scripts/ci/gate_support/unit_profile_writes.py',native_adapter='src/swcli/hosts/windows_document_unit_profile.py',catalog='src/swcli/document_unit_profile.py').items():
            raw_source=subprocess.check_output(['git','show',HEAD+':'+path],cwd=repo);lf=raw_source.replace(b'\r\n',b'\n')
            forms={hashlib.sha256(lf).hexdigest():'LF',hashlib.sha256(lf.replace(b'\n',b'\r\n')).hexdigest():'CRLF'}
            require(p['operating_source_sha256'][label] in forms,'operating source bytes: '+path);source_forms[path]=forms[p['operating_source_sha256'][label]]
        require([c['document_type'] for c in p['cases']]==[1,2,3],'exact three types')
        domains={};case_summaries=[];file_count=0;geom_count=0;nonexact=0;max_delta=0.0
        baseline=p['cases'][0]['geometry_before']
        for k,v in (('volume_mm3',12000),('surface_area_mm2',3800)):
            require(math.isclose(baseline[k],v,rel_tol=1e-7,abs_tol=1e-5),'analytic box')
        for axis,v in zip('xyz',(0,0,5)):require(math.isclose(baseline['centroid_mm'][axis],v,rel_tol=1e-7,abs_tol=1e-5),'analytic centroid')
        for case,suffix in zip(p['cases'],('SLDPRT','SLDASM','SLDDRW')):
            kind=case['document_type'];config='Default' if kind in (1,2) else None
            require(case['success'] is case['write_diagnostic_success'] is True,'case incomplete')
            require(len(case['template_sha256'])==64 and hashlib.sha256(z.read(PREFIX+'units.'+suffix)).hexdigest()==case['file_sha256'],'initial native/template hash')
            current=case['initial_profile'];fingerprint(current);initial=current['values']['system']['native_value']
            prepared=[];scalar=[];system=[];phase='prepare';previous_native_sha=case['file_sha256']
            for index,s in enumerate(case['write_steps'],1):
                before,after,result=s['before'],s['after'],s['result'];bf,af=fingerprint(before),fingerprint(after)
                require(s['success'] is True and typed(before)==typed(current) and s['before_fingerprint']==bf and s['after_fingerprint']==af,'complete source chain/fingerprint')
                require(before['document_type']==after['document_type']==kind,'snapshot type')
                field,value=s['field'],s['value'];target=FIELDS[field][value] if FIELDS[field] else value
                require(type(target) is int and target==s['native_target']==after['values'][field]['native_value']!=before['values'][field]['native_value'],'changed target')
                require(result['ok'] is True and result['changed'] is True and result['native_return_value'] is True and result['mutation']==dict(attempted=True,may_have_changed=True),'single setter success receipt')
                require(typed(result['before'])==typed(before) and typed(result['unit_profile'])==typed(after) and typed(result['observed'])==typed(after),'raw result')
                if s['role']=='explicit-custom-preparation':require(phase=='prepare' and field=='system','prepare phase');prepared.append(target)
                elif s['role']=='scalar':
                    require(phase in ('prepare','scalar') and field!='system','scalar phase');phase='scalar';scalar.append((field,target))
                    require(before['values']['system']['native_value']==4 and before['native_units']['fraction_base']==1 and before['native_units']['fraction_value'] in (0,8) and before['native_units']['round_to_fraction']==0,'Custom decimal source')
                    require(all(typed(before['values'][f])==typed(after['values'][f]) for f in FIELDS if f!=field) and typed(before['linkage'])==typed(after['linkage']),'scalar non-target/linkage strict')
                    allowed='length_unit' if field=='linear.unit' else 'significant_digits' if field=='linear.precision' else None
                    require(all(before['native_units'][f]==after['native_units'][f] for f in RAW if f!=allowed),'raw5 unrelated drift')
                    if allowed:require(after['native_units'][allowed]==target,'raw5 target coupling')
                elif s['role']=='system-spoke':require(phase in ('scalar','system') and field=='system','system phase');phase='system';system.append((before['values']['system']['native_value'],target))
                else:raise ValueError('unplanned role')
                if field=='system':require(5 in (before['values']['system']['native_value'],target),'unplanned system pair')
                cb,ca=s['context_before'],s['context_after']
                require(cb['target_identity']==ca['target_identity'] and cb['peer_state']==ca['peer_state'] and cb['peer_identity']==ca['peer_identity'],'target/peer identity or state')
                require(cb['target_state'][0]==ca['target_state'][0]==kind and cb['target_state'][3]==ca['target_state'][3]==config and cb['target_state'][2] is False and ca['target_state'][2] is True,'config/dirty/type')
                require(s['source_sha256']==s['source_original_sha256']==previous_native_sha,'original native byte chain')
                for label in ('source','target'):
                    path=s[label+'_file'].replace('\\','/');require(path==f'kind-{kind}/step-{index:03d}/{label}.{suffix}','exact native path')
                    require(hashlib.sha256(z.read(PREFIX+path)).hexdigest()==s[label+'_sha256'],'native byte hash');file_count+=1
                require(s['save']['ok'] is True and s['save']['save_errors']==0 and s['save']['save_warnings'] is None and s['save']['document']['modified'] is False,'save')
                require(typed(s['readonly_profile'])==typed(after),'readonly full snapshot')
                require(s['readonly_refusal']['ok'] is False and s['readonly_refusal']['error']['type']=='ValueError' and s['readonly_refusal']['mutation']==dict(attempted=False,may_have_changed=False),'readonly zero mutation')
                for label,readonly in (('reopen_readonly',True),('reopen_writable_for_next_case',False)):
                    require(s[label]['ok'] is True and s[label]['read_only'] is readonly and s[label]['api_errors']==s[label]['api_warnings']==0 and s[label]['document']['modified'] is False,'planned reopen')
                if kind==1:
                    for label in ('geometry_after_write','geometry_readonly'):
                        require(s[label+'_measurement']['ok'] is True and typed(s[label+'_measurement']['metrics'])==typed(s[label]),'raw geometry receipt')
                        geometry(baseline,s[label],s['comparison_'+label]);geom_count+=1;nonexact+=not s['comparison_'+label]['exact_equal']
                        max_delta=max(max_delta,max(abs(s[label]['centroid_mm'][a]-baseline['centroid_mm'][a]) for a in 'xyz'))
                key=(kind,bf,field,target)
                require(key not in domains or domains[key]['after']==af,'same domain has conflicting native results')
                domains[key]=dict(after=af,configuration=config)
                current=after;previous_native_sha=s['target_sha256']
            expected={(f,FIELDS[f][v] if FIELDS[f] else v) for f in FIELDS if f!='system' for v in TARGETS.get(f,range(9))}
            require(len(scalar)==37 and set(scalar)==expected,'all eight scalars/precision0..8')
            require(len(system)==8 and set(system)==({(5,c) for c in (1,2,3,4)}|{(c,5) for c in (1,2,3,4)}),'all eight system directions')
            require(prepared==([] if initial==4 else [4] if initial==5 else [5,4]),'actual initial system preserved')
            case_summaries.append(dict(document_type=kind,steps=len(case['write_steps']),scalar_targets=37,system_directions=8,preparation_targets=prepared,configuration=config,template_sha256=case['template_sha256']))
        require(len(domains)==137 and file_count==278 and geom_count==92,'exact native coverage')
        return dict(audit_success=True,run_id=RUN,verified_head=HEAD,artifact_id=ARTIFACT,zip_sha256=ZIP_SHA,report_sha256=hashlib.sha256(report_bytes).hexdigest(),revision=p['revision'],duration_seconds=p['duration_seconds'],trace_rows=len(rows),completed_native_boundaries=len(durations),max_native_call_seconds=max(durations),native_error_events=0,setter_calls=139,native_files_checked=file_count+3,cases=case_summaries,part_geometry_comparisons=geom_count,part_nonexact_comparisons=nonexact,max_centroid_absolute_delta_mm=max_delta,part_raw_baseline_with_hex={**{k:dict(value=baseline[k],hex=float(baseline[k]).hex()) for k in ('volume_mm3','surface_area_mm2')},'solid_body_count':baseline['solid_body_count'],'centroid_mm':{k:dict(value=v,hex=float(v).hex()) for k,v in baseline['centroid_mm'].items()}},owned_native_pid=p['host_pid'],owned_native_exit_confirmed=True,pids_before=p['pids_before'],pids_after=p['pids_after'],source_byte_forms=source_forms,registry_lease_coverage='not exercised by internal direct adapter; required in public validation',public_write_accepted=False,template_bytes_in_zip=False,reviewable_domains=[dict(document_type=k[0],source_snapshot_sha256=k[1],field=k[2],native_target=k[3],after_snapshot_sha256=v['after'],configuration=v['configuration']) for k,v in sorted(domains.items())])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--metadata-dir',type=Path,required=True);parser.add_argument('--repo-root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();data=json.dumps(audit(args.archive,args.metadata_dir,args.repo_root),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(data)
    else:print(data,end='')

if __name__=='__main__':main()
