"""A callable root-owned-STA gate; never opens or activates CAD."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('active_census_gate',ROOT/'scripts/diagnostics/observe-active-assembly-target-census.py')
gate=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(gate)


class ActiveTargetGateTests(unittest.TestCase):
    def test_single_census_same_app_and_success_only_postflight(self):
        for fail in (False,True):
            with self.subTest(fail=fail):
                app=NS(CommandInProgress=False);document=object()
                options=NS(fixture_dir=Path('/no-files-opened'),expected_pid=42)
                report=dict(request_id='offline-only');first=ValueError('original owner failure')
                def read(**kwargs):
                    self.assertIs(kwargs['app'],app);self.assertIs(kwargs['document'],document)
                    self.assertEqual(kwargs['components'],gate.NAMES)
                    if fail:raise first
                    return NS(value=dict(face_count=6,all_faces_observed=True))
                with mock.patch.object(gate,'verify_candidate') as source, \
                     mock.patch.object(gate,'verify_files',return_value={'fixed':'sha'}) as files, \
                     mock.patch.object(gate,'preflight',return_value=document) as prepared, \
                     mock.patch.object(gate,'observe_readonly_active_targets',side_effect=read) as observe:
                    if fail:
                        with self.assertRaises(ValueError) as caught:gate.run(app,options,report)
                        self.assertIs(caught.exception,first)
                    else:gate.run(app,options,report)
                source.assert_called_once_with(options);observe.assert_called_once();self.assertEqual(files.call_count,2)
                self.assertEqual(prepared.call_count,1 if fail else 2);self.assertFalse(app.CommandInProgress)
                self.assertEqual(report['success'],not fail);self.assertTrue(report['files_unchanged'])
                self.assertFalse(report['public_acceptance']);self.assertFalse(report['handles_issued']);self.assertFalse(report['write_CAS_executed'])
                if fail:self.assertEqual(report['first_business_error']['message'],'original owner failure')

    def test_background_preflight_stops_before_request_state_setter_or_reader(self):
        class App:
            @property
            def CommandInProgress(self):return False
            @CommandInProgress.setter
            def CommandInProgress(self,value):raise AssertionError('no request-state setter for rejected background')
        with mock.patch.object(gate,'verify_candidate'),mock.patch.object(gate,'verify_files',return_value={}), \
             mock.patch.object(gate,'preflight',side_effect=RuntimeError('AssemblyNotActive')), \
             mock.patch.object(gate,'observe_readonly_active_targets') as read:
            with self.assertRaisesRegex(RuntimeError,'AssemblyNotActive'):gate.run(App(),NS(fixture_dir=Path('/none'),expected_pid=42),dict(request_id='offline'))
        read.assert_not_called()

    def test_filesystem_secondary_failure_never_replaces_first_owner_error(self):
        report=dict(request_id='offline');first=ValueError('first native failure')
        with mock.patch.object(gate,'verify_candidate'),mock.patch.object(gate,'verify_files',side_effect=[{},OSError('secondary file audit')]), \
             mock.patch.object(gate,'preflight',return_value=object()), \
             mock.patch.object(gate,'observe_readonly_active_targets',side_effect=first):
            with self.assertRaises(ValueError) as caught:gate.run(NS(CommandInProgress=False),NS(fixture_dir=Path('/none'),expected_pid=42),report)
        self.assertIs(caught.exception,first);self.assertFalse(report['success'])
        self.assertEqual(report['filesystem_audit_error']['message'],'secondary file audit')

    def test_fixed_files_require_exact_bytes_filesystem_readonly_and_no_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);files={}
            for name in gate.FILES:
                path=folder/name;path.write_bytes(name.encode());path.chmod(0o444);files[name]=gate.digest(path)
            with mock.patch.dict(gate.FILES,files,clear=True):
                self.assertEqual(set(gate.verify_files(folder)),set(files))
                path=folder/'coincident-aligned.SLDASM';path.chmod(0o644)
                with self.assertRaisesRegex(RuntimeError,'filesystem readonly'):gate.verify_files(folder)
                path.write_bytes(b'changed');path.chmod(0o444)
                with self.assertRaisesRegex(RuntimeError,'bytes differ'):gate.verify_files(folder)
                path.unlink();path.symlink_to(folder/'coincident-aligned-component.SLDPRT')
                with self.assertRaisesRegex(RuntimeError,'link refused'):gate.verify_files(folder)

    def test_preflight_exact_catalog_active_asm_and_isolated_source_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);documents=[]
            for name in gate.FILES:
                documents.append(NS(GetType=2 if name.endswith('.SLDASM') else 1,GetPathName=str((folder/name).resolve()),
                    GetSaveFlag=False,IsOpenedReadOnly=True,IsOpenedViewOnly=False))
            target=documents[0];source_path=documents[1].GetPathName
            target.GetComponents=lambda top:(NS(GetPathName=source_path),NS(GetPathName=source_path))
            app=NS(GetProcessID=42,RevisionNumber='33.5.0',GetDocumentCount=3,GetDocuments=lambda:tuple(documents),ActiveDoc=target,IsSame=lambda a,b:int(a is b))
            self.assertIs(gate.preflight(app,42,folder),target)
            app.ActiveDoc=documents[2]
            with self.assertRaisesRegex(RuntimeError,'already be active'):gate.preflight(app,42,folder)
            app.ActiveDoc=target;target.GetComponents=lambda top:(NS(GetPathName='foreign'),NS(GetPathName=source_path))
            with self.assertRaisesRegex(RuntimeError,'source outside'):gate.preflight(app,42,folder)
            app.GetDocuments=mock.Mock(side_effect=AssertionError('wrong PID must not inspect documents'))
            with self.assertRaisesRegex(RuntimeError,'PID differs'):gate.preflight(app,43,folder)
            app.GetDocuments.assert_not_called()

    def test_complete_gitless_source_and_binary_pins_checked_without_com(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);sources={}
            for name in ('src/a.py','scripts/b.py','tests/c.py'):
                path=folder/name;path.parent.mkdir();path.write_bytes(name.encode());sources[name]=gate.digest(path)
            options=NS(source_manifest=folder/'source.json',host_executable=folder/'SLDWORKS.exe',host_type_library=folder/'sldworks.tlb',
                       internal_zip=folder/'internal.zip',public_zip=folder/'public.zip')
            pins={}
            for field in ('internal_zip','public_zip','host_executable','host_type_library'):
                path=getattr(options,field);path.write_bytes(field.encode());pins[field]=gate.digest(path)
            python_exe=folder/'python.exe';python_exe.write_bytes(b'python')
            manifest=dict(source_files=sources,fixtures=gate.FILES,mode='active-assembly-complete-census-readonly-v1',pins=pins)
            options.source_manifest.write_text(json.dumps(manifest));options.source_manifest_sha=gate.digest(options.source_manifest)
            with mock.patch.object(gate,'ROOT',folder),mock.patch.object(gate.sys,'version_info',(3,14,7)), \
                 mock.patch.object(gate.sys,'executable',str(python_exe)),mock.patch.object(gate,'PYTHON_SHA',gate.digest(python_exe)), \
                 mock.patch.object(gate.importlib.metadata,'version',side_effect=lambda name:{'pywin32':'312','jsonschema':'4.26.0'}[name]) as versions:
                self.assertEqual(gate.verify_candidate(options),manifest)
                versions.reset_mock();(folder/'src/a.py').write_bytes(b'changed')
                with self.assertRaisesRegex(RuntimeError,'source bytes differ'):gate.verify_candidate(options)
                versions.assert_not_called()
                (folder/'src/extra.py').write_bytes(b'extra')
                with self.assertRaisesRegex(RuntimeError,'inventory differs'):gate.verify_candidate(options)
