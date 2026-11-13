"""Offline CLI/SDK/MCP contract gate with synthetic transport, never native proof."""
import argparse
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import re
from unittest.mock import patch

import swcli
from swcli.cli import build_parser, _typed_operation
from swcli.document_font_scopes import NATIVE_FONT_WRITE_PROFILES, validate_font_scopes
from swcli.mcp import DaemonBridge
from swcli.operation_schemas import OPERATION_CATALOG
from swcli.sdk import Client


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def snapshot():
    font = dict(typeface='Arial', height_mm=3.0, height_points=8, height_mode='millimeters',
        bold=False, italic=False, underline=False, strikeout=False, backwards=False,
        upside_down=False, vertical=False, width_factor=1.0, char_spacing_factor=1.0,
        escapement=0.0, line_spacing=1.0, line_length=0.0, oblique_angle=0.0)
    return {scope:deepcopy(font) for scope in ('dimensions','notes','tables','annotations')}


def receipt(request_id, *, partial=False):
    return dict(api_version='swcli/v1', success=True, request_id=request_id, duration_ms=0.0,
        result=dict(ok=False, action='document.font-scope-set',
            mutation=dict(attempted=partial, may_have_changed=partial),
            error=dict(type='SyntheticNativeFirstFailure' if partial else 'DocumentFontScopeNotCalibrated',
                       message='offline synthetic receipt; no native call')))


def offline_gate():
    public = OPERATION_CATALOG['document.font-scope-set'].parameters['x-swcli-font-write-profiles']
    require(set(public) == set(NATIVE_FONT_WRITE_PROFILES) == {'notes'}, 'new public font scope was enabled')
    fonts = snapshot()
    validate_font_scopes(fonts)
    context = dict(document_id='d-abc123', expected_update_stamp=17, lease_id='l-abc123abc123')
    fields = [('typeface','Times New Roman'),('height_mm',3.5),('height_points',14),
              ('bold',True),('italic',True),('underline',True),('strikeout',True)]
    proofs = []
    with patch('socket.create_connection', side_effect=RuntimeError('offline gate forbids network')), \
         patch('socket.socket.connect', side_effect=RuntimeError('offline gate forbids network')), \
         patch('socket.socket.connect_ex', side_effect=RuntimeError('offline gate forbids network')), \
         patch('subprocess.Popen', side_effect=RuntimeError('offline gate forbids process launch')):
        client, bridge, parser = Client(session_id='font-offline'), DaemonBridge(session_id='font-offline'), build_parser()
        for scope in ('dimensions','tables'):
            for field,value in fields:
                params = dict(scope=scope,field=field,value=value,expected_fonts=deepcopy(fonts))
                args = parser.parse_args(['document','font-scope-set',scope,field,json.dumps(value),
                    '--if-fonts',json.dumps(fonts),'--document',context['document_id'],
                    '--if-update-stamp','17','--lease',context['lease_id'],'--json'])
                name, values, as_json, document, stamp, lease = _typed_operation(args)
                require((name,values,as_json,document,stamp,lease) ==
                    ('document.font-scope-set',params,True,context['document_id'],17,context['lease_id']),
                    'CLI font scope, scalar, CAS or required context differs')
                for frontend in ('sdk','mcp'):
                    request_id='offline-'+frontend+'-'+scope+'-'+field
                    envelope=receipt(request_id)
                    target='swcli.sdk.client.call_daemon' if frontend=='sdk' else 'swcli.mcp.call_daemon'
                    with patch(target,return_value=deepcopy(envelope)) as transport:
                        if frontend=='sdk':
                            result=client.document.font_scope_set(**params,**context,request_id=request_id).raw
                        else:
                            result=bridge.call('execute',dict(operation=name,parameters=params,
                                **context,request_id=request_id))
                    require(transport.call_count==1,'font transport retried or was not called exactly once')
                    require(transport.call_args.args==(name,params),'font request payload changed')
                    for key,value_context in dict(**context,request_id=request_id).items():
                        require(transport.call_args.kwargs[key]==value_context,'font request context changed: '+key)
                    require(result==envelope,'font refusal receipt changed')
                proofs.append(dict(scope=scope,field=field,frontends=['cli-parse','sdk-mock','mcp-mock']))
        negatives = []
        for change in (dict(field='bold',value=1),dict(field='height_mm',value=False),
                       dict(field='height_points',value=14.5),dict(field='typeface',value=''),
                       dict(scope='annotations'),dict(expected_fonts={}),dict(arbitrary_com='SetAnything')):
            params=dict(scope='dimensions',field='bold',value=True,expected_fonts=deepcopy(fonts))
            params.update(change)
            with patch('swcli.sdk.client.call_daemon') as transport:
                try:
                    client._execute('document.font-scope-set',params,**context)
                except Exception:
                    require(transport.call_count==0,'invalid font request reached transport')
                else:
                    raise RuntimeError('invalid font request was accepted')
            negatives.append(list(change))
        for missing in context:
            invalid_context=dict(context);invalid_context[missing]=None
            with patch('swcli.sdk.client.call_daemon') as transport:
                try:
                    client.document.font_scope_set(scope='tables',field='bold',value=True,
                        expected_fonts=fonts,**invalid_context)
                except Exception:
                    require(transport.call_count==0,'incomplete font context reached transport')
                else:
                    raise RuntimeError('incomplete font context was accepted')
            negatives.append([missing])
        for frontend in ('sdk','mcp'):
            request_id='offline-partial-'+frontend
            envelope=receipt(request_id,partial=True)
            params=dict(scope='tables',field='height_points',value=14,expected_fonts=fonts)
            target='swcli.sdk.client.call_daemon' if frontend=='sdk' else 'swcli.mcp.call_daemon'
            with patch(target,return_value=deepcopy(envelope)) as transport:
                result=(client.document.font_scope_set(**params,**context,request_id=request_id).raw
                    if frontend=='sdk' else bridge.call('execute',dict(operation='document.font-scope-set',
                        parameters=params,**context,request_id=request_id)))
            require(transport.call_count==1 and result==envelope,'partial receipt or first error was erased/retried')
    return dict(evidence_kind='offline-synthetic-font-requests',success=True,native_executed=False,
        public_acceptance=False,inheritance_acceptance=False,public_new_scopes_enabled=False,
        cases=proofs,frontend_checks=len(proofs)*3,invalid_request_checks=len(negatives),partial_receipt_checks=2)


def verify_installed_sources(source, installed):
    expected = {path.relative_to(source):path for path in source.rglob('*')
                if path.is_file() and path.suffix in ('.py','.json')}
    require(expected, 'offline source package is empty')
    actual = {path.relative_to(installed):path for path in installed.rglob('*')
              if path.is_file() and path.suffix in ('.py','.json')}
    require(set(expected)==set(actual), 'installed Python/schema files differ from source package')
    for name,path in expected.items():
        require(hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(actual[name].read_bytes()).digest(),
                'installed source differs: '+str(name))
    return len(expected)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-head',required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    require(re.fullmatch(r'[0-9a-f]{40}',args.source_head) is not None,'exact offline source head required')
    checked=verify_installed_sources(Path(__file__).resolve().parents[2]/'src/swcli',Path(swcli.__file__).resolve().parent)
    result=dict(source_head=args.source_head,installed_source_files_verified=checked,
        source_head_binding='verify the pinned source bundle separately; this gate compares installed Python/schema bytes',
        **offline_gate())
    data=json.dumps(result,sort_keys=True,indent=2)+'\n'
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:stream.write(data)
    print(data,end='')


if __name__=='__main__':
    main()
