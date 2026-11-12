"""Portable traps for one preselected NeutralFree difference, never a parameter grid."""
from contextlib import redirect_stderr
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
from gate_support import step_null_sketch_readback_candidate as null_mode
from gate_support import step_sketch_readback_candidate as sketch_mode
import test_step_sketch_readback_candidate as fixtures
from test_step_wire_import_once import Failure
from test_step_explicit_null_binding import contract

NEUTRAL='swImportNeutral_FreeCurvesAndPoints'


class NeutralFreeCandidateTests(unittest.TestCase):
    run_roundtrip=fixtures.SketchRoundtripTests.run_roundtrip

    def test_only_neutral_free_changes_with_same_null_call_and_strict_three_geometry_roundtrip(self):
        for kind in ('solid-surface','wireframe','wireframe-sketches'):
            with self.subTest(kind=kind):
                case,exc,reads,app,live=self.run_roundtrip(null_candidate=True,neutral_free_candidate=True,kind=kind)
                self.assertIsNone(exc);self.assertTrue(case['success']);self.assertIsNone(live['document'])
                p=case['sketch_observer_preferences'];expected={**null_mode.PUBLIC_PROFILE,NEUTRAL:True}
                self.assertEqual(p['requested'],expected);self.assertEqual(p['changed_from_e039'],[NEUTRAL])
                self.assertEqual([k for k in expected if expected[k]!=p['e039_baseline'][k]],[NEUTRAL])
                self.assertEqual(p['requested']['swImportCurvePreference'],0);self.assertEqual(p['requested']['swImportNeutral_CurvesAndPointsOption'],0)
                self.assertEqual(p['writes'][-1]['name'],NEUTRAL);self.assertEqual(p['restore'][0]['name'],NEUTRAL)
                self.assertFalse(app.values[NEUTRAL]);self.assertTrue(p['restored'])
                raw=app.binding_raw;self.assertEqual([x[0] for x in raw._oleobj_.calls],['Invoke']);self.assertEqual(raw.lookups,0)
                args=raw._oleobj_.calls[0][1];self.assertEqual(args[:4],(227,0,1,1));self.assertEqual(args[5],'r')
                self.assertEqual((args[6].varianttype,args[6].value),(9,None));self.assertEqual(args[7].varianttype,16387)
                e=case['null_sketch_import'];self.assertEqual(e['changed_variables'],[NEUTRAL]);self.assertTrue(e['same_invocation_route_as_e039'])
                self.assertEqual(e['comparison_head'],'e039ae596d20d870752c6de7b02c8e1b283d5d62')
                self.assertEqual(reads,0 if kind=='solid-surface' else 2)

    def test_repeated_none_errors1_stays_failure_with_one_call_and_no_fallback(self):
        c,exc,reads,app,live=self.run_roundtrip(null_candidate=True,neutral_free_candidate=True,load_error=1,null_document=True)
        self.assertEqual(str(exc),'STEP geometry readback failed');self.assertFalse(c.get('success',False));self.assertEqual(reads,0)
        self.assertEqual(len(app.binding_raw._oleobj_.calls),1);self.assertNotIn('imported_geometry',c);self.assertNotIn('imported_save',c)
        self.assertTrue(c['sketch_observer_preferences']['restored']);self.assertFalse(app.values[NEUTRAL])

    def test_neutral_partial_setter_error_restores_only_attempted_value_and_never_retries(self):
        app,constants=fixtures.pref_fixture();app.partial_set=NEUTRAL;case={}
        with self.assertRaisesRegex(Failure,'first partial setter error'):
            with sketch_mode.preferences(app,constants,fixtures.call,case,lambda:None,neutral_free_candidate=True):self.fail('native must not start')
        self.assertEqual(app.values,app.before);self.assertTrue(case['sketch_observer_preferences']['restored'])
        self.assertEqual([v for k,v in app.writes if k==NEUTRAL],[True,False]);self.assertEqual(app.loads,[])

    def test_neutral_restore_failure_preserves_first_native_failure_and_cannot_stay_green(self):
        for fail_native in (False,True):
            with self.subTest(native_failure=fail_native):
                c,exc,reads,app,live=self.run_roundtrip(null_candidate=True,neutral_free_candidate=True,restore_fail=NEUTRAL,
                    load_error=1 if fail_native else 0,null_document=fail_native)
                self.assertIsNotNone(exc);self.assertFalse(c.get('success',False));self.assertTrue(c['sketch_observer_preferences']['restore_errors'])
                self.assertEqual(str(exc),'STEP geometry readback failed' if fail_native else 'Sketch observer preferences could not be restored')
                self.assertEqual(len(app.binding_raw._oleobj_.calls),1)

    def test_other_profile_drift_rejects_before_any_preference_write(self):
        app,constants=fixtures.pref_fixture();app.values['swImportNeutral_CurvesAndPointsOption']=1;case={}
        with self.assertRaisesRegex(RuntimeError,'other eight-value drift'):
            with sketch_mode.preferences(app,constants,fixtures.call,case,lambda:None,neutral_free_candidate=True):self.fail('native must not start')
        self.assertEqual(app.writes,[]);self.assertEqual(app.loads,[])

    def test_unknown_neutral_value_on_cleanup_is_not_overwritten_as_false(self):
        app,constants=fixtures.pref_fixture();case={}
        with self.assertRaisesRegex(RuntimeError,'unknown preference'):
            with sketch_mode.preferences(app,constants,fixtures.call,case,lambda:None,neutral_free_candidate=True) as verify:
                app.values[NEUTRAL]=None;verify()
        self.assertIsNone(app.values[NEUTRAL]);self.assertEqual([v for k,v in app.writes if k==NEUTRAL],[True])
        self.assertFalse(case['sketch_observer_preferences']['restored'])

    def test_neutral_true_does_not_relax_health_or_reopened_vector_and_hash(self):
        for options in ({'initial_health':1},{'reopened_health':1},{'reopened_lengths':[10]*4+[30]*4+[41]*4},{'mutate_native':True},{'mutate_step':True}):
            with self.subTest(options=options):
                c,exc,reads,app,live=self.run_roundtrip(null_candidate=True,neutral_free_candidate=True,**options)
                self.assertIsNotNone(exc);self.assertFalse(c.get('success',False));self.assertEqual(len(app.binding_raw._oleobj_.calls),1)
                self.assertTrue(c['sketch_observer_preferences']['restored'])

    def test_mode_is_mutually_exclusive_and_supervisor_forwards_only_new_mode(self):
        reader=fixtures.load()
        with mock.patch.object(reader,'worker') as worker,self.assertRaisesRegex(RuntimeError,'requires --export-report'):
            reader.main(['--output-dir','unused','--swconst','unused','--neutral-free-null-sketch-candidate','--worker'])
        worker.assert_not_called()
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            reader.main(['--output-dir','unused','--swconst','unused','--export-report','unused','--neutral-free-null-sketch-candidate','--null-sketch-readback-candidate'])
        process=mock.Mock();process.poll.return_value=None
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);lib=root/'swconst.tlb';lib.write_bytes(b'fake')
            with mock.patch.object(reader.subprocess,'Popen',return_value=process) as start,mock.patch.object(reader.time,'monotonic',side_effect=[0,1800]),mock.patch.object(reader.time,'sleep'):
                self.assertEqual(reader.main(['--output-dir',str(root/'out'),'--swconst',str(lib),'--export-report',str(root/'writer.json'),'--neutral-free-null-sketch-candidate']),124)
            args=start.call_args.args[0];self.assertEqual(args.count('--neutral-free-null-sketch-candidate'),1)
            self.assertNotIn('--null-sketch-readback-candidate',args);self.assertNotIn('--sketch-readback-candidate',args)
            process.kill.assert_called_once();process.wait.assert_called_once()

    def test_worker_selects_same_eight_with_explicit_prehost_candidate_and_one_ci_argument(self):
        import swcli.hosts.windows as windows
        import swcli.hosts.windows_step_export as step
        reader=fixtures.load();head='a'*40
        report=dict(source_commit=head,success=True,cleanup_errors=[],outputs=[dict(protocol=p,geometry=g,surface=s,path=str(i),sha256='b'*64) for i,(p,g,s) in enumerate(sketch_mode.EXPECTED_OUTPUTS)])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'writer.json';source.write_text(json.dumps(report))
            args=SimpleNamespace(output_dir=root,swconst=root/'swconst.tlb',export_report=source,neutral_free_null_sketch_candidate=True,null_sketch_readback_candidate=False,sketch_readback_candidate=False)
            def run(*values,**options):
                self.assertEqual(options['diagnostic_case'],'step-public-neutral-free-null-sketch-candidate');self.assertEqual(len(options['case_plan']),8)
                reader.harness.read_constants(SimpleNamespace(),args.swconst)
                options['case_runner'](None,None,None,None,None,None,None,None,None,profile_kind='0')
                return 0
            with mock.patch.object(windows,'_com_value',windows._com_value),mock.patch.object(step,'_native_windows_runtime',return_value=True),mock.patch.dict('os.environ',{'GITHUB_SHA':head}),mock.patch.object(reader,'read_step_constants',return_value={}),mock.patch.object(reader,'read_import_constants',return_value={}),mock.patch.object(reader,'read_interface_contract',return_value={}),mock.patch.object(null_mode,'preflight',return_value={'binding_package':{'verified':True},'installed_invocation_contract':contract(),'neutral_free_candidate':True}) as preflight,mock.patch.object(reader.harness,'run',side_effect=run),mock.patch.object(sketch_mode,'readback_case',return_value=None) as readback,mock.patch.object(reader.harness,'acquire_resident_app') as acquire:
                self.assertEqual(reader.worker(args),0);preflight.assert_called_once_with(args.swconst,neutral_free_candidate=True)
                self.assertTrue(readback.call_args.kwargs['neutral_free_candidate']);self.assertIsNotNone(readback.call_args.kwargs['load_model']);acquire.assert_not_called()
        text=(ROOT/'.github/workflows/ci.yml').read_text();self.assertEqual(text.count('--neutral-free-null-sketch-candidate'),1)
        self.assertNotIn('--null-sketch-readback-candidate',text)


if __name__=='__main__':unittest.main()
