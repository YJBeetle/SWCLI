"""Public CLI/daemon revolve acceptance; never imports COM or calibrates a host.

Requires an enabled, evidence-backed operation. One fresh owned daemon/host,
600s native requests and 1800s group, no retry/restart inside the group.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

from swcli.revolve_geometry import cylinder_expectation, verify_cylinder_metrics
from swcli.result_schemas import validate_operation_result


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


modeling = load('_revolve_public_modeling', 'verify-modeling.py')
require = modeling.require


def arguments(sketch, bounds, stamp, *, axis=None):
    return ['feature','revolve',sketch,'--expected-profile-mm',*bounds,
            '--axis-mm',*(axis or [0,bounds[1],0,bounds[3]]),'--angle-deg',360,'--if-update-stamp',stamp]


def verify_creation(result, bounds, transform):
    validate_operation_result('feature.revolve',result)
    require(result['ok'] is True and result['verified'] is True and not result['cleanup_errors']
            and result['feature']['type'] == 'Revolution'
            and re.fullmatch(r'f-[a-z0-9]{6}',result['feature']['feature_id'])
            and result['mutation'] == dict(attempted=True,creation_returned=True,may_have_changed=True),
            'native editable revolve creation/partial-state evidence is incomplete')
    expected=cylinder_expectation(bounds,transform)
    verify_cylinder_metrics(result['metrics'],expected)
    require(result['definition']['axis_matches'] is True and result['definition']['boss'] is True
            and result['definition']['thin'] is False and result['definition']['reverse'] is False
            and math.isclose(result['definition']['angle_rad'],2*math.pi,rel_tol=0,abs_tol=1e-12),
            'public result lacks exact axis/native definition evidence')
    return expected


def unchanged(gate, document, before, result):
    require(result['ok'] is False and result.get('mutation') ==
            dict(attempted=False,creation_returned=False,may_have_changed=False),
            'refused operation reached the native write boundary')
    require(gate.command('document','inspect',document=document)['document'] == before,
            'refused operation changed document state')



def verify_saved_profile(observed, bounds, transform):
    require(observed['geometry_complete'] is True and observed['editing'] is False
            and observed['profile_segment_count']==4 and observed['segment_count']==6,
            'saved profile geometry is incomplete or not the original center rectangle')
    x0,y0,x1,y1=bounds
    corners=((x0,y0,0),(x1,y0,0),(x1,y1,0),(x0,y1,0))
    edges=[]
    for segment in observed['segments']:
        if segment['construction']:
            continue
        geometry=segment['geometry']
        require(geometry is not None and geometry['kind']=='line','saved profile has a nonline')
        pair=[]
        for point in (geometry['start_mm'],geometry['end_mm']):
            ids=[i for i,c in enumerate(corners) if all(math.isclose(point[a],c[j],rel_tol=0,abs_tol=1e-6)
                    for j,a in enumerate('xyz'))]
            require(len(ids)==1,'saved profile endpoint differs from an exact expected corner')
            pair.append(ids[0])
        edges.append(tuple(sorted(pair)))
    require(len(edges)==4 and set(edges)=={(0,1),(1,2),(2,3),(0,3)},'saved profile is not the same simple closed rectangle')
    require(len(observed['model_to_sketch_transform'])==len(transform)==16 and
            all(math.isclose(a,b,rel_tol=0,abs_tol=1e-12) for a,b in
                zip(observed['model_to_sketch_transform'],transform)), 'saved sketch plane transform changed')


def run(gate):
    gate.record.update(profile='bounded-revolve-public',success=False,public_acceptance=False,
                       source_commit=os.environ.get('GITHUB_SHA'),revolve_cases=[])
    host=gate.record['host']=gate.health()['host']
    require(host['owned_by_daemon'] is True and host['shared_interactive'] is False and host['visible'] is False,
            'revolve public gate requires an exclusive hidden daemon-owned host')
    gate.require_empty()
    for plane,bounds in (('front',[0,-5,10,15]),('top',[0,3,7,21]),('right',[0,-14,4,10])):
        case=dict(plane=plane,bounds_mm=bounds,success=False)
        gate.record['revolve_cases'].append(case)
        document=gate.create()
        gate.command('document','lease','acquire','--ttl-seconds',600,document=document)
        foreground=gate.create()
        made=case['sketch']=gate.rectangle(document,plane=plane,width=bounds[2],height=bounds[3]-bounds[1],
                                          x=bounds[2]/2,y=(bounds[1]+bounds[3])/2)
        sketch=made['sketch']['sketch_id']
        gate.background(made,document)
        before=gate.command('document','inspect',document=document)['document']
        stamp=before['update_stamp']
        foreground_stamp=gate.command('document','inspect',document=foreground)['document']['update_stamp']
        case['foreign_document_refusal']=gate.command(*arguments(sketch,bounds,foreground_stamp),document=foreground,
                                                       expected_error='SketchNotFound')
        case['lease_refusal']=gate.command(*arguments(sketch,bounds,stamp),document=document,
                                            session=gate.session+'-contender',expected_error='DocumentLeaseConflict')
        case['stamp_refusal']=gate.write(*arguments(sketch,bounds,stamp+1),document=document,
                                          expected_error='DocumentUpdateConflict')
        require(gate.command('document','inspect',document=document)['document']==before,
                'identity/lease/stamp refusal changed target state')
        wrong=list(bounds);wrong[2]+=1
        case['profile_cas_refusal']=gate.write(*arguments(sketch,wrong,stamp),document=document,
                                               expected_error='RevolveProfileConflict')
        unchanged(gate,document,before,case['profile_cas_refusal'])
        case['creation']=gate.write(*arguments(sketch,bounds,stamp),document=document)
        gate.background(case['creation'],document)
        expected=verify_creation(case['creation'],bounds,made['model_to_sketch_transform'])
        case['measured']=gate.measure(document)['metrics']
        verify_cylinder_metrics(case['measured'],expected)
        path=gate.directory/(plane+'-public.SLDPRT')
        case['save']=gate.write('document','save-as',str(path),document=document)
        require(case['save']['save_errors']==0 and case['save']['save_warnings'] is None
                and case['save']['document']['modified'] is False and path.is_file()
                and case['save']['artifact']['size_bytes']==path.stat().st_size>=512,
                'public revolve native output did not save cleanly')
        digest=case['file_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        gate.close(document)
        opened=case['reopen']=gate.command('document','open',str(path),'--read-only')
        fresh=opened['document']['document_id']
        require(fresh!=document and opened['read_only'] is True
                and opened['api_errors']==opened['api_warnings']==0 and opened['document']['modified'] is False,
                'saved public revolve did not reopen cleanly read-only')
        structure=case['reopened_structure']=gate.command('document','inspect','--detail','structure',document=fresh)
        features=structure['structure']['features']
        require(not features['truncated'] and sum(f['type']=='Revolution' for f in features['items'])==1,
                'saved public output does not retain exactly one editable Revolution feature')
        sketches=gate.command('sketch','list',document=fresh)
        candidates=[s for s in sketches['sketches'] if s['absorbed'] and s['owner']['type']=='Revolution']
        require(len(candidates)==1 and candidates[0]['sketch_id']!=sketch,
                'saved revolution does not own exactly one freshly registered absorbed profile')
        observed=case['reopened_profile']=gate.command('sketch','inspect',candidates[0]['sketch_id'],document=fresh)
        require(observed['coordinate_system']=='sketch-local' and observed['profile_segment_count']==4,
                'saved editable profile is not the original four-edge section')
        verify_saved_profile(observed,bounds,made['model_to_sketch_transform'])
        case['reopened_metrics']=gate.measure(fresh)['metrics']
        verify_cylinder_metrics(case['reopened_metrics'],expected)
        diagnostic=case['reopened_diagnostics']=gate.command('document','diagnose',document=fresh)
        require(diagnostic['diagnostics']['healthy'] and not diagnostic['diagnostics']['truncated']
                and diagnostic['needs_rebuild']==0,'saved public output is not healthy')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,
                'read-only public verification altered the actual saved file contents')
        gate.close(fresh)
        gate.close(foreground)
        gate.require_empty(after_case='revolve-'+plane)
        case['success']=True
        gate.checkpoint('revolve-'+plane+'-verified')
    # A saved unabsorbed profile is necessary to exercise the read-only guard
    # before the absorbed-profile guard, with the exact same public intent.
    document=gate.create()
    made=gate.rectangle(document,width=10,height=20,x=5,y=5)
    path=gate.directory/'read-only-profile.SLDPRT'
    gate.write('document','save-as',str(path),document=document)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    gate.close(document)
    opened=gate.command('document','open',str(path),'--read-only')
    fresh=opened['document']['document_id']
    sketches=gate.command('sketch','list',document=fresh)['sketches']
    require(len(sketches)==1 and not sketches[0]['absorbed'],'read-only fixture lacks exact unabsorbed profile')
    foreground=gate.create()
    before=gate.command('document','inspect',document=fresh)['document']
    refused=gate.record['read_only_refusal']=gate.write(*arguments(sketches[0]['sketch_id'],[0,-5,10,15],before['update_stamp']),
                                                      document=fresh,expected_error='DocumentReadOnly')
    unchanged(gate,fresh,before,refused)
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'read-only refusal altered saved bytes')
    gate.close(fresh);gate.close(foreground)
    # Crossing section and a nonrectangle both fail before mutation.
    for name,kind,error in (('crossing','rectangle','RevolveProfileConflict'),('circle','circle','UnsupportedDimensionProfile')):
        document=gate.create();foreground=gate.create()
        made=gate.rectangle(document,width=10,height=20,x=0,y=5) if kind=='rectangle' else gate.circle(document,radius=5,x=5,y=5)
        before=gate.command('document','inspect',document=document)['document']
        refused=gate.record[name+'_refusal']=gate.write(*arguments(made['sketch']['sketch_id'],[0,-5,10,15],before['update_stamp']),
                                                       document=document,expected_error=error)
        unchanged(gate,document,before,refused)
        gate.close(document);gate.close(foreground)
    document=gate.create();foreground=gate.create()
    for x in (5,35):
        made=gate.rectangle(document,width=10,height=20,x=x,y=5)
        gate.write('feature','extrude',made['sketch']['sketch_id'],'--depth-mm',10,'--no-merge',document=document)
    require(gate.measure(document)['metrics']['solid_body_count']==2,'public negative fixture is not multibody')
    made=gate.rectangle(document,width=10,height=20,x=5,y=5)
    before=gate.command('document','inspect',document=document)['document']
    refused=gate.record['multibody_refusal']=gate.write(*arguments(made['sketch']['sketch_id'],[0,-5,10,15],before['update_stamp']),
                                                      document=document,expected_error='UnsupportedRevolveBodyScope')
    unchanged(gate,document,before,refused)
    gate.close(document);gate.close(foreground)
    gate.require_empty(after_case='revolve-negative-cases')
    gate.record['host_after']=gate.health()['host']
    require(gate.record['host_after']==host,'public revolve group replaced its owned host')
    gate.record.update(success=True,state='completed')


def worker(output):
    runtime=load('_revolve_public_runtime','verify-runtime-sets.py')
    args=SimpleNamespace(output_dir=output,host_output_dir=str(output),endpoint='127.0.0.1:18597',suite='core',
                         mode='hidden',request_timeout=600,startup_timeout=120,set_timeout=1800,
                         cli_command=None,daemon_log=output/'daemon.log')
    runner=runtime.Runner(args)
    item=dict(name='bounded-revolve-public')
    runner.record.update(expected_sets=[item['name']],coverage_scope='bounded-revolve-public',sets=[item])
    gate=None
    os.environ['SWCLI_TRACE_NATIVE_CALLS']='1'
    try:
        runner.start(item)
        gate=modeling.ModelingSmoke(directory=output,host_directory=str(output),endpoint=args.endpoint,
                                     request_timeout_seconds=600,depth_request_timeout_seconds=600)
        gate.record_path=output/'revolve-public.json'
        gate.record_path.write_text('{}\n')
        run(gate)
        runner.record.update(success=True,completed=True)
    except BaseException as exc:
        runner.record.update(success=False,error=dict(type=type(exc).__name__,message=str(exc)))
        if gate is not None:
            gate.record.update(success=False,state='failed',error=dict(type=type(exc).__name__,message=str(exc)))
        raise
    finally:
        if gate is not None:
            gate.cleanup()
            if gate.record['cleanup_errors']:
                gate.record.update(success=False,state='failed')
            gate.checkpoint('revolve-public-final')
        primary=sys.exc_info()[1]
        try:
            runner.stop(item)
        except BaseException as exc:
            runner.record.update(success=False,shutdown_error=dict(type=type(exc).__name__,message=str(exc)))
            if primary is None:
                raise
        finally:
            runner.checkpoint()
    require(gate.record['success'] and runner.record['success'] and not gate.record['cleanup_errors']
            and gate.checkpoint_error is None,'public revolve acceptance was incomplete')
    gate.record['public_acceptance']=True
    gate.checkpoint('revolve-public-completed')
    if gate.checkpoint_error is not None:
        raise gate.checkpoint_error


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    output=args.output_dir.resolve()
    if args.worker:
        return worker(output)
    output.mkdir()
    with (output/'driver-stdout.log').open('w') as stdout,(output/'driver-stderr.log').open('w') as stderr:
        child=subprocess.Popen([sys.executable,'-I',str(Path(__file__).resolve()),'--worker','--output-dir',str(output)],
                               stdout=stdout,stderr=stderr)
        try:
            return child.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            child.kill();child.wait()
            (output/'group-timeout.json').write_text(json.dumps(dict(seconds=1800)))
            return 124


if __name__=='__main__':
    raise SystemExit(main())
