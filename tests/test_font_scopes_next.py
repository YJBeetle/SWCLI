"""Portable candidate/dispatcher tests; never instantiate native COM."""
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

import test_document_font_scopes as portable
from swcli.daemon import operations
from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.font_scope_candidates import NEXT_FONT_SCOPES, NEXT_FONT_WRITE_PROFILES, NEXT_FONT_LINKED_READS
from swcli.hosts.windows_font_scope_candidates import read_linked_font_defaults
from swcli.hosts import windows_document_font_scopes as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location('_next_' + name.replace('-', '_'), ROOT / 'scripts/ci' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NextFontScopesTests(unittest.TestCase):
    @contextmanager
    def fixture(self, kind=1):
        f = portable.FontScopeTests()
        f.setUp()
        try:
            f.app.RevisionNumber = lambda: '33.5.0'
            f.document.GetType = lambda: kind
            if kind == 3:
                sheet_sketch, template_sketch = object(), object()
                sheet = SimpleNamespace(GetName=lambda: 'Sheet1', GetTemplateSketch=lambda: template_sketch)
                view = SimpleNamespace(GetName2=lambda: 'Sheet1', GetSketch=lambda: sheet_sketch,
                                       GetReferencedModelName=lambda: '')
                f.document.GetCurrentSheet = lambda: sheet
                f.document.GetFirstView = lambda: view
                f.document.GetEditSheet = lambda: True
                f.document.ActiveDrawingView = None
                f.document.SketchManager.ActiveSketch = sheet_sketch
            f.registry = DocumentRegistry(f.app)
            f.entry = f.registry.register(f.document)
            f.registry.set_current(f.registry.register(f.front), session_id='writer')
            f.lease = f.registry.acquire_lease(f.entry, session_id='writer', ttl_seconds=60)
            yield f
        finally:
            f.doCleanups()

    def edit(self, f, **kwargs):
        with patch.object(operations, 'set_document_font_scope_windows', adapter._calibrate_next_document_font_scope), \
             patch.object(adapter, '_native_windows_runtime', return_value=True):
            return f.edit(**kwargs)

    def test_next_profile_does_not_expand_public_catalog_or_add_protocol_switch(self):
        self.assertEqual(NEXT_FONT_SCOPES, ('dimensions', 'tables'))
        public = OPERATION_CATALOG['document.font-scope-set'].parameters['x-swcli-font-write-profiles']
        self.assertEqual(set(public), {'notes'})
        for scope in NEXT_FONT_SCOPES:
            self.assertEqual(NEXT_FONT_WRITE_PROFILES[scope]['solidworks_revision'], '33.5.0')
            self.assertEqual(NEXT_FONT_WRITE_PROFILES[scope]['document_types'], (1, 2, 3))
            with self.fixture() as f, patch.object(adapter, '_native_windows_runtime', return_value=True):
                result = f.edit(scope=scope)
                self.assertEqual(result['error']['type'], 'DocumentFontScopeNotCalibrated')
                f.assert_no_mutation()
                params = dict(scope=scope, field='bold', value=True, expected_fonts=f.fonts(), candidate_profile=True)
                with self.assertRaises(ValueError): validate_operation_request('document.font-scope-set', params)

    def test_both_candidates_seven_fields_all_document_kinds_use_normal_guarded_route(self):
        targets = [('typeface','Times New Roman'), ('bold',True), ('italic',True),
                   ('underline',True), ('strikeout',True), ('height_mm',3.5), ('height_points',14)]
        for scope in NEXT_FONT_SCOPES:
            for kind in (1, 2, 3):
                for field, value in targets:
                    with self.subTest(scope=scope, kind=kind, field=field), self.fixture(kind) as f:
                        before = f.fonts()
                        result = self.edit(f,scope=scope,field=field,value=value)
                        validate_operation_result('document.font-scope-set', result)
                        self.assertTrue(result['ok'],result)
                        self.assertEqual(result['mutation'],dict(attempted=True,may_have_changed=True))
                        self.assertTrue(result['document']['modified'])
                        self.assertFalse(result['document']['active'])
                        self.assertFalse(result['document']['current'])
                        for other in set(before)-{scope}: self.assertEqual(result['fonts'][other],before[other])
                        f.extension.SetUserPreferenceTextFormat.assert_called_once()
                        expected_pair = tuple(f.constants[n] for n in portable.FONT_SCOPES[scope])
                        self.assertEqual(f.extension.SetUserPreferenceTextFormat.call_args.args[:2],expected_pair)
                        writes=[write for obj in f.objects for write in obj.writes]
                        self.assertEqual(len(writes),1)
                        self.assertEqual(writes[0][0],portable.FONT_MEMBERS[field])
                        if field=='height_mm':
                            self.assertEqual(writes[0][1],0.0035)
                            self.assertEqual(result['fonts'][scope]['height_mode'],'millimeters')
                        if field=='height_points':
                            self.assertEqual(writes[0][1],14)
                            self.assertEqual(result['fonts'][scope]['height_mode'],'points')
                        f.app.ActivateDoc3.assert_not_called()

    def test_candidate_runtime_revision_scope_and_kind_refuse_before_font_allocation(self):
        for scope,revision,native,kind in [('notes','33.5.0',True,1),('dimensions','33.4.0',True,1),
                ('tables','34.0.0',True,1),('dimensions','33.5.0',False,1),('tables','33.5.0',True,9)]:
            with self.subTest(scope=scope,revision=revision,native=native,kind=kind), self.fixture() as f:
                f.app.RevisionNumber=lambda:revision
                f.document.GetType=lambda:kind
                with patch.object(adapter,'_native_windows_runtime',return_value=native):
                    result=adapter._calibrate_next_document_font_scope(app=f.app,document=f.document,
                        scope=scope,field='bold',value=True,expected_fonts=f.fonts())
                self.assertEqual(result['error']['type'],'DocumentFontScopeNotCalibrated')
                self.assertEqual(result['mutation'],dict(attempted=False,may_have_changed=False))
                f.extension.GetUserPreferenceTextFormat.assert_not_called()
                f.assert_no_mutation()

    def test_every_member_of_every_scope_participates_in_candidate_cas(self):
        for target in NEXT_FONT_SCOPES:
            with self.fixture() as f:
                for scope,font in f.fonts().items():
                    for field,value in font.items():
                        with self.subTest(target=target,scope=scope,field=field):
                            stale=deepcopy(f.fonts())
                            stale[scope][field]=(not value if type(value) is bool else
                                ('points' if value=='millimeters' else 'millimeters') if field=='height_mode' else
                                value+' different' if type(value) is str else value+1)
                            result=self.edit(f,scope=target,expected=stale)
                            self.assertEqual(result['error']['type'],'DocumentFontScopeConflict')
                            self.assertFalse(result['mutation']['attempted'])
                f.assert_no_mutation()

    def test_candidate_noop_keeps_dirty_stamp_identity_and_has_zero_setters(self):
        for scope in NEXT_FONT_SCOPES:
            with self.fixture() as f:
                before=f.registry.describe(f.entry)
                result=self.edit(f,scope=scope,field='bold',value=False)
                self.assertTrue(result['ok'],result)
                self.assertFalse(result['changed'])
                self.assertEqual(result['document'],before)
                f.assert_no_mutation()

    def test_candidate_lease_stamp_readonly_and_edit_context_guards(self):
        for scope in NEXT_FONT_SCOPES:
            with self.fixture() as f:
                with self.assertRaises(DocumentLeaseConflict): self.edit(f,scope=scope,session='contender')
                with self.assertRaises(operations.DocumentUpdateConflict): self.edit(f,scope=scope,stamp=8)
                f.document.IsOpenedReadOnly=lambda:True
                result=self.edit(f,scope=scope)
                self.assertFalse(result['mutation']['attempted'])
                f.assert_no_mutation()
            with self.fixture() as f:
                f.document.SketchManager.ActiveSketch=object()
                result=self.edit(f,scope=scope)
                self.assertFalse(result['mutation']['attempted'])
                f.assert_no_mutation()

    def test_candidate_live_setter_failure_preserves_partial_without_retry_or_rollback(self):
        for scope in NEXT_FONT_SCOPES:
            for error in (False,RuntimeError('first candidate native failure')):
                with self.subTest(scope=scope,error=error), self.fixture() as f:
                    f.live=True
                    f.extension.SetUserPreferenceTextFormat.side_effect=[error] if error is False else error
                    result=self.edit(f,scope=scope)
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['mutation'],dict(attempted=True,may_have_changed=True))
                    self.assertTrue(f.native[scope]['Bold'])
                    self.assertTrue(f.modified)
                    f.extension.SetUserPreferenceTextFormat.assert_called_once()
                    self.assertEqual(sum(len(obj.writes) for obj in f.objects),1)
                    f.app.ActivateDoc3.assert_not_called()

    def test_linked_table_witnesses_are_complete_reads_only_and_never_claim_inheritance(self):
        with self.fixture() as f:
            constants={"swDetailingNoOptionSpecified":91}
            pairs={}
            for index,(label,(preference,option)) in enumerate(NEXT_FONT_LINKED_READS['tables'].items(),500):
                constants[preference]=index
                pairs[index,91]=portable.Format(f.native['tables'])
            getter=Mock(side_effect=lambda pref,option:pairs[pref,option])
            document=SimpleNamespace(Extension=SimpleNamespace(GetUserPreferenceTextFormat=getter))
            observed=read_linked_font_defaults(document,constants,'tables')
            self.assertEqual(set(observed['fonts']),{'bom','general','hole','revision','title_block'})
            self.assertEqual(getter.call_count,5)
            self.assertTrue(all(len(row)==17 for row in observed['fonts'].values()))
            self.assertTrue(all(len(row)==17 for row in observed['native_fonts'].values()))
            self.assertIn('inheritance not accepted',observed['status'])
            self.assertFalse(any(obj.writes for obj in pairs.values()))
            getter.side_effect=None;getter.return_value=None
            with self.assertRaisesRegex(RuntimeError,'linked table font unavailable'):
                read_linked_font_defaults(document,constants,'tables')
            getter.reset_mock()
            with self.assertRaises(ValueError): read_linked_font_defaults(document,constants,'notes')
            getter.assert_not_called()

    def test_next_watchdog_routes_one_scope_and_rejects_notes_or_inheritance_profile(self):
        runner=script('run-font-scopes-calibration.py')
        for scope in NEXT_FONT_SCOPES:
            args=SimpleNamespace(profile='internal',scope=scope,swconst=Path('official.tlb'),drawing_template=Path('gb.drwdot'))
            command=runner.worker_command(args,Path('evidence'))
            self.assertEqual(command[-2:],['--scope',scope])
            self.assertIn('-I',command)
        for profile,scope in [('inheritance-seed','dimensions'),('internal','notes'),('internal','anything')]:
            args=SimpleNamespace(profile=profile,scope=scope)
            with self.assertRaises(ValueError): runner.worker_command(args,Path('evidence'))
        self.assertEqual((runner.NATIVE_TIMEOUT_SECONDS,runner.GROUP_TIMEOUT_SECONDS),(600,1800))

    def test_next_entry_passes_selected_scope_to_reused_native_harness_without_com(self):
        module=script('verify-font-scopes-calibration.py')
        for scope in NEXT_FONT_SCOPES:
            with tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp); library=base/'swconst.tlb'; template=base/'gb.drwdot'
                library.touch(); template.touch()
                with patch.object(module.harness,'read_constants'),patch.object(module.harness,'run',return_value=0) as run:
                    result=module.main(['--output-dir',str(base/'out'),'--swconst',str(library),
                                       '--drawing-template',str(template),'--scope',scope])
                    self.assertEqual(result,0)
                    self.assertEqual(run.call_args.kwargs['diagnostic_case'],'font-scopes-next-'+scope)
                    with patch.object(module,'calibrate_case',return_value='probe') as case:
                        self.assertEqual(run.call_args.kwargs['case_runner'](None,None,{}),'probe')
                        self.assertEqual(case.call_args.kwargs['selected_scopes'],(scope,))
                        self.assertIs(case.call_args.kwargs['candidate_setter'],adapter._calibrate_next_document_font_scope)


if __name__=='__main__':
    unittest.main()
