"""Read existing probe04 host receipts only. No VM, COM, guard execution or original reads."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path('/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113')
SHARE=ROOT/'markingjig-phase-probe-a7ecb97-04'
PREPARED=('proposal.json','launch-probe.py','markingjig-code-a7ecb97.zip','launcher_receipts.py',
          'query-context.py','host-original-guard.py','coordinator-cad-grant.example.json')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(value,reason):
    if not value:raise RuntimeError(reason)


def audit():
    context=json.loads((SHARE/'host-execution-context.json').read_bytes())
    rows=context['commands'];by_name={row['name']:row for row in rows}
    require(len(by_name)==len(rows),'duplicate host command receipt')
    require(context['source_head']=='a7ecb97d30f0913105080d93e1725acea6e67ce7','runtime head changed')
    require(context['guest_execution_attempts']==0,'candidate execution count differs')
    require(by_name['host-originals-before']['exit']==1,'host guard failure missing')
    require(context['first_error']['message']=='host-originals-before exit 1','original first error differs')
    require(not context['cleanup_errors'],'recorded cleanup error')
    require(all(by_name[name]['exit']==0 for name in
                ('check-package','fresh-OS-context','guest-check-package','idle-restore','host-after')),
            'one stated prerequisite did not pass')
    candidate=[row for row in rows if '--execute' in row['argv']]
    require(candidate==[],'guest candidate execute command observed')
    for name in ('coordinator-cad-grant.json','entry-arrived.json','native-launch-started.json',
                 'launcher-context.json','launcher-context.partial.json','native-output',
                 'host-originals-before.json','host-originals-after.json'):
        require(not (SHARE/name).exists(),'unexpected evidence present: '+name)
    checked=json.loads((SHARE/'guest-check-package.stdout').read_bytes())
    require(checked['package_valid'] is True and checked['native_operations']==0 and checked['runtime_members']==8,
            'guest package check differs')
    source=(SHARE/'host-original-guard.py').read_bytes();tree=ast.parse(source)
    zip_calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='ZipFile']
    require(len(zip_calls)==1,'guard ZIP call is not unique')
    expr=zip_calls[0].args[0]
    require(isinstance(expr,ast.BinOp) and isinstance(expr.right,ast.Constant),'unexpected ZIP expression')
    old_name=expr.right.value
    require(old_name=='markingjig-code-c9846f6.zip' and not (SHARE/old_name).exists(),'stale ZIP reference not confirmed')
    loops=[n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple)
           and [getattr(x,'id',None) for x in n.target.elts]==['name','pinned']]
    require(len(loops)==1 and zip_calls[0].lineno<loops[0].lineno,'cannot establish failure precedes original read loop')
    stderr=(SHARE/'host-originals-before.stderr').read_text()
    require('FileNotFoundError' in stderr and old_name in stderr,'original guard error missing')
    info=(SHARE/'host-after.stdout').read_text()
    require('Pause idle: on' in info,'idle restoration not proved by after receipt')
    frozen={}
    for number in ('02','03','04'):
        folder=SHARE if number=='04' else ROOT/('markingjig-phase-probe-c9846f6-'+number)
        manifest=json.loads((folder/'review-manifest.json').read_bytes())['files']
        names=PREPARED if number=='04' else tuple(n.replace('a7ecb97','c9846f6') for n in PREPARED)
        for name in names:require(digest(folder/name)==manifest[name]['sha256'],'frozen file changed: '+str(folder/name))
        frozen[number]=True
    evidence_names=('host-execution-context.json','host-originals-before.stderr','guest-check-package.stdout',
                    'guest-check-package.stderr','idle-restore.stdout','host-after.stdout','host-original-guard.py',
                    'proposal.json','launch-probe.py','markingjig-code-a7ecb97.zip')
    return dict(schema='swcli.markingjig-probe04-preflight-failure-audit.v1',
                status='stopped-before-candidate-execution',source_head=context['source_head'],product_head=context['product_head'],
                allocation_id=context['allocation_id'],original_outer_first_error=context['first_error'],
                guard_error=dict(type='FileNotFoundError',referenced_ZIP=old_name,actual_ZIP='markingjig-code-a7ecb97.zip',
                                 ZIP_open_line=zip_calls[0].lineno,original_read_loop_line=loops[0].lineno),
                host_and_guest_package_checks_passed=True,
                guest_OS_queries=1,guest_package_checks=1,guest_candidate_execute_commands=0,
                formal_grant_present=False,entry_or_native_receipts_present=False,CAD_or_GetBodies3_attempts=0,
                fresh_eleven_original_proof_available=False,original_before_or_after_guard_completed=False,
                historical_host_after_idle_pause='on',cleanup_errors=context['cleanup_errors'],
                frozen_prepared_files_unchanged=frozen,evidence_sha256={n:digest(SHARE/n) for n in evidence_names},
                original_finished_utc=context['finished_utc'],
                validation_gap='22 offline checks compiled/hashed guard source, but did not exercise its ZIP filename linkage',
                next_step_owner='root prepares fresh05 with guard ZIP linkage fix and real ZIP parsing precheck; this audit performs no repair',
                own_operations=dict(VM=0,COM=0,CAD=0,business_original_reads=0,frozen_file_writes=0,push=0,new_CI=0),
                limits=['package_valid is not full host original preflight success',
                        'no new eleven-original before/after proof may be borrowed from earlier runs',
                        'guest OS query and check-package ran; zero guest candidate execute does not mean zero guest commands'])


if __name__=='__main__':print(json.dumps(audit(),indent=2,ensure_ascii=False))
