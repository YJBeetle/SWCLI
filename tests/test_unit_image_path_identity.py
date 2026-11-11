"""Strict OS path expansion and stat identity; no alternate image admission."""
import base64
from contextlib import ExitStack
import ctypes
from datetime import datetime,timezone
import importlib.util
import json
import ntpath
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_strict_units_image_path',ROOT/'scripts/ci/gate_support/unit_owned_native.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
SHORT=r'C:\PROGRA~1\SOLIDW~1\SLDWORKS.exe'
LONG=native.EXPECTED_CI_IMAGE


class ImagePathIdentityTests(unittest.TestCase):
    def setUp(self):
        self.handle=SimpleNamespace(Close=mock.Mock())
        self.identity=dict(pid=123,image=SHORT,creation_timestamp=200.0,creation_utc='stable-creation')
        self.api=SimpleNamespace(OpenProcess=mock.Mock(return_value=self.handle),TerminateProcess=mock.Mock())
        self.constants=SimpleNamespace(SYNCHRONIZE=0x100000,PROCESS_TERMINATE=1)
        self.expanded=LONG;self.returned=None;self.bad_nul=False
        def expand(image,buffer,capacity):
            buffer.value=self.expanded
            returned=len(self.expanded.encode('utf-16-le'))//2 if self.returned is None else self.returned
            if self.bad_nul:buffer[returned]='X'
            return returned
        self.expand=mock.Mock(side_effect=expand)
        self.kernel=SimpleNamespace(GetLongPathNameW=self.expand)
        self.stats={SHORT:SimpleNamespace(st_dev=5,st_ino=17),LONG:SimpleNamespace(st_dev=5,st_ino=17)}
        self.stat=mock.Mock(side_effect=lambda path:self.stats[path])
        self.samefile=mock.Mock(return_value=True)
        self.observations=[]

    def invoke(self,*,observe=None):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict('sys.modules',win32api=self.api,win32con=self.constants))
            stack.enter_context(mock.patch.object(native,'process_identity',return_value=self.identity))
            stack.enter_context(mock.patch.object(ctypes,'WinDLL',return_value=self.kernel,create=True))
            stack.enter_context(mock.patch.object(ctypes,'get_last_error',return_value=5,create=True))
            stack.enter_context(mock.patch.object(ctypes,'WinError',side_effect=lambda code:OSError(code,'Windows path API failed'),create=True))
            stack.enter_context(mock.patch.object(native.os,'stat',self.stat))
            stack.enter_context(mock.patch.object(native.os.path,'samefile',self.samefile))
            return native.capture(123,100.0,observe=observe or self.observations.append)

    def assert_rejected(self,exception=RuntimeError,match=None):
        context=self.assertRaisesRegex(exception,match) if match else self.assertRaises(exception)
        with context as caught:self.invoke()
        self.handle.Close.assert_called_once();self.api.TerminateProcess.assert_not_called();self.api.OpenProcess.assert_called_once()
        self.assertEqual(len(self.observations),1);self.assertNotIn('handle',self.observations[0]);json.dumps(self.observations[0])
        return caught.exception

    def test_proven_short_image_retains_raw_four_fields_and_same_process_handle(self):
        handle,identity=self.invoke()
        self.assertIs(handle,self.handle);self.assertIs(identity,self.identity);self.assertEqual(set(identity),{'pid','image','creation_timestamp','creation_utc'});self.assertEqual(identity['image'],SHORT)
        self.handle.Close.assert_not_called();self.expand.assert_called_once();self.samefile.assert_called_once_with(SHORT,LONG)
        value=self.observations[0];self.assertEqual(value['admission_identity'],{**identity,'image':LONG});self.assertIn('raw Query',value['identity_image_representation'])
        path=value['image_path_identity'];self.assertTrue(path['expanded_matches_expected']);self.assertTrue(path['recorded_file_ids_match']);self.assertTrue(path['file_ids_available']);self.assertEqual(path['raw_stat'],dict(device=5,inode=17))
        q=path['expansion'];self.assertEqual(q['api'],'GetLongPathNameW');self.assertEqual(q['returned_chars'],len(LONG));self.assertTrue(q['nul_at_returned_index'])
        codec='utf-16-le' if ctypes.sizeof(ctypes.c_wchar)==2 else 'utf-32-le'
        self.assertEqual(base64.b64decode(q['buffer_prefix_b64']),LONG.encode(codec)+b'\0'*ctypes.sizeof(ctypes.c_wchar))

    def test_full_long_image_still_requires_expansion_and_samefile(self):
        self.identity['image']=LONG;self.invoke();self.expand.assert_called_once();self.samefile.assert_called_once_with(LONG,LONG)

    def test_expansion_and_file_ids_are_json_fsynced_before_all_admission_predicates(self):
        saved=[];original=native.validate_identity
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'raw.json'
            def observe(value):
                with path.open('w') as stream:json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
                saved.append(json.loads(path.read_bytes()))
            def validate(*args):
                self.assertEqual(saved[0]['image_path_identity']['expansion']['expanded_image'],LONG)
                self.assertTrue(saved[0]['image_path_identity']['samefile']);self.assertEqual(saved[0]['image_path_identity']['expected_stat'],dict(device=5,inode=17))
                return original(*args)
            with mock.patch.object(native,'validate_identity',side_effect=validate):self.invoke(observe=observe)

    def test_api_success_returning_raw_short_name_is_not_sufficient(self):
        self.expanded=SHORT;self.assert_rejected(match='full image differs');self.expand.assert_called_once()

    def test_wrong_directory_and_wrong_executable_never_admit_even_if_file_ids_match(self):
        for expanded in (r'C:\Other\SLDWORKS.exe',r'C:\Program Files\SOLIDWORKS\Other.exe'):
            with self.subTest(expanded=expanded):
                self.setUp();self.expanded=expanded;self.assert_rejected(match='full image differs')

    def test_same_long_path_cannot_admit_different_file_or_volume(self):
        for change in (dict(st_dev=5,st_ino=18),dict(st_dev=6,st_ino=17)):
            with self.subTest(change=change):
                self.setUp();self.stats[LONG]=SimpleNamespace(**change);self.samefile.return_value=False
                self.assert_rejected(match='do not prove the same installed file')

    def test_samefile_result_and_recorded_ids_must_both_prove_identity(self):
        for samefile,ino in ((False,17),(True,18),(True,0)):
            with self.subTest(samefile=samefile,ino=ino):
                self.setUp();self.samefile.return_value=samefile;self.stats[LONG]=SimpleNamespace(st_dev=5,st_ino=ino)
                self.assert_rejected(match='do not prove the same installed file')

    def test_missing_or_denied_stat_and_samefile_exceptions_are_persisted_then_closed(self):
        for target,error in (('stat',FileNotFoundError(2,'missing installed image')),('stat',PermissionError(13,'stat denied')),('samefile',PermissionError(13,'samefile denied')),('samefile',OSError(5,'samefile IO error'))):
            with self.subTest(target=target,error=error):
                self.setUp();getattr(self,target).side_effect=error;caught=self.assert_rejected(type(error))
                self.assertIs(caught,error);self.assertEqual(self.observations[0]['image_path_identity']['error']['type'],type(error).__name__)

    def test_expansion_api_failure_records_raw_result_and_never_stats_or_retries(self):
        self.returned=0;error=self.assert_rejected(OSError)
        self.expand.assert_called_once();self.stat.assert_not_called();self.samefile.assert_not_called()
        evidence=error.identity_observation['image_path_identity'];self.assertEqual(evidence['expansion']['last_error'],5);self.assertEqual(evidence['expansion']['returned_chars'],0);self.assertEqual(evidence['error']['type'],'OSError')

    def test_expansion_exception_is_persisted_before_failed_candidate_is_closed(self):
        error=OSError('expansion invocation failed');self.expand.side_effect=error
        self.assertIs(self.assert_rejected(OSError),error);self.stat.assert_not_called();self.expand.assert_called_once()

    def test_required_large_buffer_and_bad_length_or_nul_fail_without_resize(self):
        for returned,bad_nul in ((32768,False),(40000,False),(len(LONG)-1,False),(None,True)):
            with self.subTest(returned=returned,bad_nul=bad_nul):
                self.setUp();self.returned=returned;self.bad_nul=bad_nul;self.assert_rejected()
                self.expand.assert_called_once();self.stat.assert_not_called();q=self.observations[0]['image_path_identity']['expansion']
                self.assertLessEqual(len(base64.b64decode(q['buffer_prefix_b64'])),32768*ctypes.sizeof(ctypes.c_wchar))

    def test_valid_expansion_longer_than_260_chars_is_fully_recorded(self):
        self.expanded='C:\\'+('directory\\'*35)+'SLDWORKS.exe'
        self.assert_rejected(match='full image differs');q=self.observations[0]['image_path_identity']['expansion']
        self.assertGreater(q['returned_chars'],260);self.assertEqual(q['expanded_image'],self.expanded)

    def test_short_file_proof_cannot_bypass_pid_or_creation_window(self):
        for change in (dict(pid=999),dict(creation_timestamp=99.0),dict(creation_timestamp=float('inf'))):
            with self.subTest(change=change):
                self.setUp();self.identity.update(change);self.assert_rejected(match='PID differs|creation time')

    def test_persistence_failure_never_runs_validation_or_exposes_retained_handle(self):
        error=OSError('path identity fsync denied')
        with mock.patch.object(native,'validate_identity') as validate:
            with self.assertRaisesRegex(OSError,'path identity fsync denied'):self.invoke(observe=mock.Mock(side_effect=error))
        validate.assert_not_called();self.handle.Close.assert_called_once();self.api.TerminateProcess.assert_not_called()

    def test_observer_cannot_forge_expanded_path_or_samefile_to_admit_wrong_file(self):
        self.expanded=r'C:\Wrong\SLDWORKS.exe';self.samefile.return_value=False
        def observer(value):
            value['admission_identity']['image']=LONG;value['image_path_identity']['samefile']=True
        with self.assertRaisesRegex(RuntimeError,'full image differs'):self.invoke(observe=observer)
        self.handle.Close.assert_called_once();self.assertEqual(self.identity['image'],SHORT)

    def test_observer_cannot_forge_samefile_when_expanded_path_already_matches(self):
        self.samefile.return_value=False
        def observer(value):value['image_path_identity']['samefile']=True
        with self.assertRaisesRegex(RuntimeError,'do not prove the same installed file'):self.invoke(observe=observer)
        self.handle.Close.assert_called_once();self.api.TerminateProcess.assert_not_called()

    def test_termination_still_rechecks_raw_identity_on_same_held_handle(self):
        handle,identity=self.invoke();self.api.OpenProcess.reset_mock()
        with mock.patch.dict('sys.modules',win32api=self.api),mock.patch.object(native,'process_identity',return_value=dict(identity)):
            native.terminate(handle,identity)
        self.api.TerminateProcess.assert_called_once_with(handle,1);self.api.OpenProcess.assert_not_called();self.assertEqual(self.expand.call_count,1)
        self.api.TerminateProcess.reset_mock()
        with mock.patch.dict('sys.modules',win32api=self.api),mock.patch.object(native,'process_identity',return_value={**identity,'image':LONG}):
            with self.assertRaisesRegex(RuntimeError,'identity changed'):native.terminate(handle,identity)
        self.api.TerminateProcess.assert_not_called()


@unittest.skipUnless(sys.platform=='win32','read-only actual Windows short/long file identity APIs')
class WindowsActualImagePathTests(unittest.TestCase):
    def test_real_windows_short_and_long_file_paths_have_same_os_identity(self):
        from ctypes import wintypes
        observation={};probe={}
        with tempfile.TemporaryDirectory(prefix='units image path ') as directory:
            expected=Path(directory)/'Owned native image fixture.exe';expected.write_bytes(b'identity fixture')
            expected=str(expected.resolve());kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            short=kernel.GetShortPathNameW;short.argtypes=[wintypes.LPCWSTR,wintypes.LPWSTR,wintypes.DWORD];short.restype=wintypes.DWORD
            buffer=ctypes.create_unicode_buffer(32768);length=short(expected,buffer,len(buffer));probe.update(expected=expected,short_returned_chars=length,short_image=buffer.value)
            try:
                self.assertTrue(0<length<len(buffer))
                if ntpath.normcase(buffer.value)==ntpath.normcase(expected):self.skipTest('volume did not provide a distinct short representation')
                expanded=native.image_path_identity(buffer.value,expected,observation=observation);probe['expanded']=expanded
                native.validate_identity(dict(pid=1,image=expanded,creation_timestamp=2),1,1,3,expected)
                self.assertTrue(observation['samefile']);self.assertTrue(observation['recorded_file_ids_match']);self.assertTrue(observation['file_ids_available'])
                self.assertEqual(observation['expansion']['ctypes_bytes'],dict(DWORD=4,wchar=2));self.assertTrue(observation['expansion']['nul_at_returned_index'])
            finally:print('units.short-long-file-identity-observation '+json.dumps(dict(**probe,evidence=observation),ensure_ascii=True))

    def test_real_windows_different_and_missing_files_cannot_supply_same_file_proof(self):
        with tempfile.TemporaryDirectory(prefix='units identity negative ') as directory:
            a=Path(directory)/'first image.exe';b=Path(directory)/'second image.exe';a.write_bytes(b'a');b.write_bytes(b'b')
            observation={};native.image_path_identity(str(a),str(b),observation=observation)
            self.assertFalse(observation['samefile']);self.assertFalse(observation['recorded_file_ids_match'])
            with self.assertRaises(OSError):native.image_path_identity(str(a.parent/'missing image.exe'),str(b),observation={})

if __name__=='__main__':unittest.main()
