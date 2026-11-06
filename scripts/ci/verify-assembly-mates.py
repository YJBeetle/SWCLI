"""Independent installed public CLI -> daemon -> worker standard-mate gate.

Never imports COM or uses the private native-calibration permission. All parts,
assemblies, mate reads/writes, refusals and save/reopen operations use public CLI.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from swcli.result_schemas import validate_operation_result

spec=importlib.util.spec_from_file_location('_mates_public_modeling',Path(__file__).with_name('verify-modeling.py'))
modeling=importlib.util.module_from_spec(spec);spec.loader.exec_module(modeling)
require=modeling.require


def content(snapshot):
    result=copy.deepcopy(snapshot)
    for key in ('title','path','update_stamp','modified'):result.pop(key)
    references={}
    for component in result['components']:
        component.pop('source_update_stamp')
        component.pop('native_id',None)
        geometry_keys=set()
        for face in component['faces']:
            reference=face.pop('reference_sha256')
            face.pop('index')
            key=json.dumps(face,sort_keys=True,allow_nan=False)
            require(key not in geometry_keys,'reopened face geometry is ambiguous')
            geometry_keys.add(key)
            references[reference]=[component['name'],copy.deepcopy(face)]
        component['faces'].sort(key=lambda face:json.dumps(face,sort_keys=True))
    for mate in result['mates']:
        mate['references']=[references[ref] for ref in mate['references']]
    return result


def verify_content(actual,expected):
    import math
    if type(actual) in (int,float) and type(expected) in (int,float):
        require(math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10),'saved numerical mate content changed')
    elif isinstance(actual,dict) and isinstance(expected,dict):
        require(set(actual)==set(expected),'saved mate content fields changed')
        for key in actual:verify_content(actual[key],expected[key])
    elif isinstance(actual,list) and isinstance(expected,list):
        require(len(actual)==len(expected),'saved mate list changed')
        for a,b in zip(actual,expected):verify_content(a,b)
    else:require(type(actual) is type(expected) and actual==expected,'saved component/mate identity changed')


def command_mate(gate,target,kind,alignment,targets,snapshot,*,session=None,lease=None,expected_error=None):
    return gate.command('assembly','add-mate','--kind',kind,'--alignment',alignment,
        '--targets',json.dumps(targets),'--expected-value',json.dumps(snapshot),
        '--if-update-stamp',snapshot['update_stamp'],document=target,
        session=session,lease=lease,expected_error=expected_error)


def read(gate,target,names):
    result=gate.command('assembly','mate-targets',*names,document=target)
    validate_operation_result('assembly.mate-targets',result)
    require(result['ok'],'native target read failed')
    return result


def run_case(gate,kind,alignment):
    case=dict(kind=kind,alignment=alignment,success=False)
    gate.record['cases'].append(case)
    prefix=kind+'-'+alignment
    source=gate.create()
    circle=gate.circle(source,radius=3)
    gate.write('feature','extrude',circle['sketch']['sketch_id'],'--depth-mm',10,document=source)
    part=gate.directory/(prefix+'.SLDPRT')
    gate.write('document','save-as',str(part),document=source)
    part_hash=hashlib.sha256(part.read_bytes()).hexdigest()
    source_structure=gate.command('document','inspect','--detail','structure',document=source)
    cfg=source_structure['structure']['configurations']['active']
    assembly=gate.command('document','create','--type','assembly')['document']['document_id']
    inserted=[]
    for i in range(2):
        inserted.append(gate.write('assembly','add-component',str(part),'--configuration',cfg,
            '--x-mm',i*30,'--y-mm',i*10,'--z-mm',i*20,document=assembly))
    names=[item['component']['name'] for item in inserted]
    foreground=gate.create()
    before=read(gate,assembly,names)
    gate.background(before,assembly)
    expected=before['snapshot']
    targets=[]
    for component in expected['components']:
        candidates=[f for f in component['faces'] if f['surface_kind']==('plane' if kind=='coincident' else 'cylinder')]
        if kind=='coincident':candidates=[f for f in candidates if abs(f['parameters'][5])<1e-12]
        require(len(candidates)==1,'fixture target face must be unambiguous')
        targets.append(dict(component=component['name'],face_index=candidates[0]['index']))
    lease=gate.command('document','lease','acquire','--ttl-seconds',600,document=assembly)['lease']['lease_id']
    # The same exact context must reject foreign leases and stale complete CAS
    # before a native CreateMate, while a background read remains legal.
    foreign=command_mate(gate,assembly,kind,alignment,targets,expected,
        session=gate.session+'-foreign',expected_error='DocumentLeaseConflict')
    case['foreign_lease_refusal']=foreign
    gate.background(read(gate,assembly,names),assembly)
    stale=copy.deepcopy(expected);stale['components'][1]['faces'][targets[1]['face_index']]['area_mm2']+=1
    refused=command_mate(gate,assembly,kind,alignment,targets,stale,lease=lease,expected_error='MateValueConflict')
    case['cas_refusal']=refused
    require(not refused['mutation']['attempted'],'stale CAS reached CreateMate')
    after_refusal=read(gate,assembly,names)
    require(after_refusal['snapshot']==expected,'refusal changed assembly/component state')
    made=command_mate(gate,assembly,kind,alignment,targets,expected,lease=lease)
    validate_operation_result('assembly.add-mate',made)
    gate.background(made,assembly)
    require(made['mutation']['attempted'] and made['mutation']['creation_returned'] and
            made['mate']['kind']==kind and made['mate']['alignment']==alignment and
            made['mate']['distance_mm']<=1e-5 and made['mate']['parallel_error']<=1e-8 and
            made['mate']['error_code']==0 and not made['mate']['suppressed'],
            'public mate write did not verify its native solve/entities')
    case['creation']=made
    saved=gate.directory/(prefix+'.SLDASM')
    case['save_as']=gate.write('document','save-as',str(saved),document=assembly)
    require(not case['save_as']['document']['modified'],'assembly SaveAs is not clean')
    case['save']=gate.write('document','save',document=assembly)
    require(not case['save']['document']['modified'],'assembly Save3 is not clean')
    persisted=read(gate,assembly,names)
    case['saved_content']=content(persisted['snapshot'])
    saved_hash=hashlib.sha256(saved.read_bytes()).hexdigest()
    gate.close(assembly)
    remaining=gate.command('document','list')['documents']
    if source in {doc['document_id'] for doc in remaining}:gate.close(source)
    else:gate.owned.pop(source,None)
    gate.close(foreground)
    gate.require_empty()
    # Reopen twice from disk; all component documents must first be absent.
    for mode in ('writable','readonly'):
        opened=gate.command('document','open',str(saved),*(['--read-only'] if mode=='readonly' else []))
        fresh=opened['document']['document_id']
        require(fresh!=assembly and opened['api_errors']==0 and opened['api_warnings'] in ((0,2) if mode=='readonly' else (0,)),
                'independent native reopen returned errors or unexpected warnings')
        reopened=read(gate,fresh,names)
        require(not reopened['snapshot']['modified'],'fresh reopened assembly is modified')
        verify_content(content(reopened['snapshot']),case['saved_content'])
        case.setdefault('reopens',[]).append(dict(mode=mode,open=opened,targets=reopened))
        if mode=='readonly':
            refusal=command_mate(gate,fresh,kind,alignment,targets,reopened['snapshot'],expected_error='DocumentReadOnly')
            require(not refusal['mutation']['attempted'],'read-only mate write reached native creation')
            case['readonly_refusal']=refusal
        gate.close(fresh)
        gate.require_empty()
        require(hashlib.sha256(saved.read_bytes()).hexdigest()==saved_hash,'reopen changed saved ASM bytes')
    require(hashlib.sha256(part.read_bytes()).hexdigest()==part_hash,'public mate gate changed source part bytes')
    case.update(part_sha256=part_hash,assembly_sha256=saved_hash,part_size_bytes=part.stat().st_size,
                assembly_size_bytes=saved.stat().st_size,success=True)
    gate.checkpoint(prefix+'-verified')


def run(gate):
    gate.record.update(scope='public-assembly-standard-mates',full_acceptance_eligible=False)
    gate.record['host']=gate.health()['host']
    gate.require_empty()
    for operation in ('assembly.mate-targets','assembly.add-mate'):
        capability=gate.command('capabilities','--operation',operation)
        require(capability['operations']==[operation],'running daemon did not publish exact mate operation')
    for kind in ('coincident','concentric'):
        for alignment in ('aligned','anti-aligned'):
            run_case(gate,kind,alignment)
            require(gate.health()['host']==gate.record['host'],'host was replaced inside the public mate group')
    gate.record['host_after']=gate.health()['host']
    require(gate.record['host_after']==gate.record['host'],'public mate host changed')
    gate.record.update(state='completed',success=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--endpoint',required=True)
    parser.add_argument('--request-timeout',type=float,default=600)
    parser.add_argument('--host-output-dir')
    parser.add_argument('--cli-command')
    parser.add_argument('--suite',default='core')
    parser.add_argument('--sample-part')
    parser.add_argument('--sample-assembly')
    args=parser.parse_args(argv)
    require(args.request_timeout==600,'public mate native request budget must stay 600 seconds')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    gate=modeling.ModelingSmoke(directory=args.output_dir,host_directory=args.host_output_dir or str(args.output_dir),
        endpoint=args.endpoint,cli=[args.cli_command] if args.cli_command else None,request_timeout_seconds=600,suite=args.suite)
    with gate.record_path.open('x',encoding='utf-8') as stream:json.dump(gate.record,stream)
    try:run(gate)
    except BaseException:
        gate.record.update(state='failed',success=False)
        raise
    finally:
        gate.cleanup();gate.checkpoint('assembly-mates-final')
    if gate.checkpoint_error:raise gate.checkpoint_error
    require(not gate.record['cleanup_errors'],'public mate cleanup failed')


if __name__=='__main__':main()
