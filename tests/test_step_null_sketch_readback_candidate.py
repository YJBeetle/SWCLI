"""Portable preselected NULL + sketch path traps; no native success claim."""
from contextlib import ExitStack,redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/ci'))
from gate_support import step_null_sketch_readback_candidate as candidate
import test_step_sketch_readback_candidate as sketch_tests
load=sketch_tests.load
from test_step_explicit_null_binding import contract
from test_step_wire_import_once import Failure


class NullSketchCandidateTests(unittest.TestCase):
    run_roundtrip=sketch_tests.SketchRoundtripTests.run_roundtrip

    def test_preselected_null_one_invoke_all_geometry_modes_and_unchanged_strict_roundtrip(self):
        for kind in ('solid-surface','wireframe','wireframe-sketches'):
            with self.subTest(kind=kind):
                case,exc,reads,app,live=self.run_roundtrip(null_candidate=True,kind=kind)
                self.assertIsNone(exc);self.assertTrue(case['success']);self.assertEqual(reads,0 if kind=='solid-surface' else 2)
                self.assertIsNone(live['document']);self.assertEqual(app.CloseDoc.call_count,2)
                raw=app.binding_raw;self.assertEqual(raw.lookups,0);self.assertEqual(raw.lazy_reads,0)
                self.assertEqual(raw._oleobj_.metadata_calls,[('GetIDsOfNames',(0,'LoadFile4'))])
                self.assertEqual([x[0] for x in raw._oleobj_.calls],['Invoke'])
                args=raw._oleobj_.calls[0][1];self.assertEqual(args[:4],(227,0,1,1));self.assertEqual(args[5],'r')
                self.assertEqual((args[6].varianttype,args[6].value),(9,None));self.assertEqual(args[7].varianttype,16387)
                self.assertIsNot(args[6],app.data);e=case['null_sketch_import']
                self.assertFalse(e['single_null_causal_claim']);self.assertFalse(e['factory_argument_used'])
                self.assertIn('changed_variables_from_f56f792',e['binding']);self.assertNotIn('changed_variables_from_60f1cf8',e['binding'])
                self.assertEqual(case['sketch_observer_preferences']['requested'],candidate.PUBLIC_PROFILE)
                self.assertIn('explicit NULL',case['import_return']['import_data'])

    def test_null_none_errors1_remains_first_failure_no_factory_fallback_or_save(self):
        # This is the new route returning the same genuine failure; it must stay failed.
        case,exc,reads,app,live=self.run_roundtrip(null_candidate=True,load_error=1,null_document=True)
        self.assertIsNotNone(exc);self.assertEqual(str(exc),'STEP geometry readback failed')
        self.assertFalse(case.get('success',False));self.assertEqual(reads,0)
        self.assertNotIn('imported_save',case);self.assertEqual(len(app.binding_raw._oleobj_.calls),1)
        self.assertEqual(app.binding_raw.lookups,0);self.assertEqual(case['null_sketch_import']['errors'],1)

    def test_unknown_name_id_stops_before_native_and_preserves_full_restore(self):
        for value in (228,None,Failure('first name error')):
            with self.subTest(value=type(value).__name__):
                case,exc,reads,app,live=self.run_roundtrip(null_candidate=True,null_dispid=value,expected_loads=0)
                self.assertIsNotNone(exc);self.assertEqual(reads,0);self.assertEqual(app.binding_raw._oleobj_.calls,[])
                self.assertFalse(case['null_sketch_import']['binding']['explicit_invoke_attempted'])
                self.assertNotIn('imported_geometry',case);self.assertTrue(case['sketch_observer_preferences']['restored'])

    def test_different_full_profile_rejects_without_setting_neutral_or_calling_native(self):
        case,exc,reads,app,live=self.run_roundtrip(null_candidate=True,neutral_free=True,expected_loads=0)
        self.assertIn('eight-value profile differs',str(exc));self.assertEqual(reads,0)
        self.assertEqual(app.binding_raw._oleobj_.calls,[])
        self.assertTrue(app.values['swImportNeutral_FreeCurvesAndPoints'])
        self.assertNotIn('swImportNeutral_FreeCurvesAndPoints',[k for k,v in app.writes])

    def test_null_model_does_not_bypass_feature_health_or_reopened_geometry(self):
        for options in ({'initial_health':1},{'reopened_health':1},{'reopened_lengths':[10]*4+[30]*4+[41]*4}):
            with self.subTest(options=options):
                case,exc,reads,app,live=self.run_roundtrip(null_candidate=True,**options)
                self.assertIsNotNone(exc);self.assertFalse(case.get('success',False))
                self.assertEqual(len(app.binding_raw._oleobj_.calls),1)
                if 'initial_health' in options:self.assertNotIn('imported_save',case)
                else:self.assertFalse(case['reopened_imported_geometry']['complete'])

    def test_prehost_version_or_source_signature_failure_cannot_start_a_host(self):
        path=Path('/fake/swconst.tlb')
        with mock.patch.object(candidate.importlib.metadata,'version',return_value='313'),mock.patch.object(candidate.step_null_binding,'attest_package') as package:
            with self.assertRaisesRegex(RuntimeError,'pywin32312'):candidate.preflight(path)
            package.assert_not_called()
        for failed in ('package','contract'):
            with ExitStack() as patches:
                patches.enter_context(mock.patch.object(candidate.importlib.metadata,'version',return_value='312'))
                p=patches.enter_context(mock.patch.object(candidate.step_null_binding,'attest_package',return_value={'verified':True}))
                c=patches.enter_context(mock.patch.object(candidate.step_explicit_null_binding,'installed_contract',return_value=contract()))
                (p if failed=='package' else c).side_effect=RuntimeError('unverified '+failed)
                with self.subTest(failed=failed),self.assertRaisesRegex(RuntimeError,'unverified'):candidate.preflight(path)
                if failed=='package':c.assert_not_called()

    def test_new_mode_is_exclusive_and_public_report_required_before_worker(self):
        reader=load()
        with mock.patch.object(reader,'worker') as worker:
            with self.assertRaisesRegex(RuntimeError,'requires --export-report'):
                reader.main(['--output-dir','unused','--swconst','unused','--null-sketch-readback-candidate','--worker'])
            with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                reader.main(['--output-dir','unused','--swconst','unused','--export-report','unused','--null-sketch-readback-candidate','--sketch-readback-candidate'])
            worker.assert_not_called()

    def test_supervisor_forwards_new_mode_once_only_and_keeps_deadline(self):
        reader=load();process=mock.Mock();process.poll.return_value=None
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);lib=root/'swconst.tlb';lib.write_bytes(b'fake')
            with mock.patch.object(reader.subprocess,'Popen',return_value=process) as start,mock.patch.object(reader.time,'monotonic',side_effect=[0,1800]),mock.patch.object(reader.time,'sleep'):
                code=reader.main(['--output-dir',str(root/'out'),'--swconst',str(lib),'--export-report',str(root/'source.json'),'--null-sketch-readback-candidate'])
            self.assertEqual(code,124);args=start.call_args.args[0]
            self.assertEqual(args.count('--null-sketch-readback-candidate'),1);self.assertNotIn('--sketch-readback-candidate',args)
            process.kill.assert_called_once();process.wait.assert_called_once()

    def test_worker_preflights_new_mode_before_host_and_requires_current_eight(self):
        import swcli.hosts.windows as windows
        import swcli.hosts.windows_step_export as step
        from gate_support.step_sketch_readback_candidate import EXPECTED_OUTPUTS
        reader=load();head='a'*40
        report=dict(source_commit=head,success=True,cleanup_errors=[],outputs=[dict(protocol=p,geometry=g,surface=s,path=str(i),sha256='b'*64) for i,(p,g,s) in enumerate(EXPECTED_OUTPUTS)])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'writer.json';source.write_text(json.dumps(report))
            args=SimpleNamespace(output_dir=root,swconst=root/'swconst.tlb',export_report=source,null_sketch_readback_candidate=True,sketch_readback_candidate=False)
            def run(*values,**options):
                self.assertEqual(options['diagnostic_case'],'step-public-explicit-null-sketch-readback-candidate')
                self.assertEqual(len(options['case_plan']),8)
                # The harness must run constants/preflight before any acquire call.
                reader.harness.read_constants(SimpleNamespace(),args.swconst)
                return 0
            with mock.patch.object(windows,'_com_value',windows._com_value),mock.patch.object(step,'_native_windows_runtime',return_value=True),mock.patch.dict('os.environ',{'GITHUB_SHA':head}),mock.patch.object(reader,'read_step_constants',return_value={}),mock.patch.object(reader,'read_import_constants',return_value={}),mock.patch.object(reader,'read_interface_contract',return_value={}),mock.patch.object(candidate,'preflight',return_value={'binding_package':{'verified':True},'installed_invocation_contract':contract()}) as preflight,mock.patch.object(reader.harness,'run',side_effect=run),mock.patch.object(reader.harness,'acquire_resident_app') as acquire:
                self.assertEqual(reader.worker(args),0);preflight.assert_called_once_with(args.swconst)
                acquire.assert_not_called();self.assertTrue((root/'null-sketch-preflight.json').is_file())
            report['source_commit']='c'*40;source.write_text(json.dumps(report))
            with mock.patch.object(windows,'_com_value',windows._com_value),mock.patch.object(step,'_native_windows_runtime',return_value=True),mock.patch.dict('os.environ',{'GITHUB_SHA':head}),mock.patch.object(reader.harness,'run') as run_mock:
                with self.assertRaisesRegex(RuntimeError,'fresh same-head'):reader.worker(args)
                run_mock.assert_not_called()

    def test_ci_selects_new_mode_once_only_in_existing_public_readback(self):
        text=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertEqual(text.count('--null-sketch-readback-candidate'),1)
        self.assertNotIn('--sketch-readback-candidate',text)
        block=text.split('      - name: Read back actual public STEP geometry and native save reopen\n',1)[1].split('      - name:',1)[0]
        self.assertIn('--null-sketch-readback-candidate',block)
        self.assertIn('inputs.native_step_public_targeted',block)


if __name__=='__main__':unittest.main()
