"""Offline audit integrity faults; synthetic evidence never validates CAD."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('preference_public_audit',ROOT/'scripts/dev/audit-document-properties-public.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class PublicAuditIntegrity(unittest.TestCase):
    def fixture(self,root):
        extracted=root/'original';public=extracted/'public';public.mkdir(parents=True)
        context={'public_context':{'run_id':'123','run_attempt':'1'}}
        (public/'context.json').write_text(json.dumps(context))
        archive=root/'original.zip'
        with zipfile.ZipFile(archive,'w') as z:z.write(public/'context.json','public/context.json')
        run={'status':'completed','conclusion':'success','head_sha':'a'*40,'run_attempt':1,'event':'workflow_dispatch','workflow_id':362005755,'repository':{'full_name':'YJBeetle/SWCLI'},'head_branch':'codex/docprops-calibration-performance','id':123}
        artifact={'id':456,'name':'swcli-docprops-public-123-1','workflow_run':{'head_sha':'a'*40,'id':123},'digest':'sha256:'+audit.sha(archive),'size_in_bytes':archive.stat().st_size}
        run_path=root/'run.json';run_path.write_text(json.dumps(run))
        artifact_path=root/'artifacts.json';artifact_path.write_text(json.dumps({'artifacts':[artifact]}))
        return public,archive,run_path,artifact_path

    def test_official_digest_binds_every_extracted_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.fixture(Path(folder))
            self.assertTrue(audit.verify_download(args[0],'a'*40,*args[1:])['official_digest_verified'])
            (args[0]/'context.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'extracted bytes'):audit.verify_download(args[0],'a'*40,*args[1:])

    def test_wrong_head_digest_or_unlisted_original_refused(self):
        for fault in ('head','digest','unlisted'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as folder:
                args=self.fixture(Path(folder));head='a'*40
                if fault=='head':head='b'*40
                elif fault=='digest':
                    data=json.loads(args[3].read_text());data['artifacts'][0]['digest']='sha256:'+'0'*64;args[3].write_text(json.dumps(data))
                else:(args[0]/'unlisted').write_bytes(b'other')
                with self.assertRaises(ValueError):audit.verify_download(args[0],head,*args[1:])

    def test_unknown_host_log_line_or_reordered_request_is_not_silently_lost(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trace.log'
            rows=[{'event':'swcli.native-call','request_id':'a','phase':'begin'}, {'event':'swcli.native-call','request_id':'b','phase':'begin'}, {'event':'swcli.native-call','request_id':'a','phase':'end'}]
            path.write_text('\n'.join(map(json.dumps,rows)))
            indexed=audit.IndexedTrace(path);indexed.request='a'
            self.assertEqual([json.loads(line)['phase'] for line in indexed.read_text().splitlines()],['begin','end'])
            path.write_text('{"event":"swcli.native-call", bad')
            with self.assertRaisesRegex(ValueError,'malformed'):audit.IndexedTrace(path)

    def test_refusal_must_not_reach_dirty_or_setter(self):
        proof={'request_id':'request','native_setters':[],'text_format_assignments':[],'set_save_flag_calls':0}
        row={'result':{'ok':False,'error':{'type':'ValueError'},'mutation':{'attempted':False,'may_have_changed':False}},'native_trace':proof}
        audit.refusal(row,'ValueError',{'request':proof})
        for key,value in (('set_save_flag_calls',1),('native_setters',['setter']),('text_format_assignments',['set'])):
            with self.subTest(key=key):
                original=proof[key];proof[key]=value
                with self.assertRaisesRegex(ValueError,'mutation'):audit.refusal(row,'ValueError',{'request':proof})
                proof[key]=original
