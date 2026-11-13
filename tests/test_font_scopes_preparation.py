"""Offline/durable evidence fault injection; no VM, COM, network or native CI."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import test_document_font_scopes as portable
from swcli.font_scope_candidates import NEXT_FONT_LINKED_READS
from swcli.font_scope_evidence import LinkedFontJournal
from swcli.font_snapshot import font_snapshot
from swcli.hosts.windows_font_scope_candidates import read_linked_font_defaults, read_guarded_linked_font_defaults

ROOT=Path(__file__).resolve().parents[1]
HEAD='a'*40


def module(name):
    spec=importlib.util.spec_from_file_location('_prep_'+name.replace('-','_'),ROOT/'scripts/ci'/name)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class DurableFontWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'linked.jsonl'
        self.fixture=portable.FontScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.raw=deepcopy(self.fixture.native['tables'])
        self.journal=LinkedFontJournal(self.path,kind='part',source_head=HEAD)

    def boundary(self,label,raw=None):
        raw=self.raw if raw is None else raw
        self.journal.begin(label,mutation=dict(attempted=label.startswith('changed-'),may_have_changed=label.startswith('changed-')))
        for kind in NEXT_FONT_LINKED_READS['tables']:
            self.journal.observe(kind,font_snapshot(raw),raw)
        return self.journal.complete()

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_every_type_retains_full_before_after_and_explicit_old_new_values(self):
        self.boundary('initial')
        changed=deepcopy(self.raw);changed['TypeFaceName']='Times New Roman'
        result=self.boundary('changed-typeface',changed)
        self.assertEqual(len(self.records()),14)
        self.assertFalse(result['inheritance_acceptance']);self.assertFalse(result['public_acceptance'])
        for kind in NEXT_FONT_LINKED_READS['tables']:
            self.assertEqual(result['before'][kind]['native_font'],self.raw)
            self.assertEqual(result['after'][kind]['native_font'],changed)
            self.assertEqual(result['changes'][kind],{'TypeFaceName':{'before':'Arial','after':'Times New Roman'}})
            self.assertEqual(len(result['after'][kind]['font']),17)
        rows=[r for r in self.records() if r['phase']=='font' and r['boundary']=='changed-typeface']
        self.assertEqual(len(rows),5)
        self.assertTrue(all(r['before']['native_font']==self.raw and r['after']['native_font']==changed for r in rows))

    def test_fsync_failure_preserves_partial_receipt_and_disables_retry(self):
        self.boundary('initial')
        self.journal.begin('changed-typeface',mutation=dict(attempted=True,may_have_changed=True))
        with patch('swcli.font_scope_evidence.os.fsync',side_effect=OSError('first journal fsync failure')):
            with self.assertRaisesRegex(OSError,'first journal fsync failure'):
                self.journal.observe('bom',font_snapshot(self.raw),self.raw)
        self.assertTrue(self.journal.failed)
        with self.assertRaisesRegex(RuntimeError,'already failed'):
            self.journal.observe('bom',font_snapshot(self.raw),self.raw)
        begin=next(r for r in self.records() if r['boundary']=='changed-typeface' and r['phase']=='begin')
        self.assertEqual(begin['mutation'],dict(attempted=True,may_have_changed=True))
        self.assertEqual(set(begin['before']),set(NEXT_FONT_LINKED_READS['tables']))
        self.assertFalse(any(r['phase']=='complete' and r['boundary']=='changed-typeface' for r in self.records()))

    def test_mid_getter_failure_leaves_original_and_observed_values_without_completing(self):
        self.boundary('initial')
        self.journal.begin('changed-typeface',mutation=dict(attempted=True,may_have_changed=True))
        changed=deepcopy(self.raw);changed['TypeFaceName']='Times New Roman'
        getter=Mock(side_effect=[portable.Format(changed),portable.Format(changed),RuntimeError('third getter failed')])
        constants={'swDetailingNoOptionSpecified':0}
        constants.update({pair[0]:index for index,pair in enumerate(NEXT_FONT_LINKED_READS['tables'].values(),10)})
        document=SimpleNamespace(Extension=SimpleNamespace(GetUserPreferenceTextFormat=getter))
        with self.assertRaisesRegex(RuntimeError,'third getter failed'):
            read_linked_font_defaults(document,constants,'tables',on_font=self.journal.observe)
        self.assertEqual(getter.call_count,3)
        rows=[r for r in self.records() if r['boundary']=='changed-typeface']
        self.assertEqual([r['phase'] for r in rows],['begin','font','font'])
        self.assertEqual(rows[0]['before']['hole']['native_font'],self.raw)
        self.assertEqual(rows[-1]['after']['native_font'],changed)
        with self.assertRaisesRegex(RuntimeError,'all five'):
            self.journal.complete()

    def test_linked_reads_cannot_change_foreground_pointer_state_or_target_identity(self):
        for fault in ('foreground-pointer','foreground-dirty','target-path'):
            with self.subTest(fault=fault):
                f=portable.FontScopeTests();f.setUp()
                try:
                    constants={'swDetailingNoOptionSpecified':0}
                    constants.update({pair[0]:index for index,pair in enumerate(NEXT_FONT_LINKED_READS['tables'].values(),10)})
                    calls=[0]
                    def get_font(*args):
                        calls[0]+=1
                        if calls[0]==3:
                            if fault=='foreground-pointer':f.app.ActiveDoc=object()
                            elif fault=='foreground-dirty':f.front.GetSaveFlag=lambda:True
                            else:f.document.GetPathName=lambda:'changed.SLDPRT'
                        return portable.Format(self.raw)
                    f.extension.GetUserPreferenceTextFormat.side_effect=get_font
                    with self.assertRaises(RuntimeError):
                        read_guarded_linked_font_defaults(app=f.app,document=f.document,constants=constants,scope='tables')
                    f.extension.SetUserPreferenceTextFormat.assert_not_called()
                    f.app.ActivateDoc3.assert_not_called()
                finally:f.doCleanups()

    def test_callback_storage_failure_stops_before_next_linked_getter(self):
        self.journal.begin('initial',mutation=dict(attempted=False,may_have_changed=False))
        getter=Mock(return_value=portable.Format(self.raw))
        constants={'swDetailingNoOptionSpecified':0}
        constants.update({pair[0]:index for index,pair in enumerate(NEXT_FONT_LINKED_READS['tables'].values(),10)})
        with patch('swcli.font_scope_evidence.os.fsync',side_effect=OSError('disk failure')):
            with self.assertRaisesRegex(OSError,'disk failure'):
                read_linked_font_defaults(SimpleNamespace(Extension=SimpleNamespace(GetUserPreferenceTextFormat=getter)),
                    constants,'tables',on_font=self.journal.observe)
        getter.assert_called_once()

    def test_repeated_missing_out_of_order_and_inconsistent_fonts_cannot_complete(self):
        with self.assertRaisesRegex(ValueError,'out of order'):
            self.journal.begin('changed-bold',mutation=dict(attempted=True,may_have_changed=True))
        self.journal.begin('initial',mutation=dict(attempted=False,may_have_changed=False))
        with self.assertRaises(ValueError):self.journal.observe('general',font_snapshot(self.raw),self.raw)
        self.journal.observe('bom',font_snapshot(self.raw),self.raw)
        with self.assertRaises(ValueError):self.journal.observe('bom',font_snapshot(self.raw),self.raw)
        wrong=font_snapshot(self.raw);wrong['bold']=True
        with self.assertRaisesRegex(ValueError,'differ'):self.journal.observe('general',wrong,self.raw)
        with self.assertRaisesRegex(RuntimeError,'all five'):self.journal.complete()
        with self.assertRaises(FileExistsError):LinkedFontJournal(self.path,kind='part',source_head=HEAD)

    def test_caller_mutation_cannot_rewrite_previous_or_journal_values(self):
        raw=deepcopy(self.raw);font=font_snapshot(raw)
        self.journal.begin('initial',mutation=dict(attempted=False,may_have_changed=False))
        self.journal.observe('bom',font,raw)
        raw['Bold']=True;font['bold']=True
        self.assertFalse(self.journal.current['bom']['native_font']['Bold'])
        self.assertFalse(self.records()[-1]['after']['font']['bold'])

    def test_exact_head_must_exist_and_match_environment_before_worker_is_started(self):
        runner=module('run-font-scopes-calibration.py')
        args=SimpleNamespace(scope='tables',source_head=HEAD)
        self.assertEqual(runner.source_head(args,{}),HEAD)
        with self.assertRaises(ValueError):runner.source_head(args,{'GITHUB_SHA':'b'*40})
        with self.assertRaises(ValueError):runner.source_head(SimpleNamespace(scope='tables',source_head=None),{})
        self.assertIsNone(runner.source_head(SimpleNamespace(scope=None),{}))
        with self.assertRaises(ValueError):runner.source_head(SimpleNamespace(scope=None,source_head=HEAD),{'GITHUB_SHA':'b'*40})
        with self.assertRaises(ValueError):runner.source_head(SimpleNamespace(scope=None,source_head='main'),{})
        with patch.dict(runner.os.environ,{},clear=True),patch.object(runner.subprocess,'Popen') as launch:
            with self.assertRaises(ValueError):runner.main(['--scope','tables','--output-dir',str(self.path.parent/'out'),
                '--swconst','not-used.tlb','--drawing-template','not-used.drwdot'])
            launch.assert_not_called()


class FontSourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.builder=module('prepare-font-scopes-next.py')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.git('init','-q')
        self.git('config','core.autocrlf','false')
        for name in ('pyproject.toml','scripts/ci/run-font-scopes-calibration.py',
                     'scripts/ci/verify-font-scopes-calibration.py','scripts/ci/verify-font-scopes-next-offline.py',
                     'a.c','a/child.py','unicode-字体.txt'):
            path=self.repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'source\n')
        self.git('add','.')
        self.git('-c','user.name=Offline Test','-c','user.email=offline@example.invalid',
            '-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','-qm','offline source fixture')
        self.head=self.git('rev-parse','HEAD').decode().strip()

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.repo),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout

    def test_same_exact_commit_has_identical_bundle_and_manifest_across_output_paths(self):
        first=self.builder.build(self.repo,self.head,self.root/'first')
        second=self.builder.build(self.repo,self.head,self.root/'second')
        self.assertEqual(first,second)
        self.assertEqual((self.root/'first/manifest.json').read_bytes(),(self.root/'second/manifest.json').read_bytes())
        self.assertEqual(first['source_archive_sha256'],second['source_archive_sha256'])
        self.assertFalse(first['plan']['native_executed'])
        self.assertFalse(first['plan']['public_acceptance'])
        self.assertEqual([g['scope'] for g in first['plan']['groups']],['dimensions','tables'])
        self.builder.verify(self.root/'first',self.head)

    def test_dirty_checkout_wrong_head_or_existing_destination_is_refused(self):
        with self.assertRaisesRegex(ValueError,'differs from checkout'):
            self.builder.build(self.repo,'b'*40,self.root/'wrong')
        (self.repo/'a.c').write_text('dirty')
        with self.assertRaisesRegex(ValueError,'must be clean'):
            self.builder.build(self.repo,self.head,self.root/'dirty')
        self.assertFalse((self.root/'dirty').exists())
        self.git('checkout','--','a.c')
        (self.root/'already').mkdir()
        with self.assertRaises(FileExistsError):self.builder.build(self.repo,self.head,self.root/'already')

    def test_rehashing_tampered_file_and_manifest_still_cannot_match_pinned_git_commit(self):
        output=self.root/'tamper';manifest=self.builder.build(self.repo,self.head,output)
        archive=output/manifest['source_archive']
        with zipfile.ZipFile(archive) as bundle:
            entries=[(item,bundle.read(item)) for item in bundle.infolist()]
        with zipfile.ZipFile(archive,'w') as bundle:
            for item,data in entries:
                if item.filename=='source/a.c':data=b'changed source\n'
                bundle.writestr(item,data)
        data=b'changed source\n'
        row=next(r for r in manifest['files'] if r['path']=='a.c')
        row.update(size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),git_blob=self.builder.object_hash('blob',data))
        manifest['source_archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
        (output/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'expected commit tree'):
            self.builder.verify(output,self.head)

    def test_plan_cannot_claim_native_acceptance_or_expand_budget_and_scopes(self):
        output=self.root/'plan';manifest=self.builder.build(self.repo,self.head,output)
        for change in ({'native_executed':True},{'public_acceptance':True},{'group_timeout_seconds':1801},
                       {'groups':manifest['plan']['groups']+[{'scope':'notes'}]}):
            modified=deepcopy(manifest);modified['plan'].update(change)
            (output/'manifest.json').write_text(json.dumps(modified))
            with self.assertRaisesRegex(ValueError,'closed preparation profile'):
                self.builder.verify(output,self.head)

    def test_archive_extra_entry_and_unsafe_paths_are_refused(self):
        output=self.root/'extra';manifest=self.builder.build(self.repo,self.head,output)
        archive=output/manifest['source_archive']
        with zipfile.ZipFile(archive,'a') as bundle:bundle.writestr('../extra',b'bad')
        manifest['source_archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
        (output/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):self.builder.verify(output,self.head)
        for path in ('../escape','/absolute','C:/drive','a\\b','a/../b'):
            with self.assertRaises(ValueError):self.builder.safe_path(path)


class FontOfflineRequestGateTests(unittest.TestCase):
    def test_both_scopes_frontends_negatives_and_partial_receipts_are_offline_only(self):
        gate=module('verify-font-scopes-next-offline.py')
        result=gate.offline_gate()
        self.assertEqual(result['frontend_checks'],42)
        self.assertEqual(result['invalid_request_checks'],10)
        self.assertEqual(result['partial_receipt_checks'],2)
        self.assertFalse(result['native_executed'])
        self.assertFalse(result['public_acceptance'])
        self.assertFalse(result['inheritance_acceptance'])

    def test_installed_source_or_schema_drift_cannot_use_a_matching_version_string(self):
        gate=module('verify-font-scopes-next-offline.py')
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';installed=Path(tmp)/'installed';source.mkdir();installed.mkdir()
            for root in (source,installed):
                (root/'__init__.py').write_text('VERSION = "same"')
                (root/'contract.json').write_text('{"closed":true}')
            self.assertEqual(gate.verify_installed_sources(source,installed),2)
            (installed/'contract.json').write_text('{"closed":false}')
            with self.assertRaisesRegex(RuntimeError,'installed source differs'):
                gate.verify_installed_sources(source,installed)
            (installed/'extra.py').touch()
            with self.assertRaisesRegex(RuntimeError,'files differ'):
                gate.verify_installed_sources(source,installed)

    def test_sdk_context_loss_is_a_real_gate_failure_before_transport(self):
        gate=module('verify-font-scopes-next-offline.py')
        cls=type(gate.Client().document);original=cls.font_scope_set
        def missing_lease(self,**kwargs):
            kwargs['lease_id']=None
            return original(self,**kwargs)
        with patch.object(cls,'font_scope_set',missing_lease):
            with self.assertRaises(Exception):gate.offline_gate()


if __name__=='__main__':unittest.main()
