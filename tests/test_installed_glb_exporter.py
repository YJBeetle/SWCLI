"""Synthetic bytes and filesystem traps only; never inspect a live installation."""
import ast
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'scripts/ci/inspect-installed-glb-exporter.py'
if not SCRIPT.exists(): SCRIPT = Path(__file__).with_name('inspect-installed-glb-exporter.py')
spec = importlib.util.spec_from_file_location('installed_glb_exporter_test', SCRIPT)
gate = importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


def pe_fixture(*, bits=64, normal='KERNEL32.dll', delay='api-ms-win-core-file-l1-1-0.dll', certificate=False):
    data=bytearray(0x600);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,0x80);data[0x80:0x84]=b'PE\0\0'
    size=240 if bits==64 else 224;optional=0x98;directory=optional+(112 if bits==64 else 96)
    struct.pack_into('<HHIIIHH',data,0x84,0x8664 if bits==64 else 0x14c,1,0,0,0,size,0x2000)
    struct.pack_into('<H',data,optional,0x20b if bits==64 else 0x10b)
    struct.pack_into('<Q' if bits==64 else '<I',data,optional+(24 if bits==64 else 28),0x140000000 if bits==64 else 0x400000)
    struct.pack_into('<I',data,optional+60,0x200);struct.pack_into('<I',data,optional+(108 if bits==64 else 92),16)
    section=optional+size;data[section:section+8]=b'.rdata\0\0';struct.pack_into('<IIII',data,section+8,0x400,0x1000,0x400,0x200)
    if normal is not None:
        struct.pack_into('<II',data,directory+8,0x1000,0x100)
        struct.pack_into('<IIIII',data,0x200,1,0,0,0x1100,0)
        encoded=normal.encode('ascii')+b'\0';data[0x300:0x300+len(encoded)]=encoded
    if delay is not None:
        struct.pack_into('<II',data,directory+13*8,0x1040,64)
        struct.pack_into('<IIIIIIII',data,0x240,1,0x1140,0,0,0,0,0,0)
        encoded=delay.encode('ascii')+b'\0';data[0x340:0x340+len(encoded)]=encoded
    if certificate:
        payload=b'fixture CMS bytes';length=8+len(payload);padded=(length+7)&~7
        struct.pack_into('<II',data,directory+4*8,0x600,padded)
        data+=struct.pack('<IHH',length,0x200,2)+payload+b'\0'*(padded-length)
    return bytes(data)


class PEParserTests(unittest.TestCase):
    def test_PE32_PE32plus_normal_and_delay_names_and_raw_certificate(self):
        for bits in (32,64):
            with self.subTest(bits=bits):
                pe=gate.PE(pe_fixture(bits=bits,certificate=True))
                self.assertEqual(pe.machine,0x14c if bits==32 else 0x8664)
                self.assertEqual([(r['kind'],r['name']) for r in pe.imports()], [('normal','KERNEL32.dll'),('delay','api-ms-win-core-file-l1-1-0.dll')])
                self.assertTrue(pe.imports()[1]['api_set_contract'])
                cert=pe.certificates()[0]
                self.assertEqual(base64.b64decode(cert['pkcs7_base64']),b'fixture CMS bytes')
                self.assertEqual(cert['sha256'],hashlib.sha256(b'fixture CMS bytes').hexdigest())

    def test_empty_directories_are_observed_empty_without_synthesizing_signature(self):
        pe=gate.PE(pe_fixture(normal=None,delay=None))
        self.assertEqual(pe.imports(),[]);self.assertEqual(pe.certificates(),[])

    def test_unsafe_library_names_are_rejected_before_path_lookup(self):
        for name in ('../evil.dll','..\\evil.dll','C:evil.dll','evil.dll:stream','.evil.dll','file..dll'):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):gate.PE(pe_fixture(normal=name)).imports()
                with self.assertRaises(RuntimeError):gate.dependency_locations(Path('/fixed/a.dll'),name)

    def test_truncated_unmapped_unterminated_or_ambiguous_images_refuse(self):
        for kind in ('DOS','offset','machine-header','directory','unterminated','RVA','ambiguous'):
            with self.subTest(kind=kind):
                data=bytearray(pe_fixture())
                if kind=='DOS':data[:2]=b'xx'
                elif kind=='offset':struct.pack_into('<I',data,0x3c,0xffffffff)
                elif kind=='machine-header':data=data[:0x90]
                elif kind=='directory':struct.pack_into('<I',data,0x98+108,17)
                elif kind=='unterminated':struct.pack_into('<II',data,0x98+112+8,0x1000,20)
                elif kind=='RVA':struct.pack_into('<I',data,0x200+12,0x1800)
                elif kind=='ambiguous':
                    struct.pack_into('<H',data,0x84+2,2);second=0x98+240+40;struct.pack_into('<IIII',data,second+8,0x400,0x1000,0x400,0x200)
                with self.assertRaises(RuntimeError):gate.PE(bytes(data)).imports()

    def test_delay_VA32_encoding_and_import_count_bound(self):
        data=bytearray(pe_fixture(bits=32));struct.pack_into('<II',data,0x240,0,0x401140)
        self.assertEqual(gate.PE(bytes(data)).imports()[1]['name'],'api-ms-win-core-file-l1-1-0.dll')
        with mock.patch.object(gate,'MAX_IMPORTS',1):
            with self.assertRaisesRegex(RuntimeError,'count exceeds bound'):gate.PE(pe_fixture()).imports()

    def test_security_directory_is_file_offset_and_rejects_overlap_or_bad_length(self):
        for kind in ('RVA-not-file-offset','overlap','short','misaligned'):
            with self.subTest(kind=kind):
                data=bytearray(pe_fixture(certificate=True));entry=0x98+112+32
                if kind=='RVA-not-file-offset':struct.pack_into('<I',data,entry,0x1600)
                elif kind=='overlap':struct.pack_into('<I',data,entry,0x200)
                elif kind=='short':struct.pack_into('<I',data,0x600,7)
                elif kind=='misaligned':struct.pack_into('<I',data,entry,0x601)
                with self.assertRaises(RuntimeError):gate.PE(bytes(data)).certificates()


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.install=self.root/'install';self.install.mkdir();self.system=(self.root/'System32',self.root/'SysWOW64')
        for p in self.system:p.mkdir()
        self.ps=self.root/'powershell.exe';self.ps.write_bytes(b'not executed')
        self.output=self.root/'output';self.output.mkdir()
        script=self.root/SCRIPT.name;script.write_bytes(SCRIPT.read_bytes())
        script.with_name('inspect-installed-glb-exporter-metadata.ps1').write_bytes(SCRIPT.with_name('inspect-installed-glb-exporter-metadata.ps1').read_bytes())
        for relative in gate.REQUIRED_FILES:
            p=self.install/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(pe_fixture(certificate=True))
        self.patches=[mock.patch.object(gate,'__file__',str(script)),mock.patch.object(gate,'INSTALL_ROOT',self.install),mock.patch.object(gate,'SYSTEM_DIRS',self.system),mock.patch.object(gate,'POWERSHELL',self.ps)]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def runner(self, command, **options):
        self.assertEqual(command[:5],[str(self.ps),'-NoLogo','-NoProfile','-NonInteractive','-File'])
        self.assertEqual(options,dict(capture_output=True,timeout=120,check=False))
        self.assertNotIn('Bypass',command);self.assertNotIn('shell',options)
        request=json.loads(Path(command[command.index('-RequestPath')+1]).read_bytes());self.request=request
        rows=[dict(relative_path=r['relative_path'],sha256_before=r['expected_sha256'],sha256_after=r['expected_sha256'],
                   version={'status':'observed','file_version':'fixture.1','product_version':'fixture.1'},
                   signature={'status':'metadata_only','cryptographic_validity':'unknown_not_verified','catalog_signature':'unknown_not_queried'}) for r in request['files']]
        reply=dict(success=True,kind='data-only-file-version-and-embedded-CMS-metadata',target_dll_loads=0,cad_activations=0,network_verification=False,signature_verified=False,files=rows)
        Path(command[command.index('-OutputPath')+1]).write_text(json.dumps(reply));return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')

    def test_fixed_files_stable_metadata_and_bounded_dependencies_no_runtime_verdict(self):
        (self.system[0]/'KERNEL32.dll').write_bytes(b'presence only')
        report={};gate.collect(self.output,report,runner=self.runner)
        self.assertTrue(report['collection_completed']);self.assertFalse(report['exporter_runtime_accepted'])
        self.assertEqual(len(report['files']),6);self.assertEqual(len(self.request['files']),4)
        for row in report['files'][:4]:
            self.assertEqual(row['before'],row['after'])
            self.assertEqual(row['presence_before'],row['presence_after'])
            self.assertEqual(row['pe']['machine_name'],'AMD64')
            self.assertEqual(row['signature_table']['cryptographic_validity'],'unknown_not_verified')
            normal,delay=row['dependency_locations']
            self.assertTrue(normal['static_path_match']);self.assertFalse(delay['static_path_match'])
            self.assertEqual(delay['runtime_resolution'],'unknown_not_executed')
            self.assertTrue(delay['not_found_is_not_runtime_missing'])
            expected=gate.dependency_locations(self.install/row['relative_path'],'KERNEL32.dll')
            self.assertEqual([r['path'] for r in normal['checked_paths']],[str(p) for p in expected])
        self.assertEqual(report['files'][-1]['presence_before']['status'],'not_present_at_checked_path')

    def test_required_absent_background_TLB_and_malformed_PE_remain_explicit(self):
        (self.install/gate.REQUIRED_FILES[0]).unlink();(self.install/'SWXRExporter.tlb').write_bytes(b'standalone metadata')
        (self.install/gate.REQUIRED_FILES[1]).write_bytes(b'not PE')
        report={};gate.collect(self.output,report,runner=self.runner)
        self.assertFalse(report['required_files_all_present'])
        self.assertEqual(report['files'][0]['presence_before']['status'],'not_present_at_checked_path')
        self.assertEqual(report['files'][1]['pe']['status'],'unknown')
        self.assertEqual(report['files'][1]['static_imports']['status'],'unknown')
        self.assertEqual(report['files'][1]['signature_table']['status'],'unknown')
        self.assertEqual(report['files'][-1]['pe']['status'],'not_applicable_standalone_tlb')

    def test_symlink_file_parent_or_reparse_attribute_is_unknown_and_never_opened(self):
        source=self.install/gate.REQUIRED_FILES[0];target=self.root/'elsewhere.dll';target.write_bytes(pe_fixture());source.unlink();source.symlink_to(target)
        self.assertEqual(gate.probe(source)['status'],'unknown')
        with self.assertRaises(RuntimeError):gate.stable_read(source)
        source.unlink();source.write_bytes(pe_fixture())
        with mock.patch.object(gate,'regular',return_value=False),mock.patch.object(gate.os,'open') as opened:
            with self.assertRaises(RuntimeError):gate.stable_read(source)
            opened.assert_not_called()
        nested=self.root/'alias';nested.symlink_to(self.install,target_is_directory=True)
        self.assertEqual(gate.probe(nested/gate.REQUIRED_FILES[0])['status'],'unknown')
        native=os.stat(source,follow_symlinks=False)
        value=SimpleNamespace(st_mode=native.st_mode,st_file_attributes=0x400)
        self.assertFalse(gate.regular(value))

    def test_stat_open_race_and_zero_identity_refuse_before_read(self):
        source=self.install/gate.REQUIRED_FILES[0];native=os.stat(source,follow_symlinks=False)
        changed=SimpleNamespace(**{k:getattr(native,k) for k in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns')},st_file_attributes=0)
        changed.st_ino+=1
        with mock.patch.object(gate.os,'fstat',return_value=changed):
            with self.assertRaisesRegex(RuntimeError,'between path stat and open'):gate.stable_read(source)
        changed.st_ino=0
        with mock.patch.object(gate.os,'stat',return_value=changed),mock.patch.object(gate,'parent_identity',return_value=[]),mock.patch.object(gate.os,'open') as opened:
            with self.assertRaisesRegex(RuntimeError,'identity is unavailable'):gate.stable_read(source)
            opened.assert_not_called()

    def test_source_mutation_or_replacement_after_metadata_cannot_pass(self):
        for kind in ('bytes','replacement','appeared'):
            with self.subTest(kind=kind):
                source=self.install/gate.REQUIRED_FILES[0];before=source.read_bytes()
                def runner(command,**options):
                    result=self.runner(command,**options)
                    if kind=='bytes':source.write_bytes(before+b'changed')
                    elif kind=='replacement':
                        replacement=self.root/'replace.dll';replacement.write_bytes(before);replacement.replace(source)
                    else:(self.install/'SWXRExporter.tlb').write_bytes(b'new')
                    return result
                report={}
                with self.assertRaises(RuntimeError):gate.collect(self.output,report,runner=runner)
                self.assertNotIn('collection_completed',report)
                self.assertIn('postcheck_error',report)
                source.write_bytes(before);(self.install/'SWXRExporter.tlb').unlink(missing_ok=True)

    def test_helper_failure_remains_first_error_even_if_postcheck_also_fails(self):
        original=subprocess.TimeoutExpired(['fixed-helper'],120,output=b'first stdout',stderr=b'first stderr')
        def runner(command,**options):
            (self.install/gate.REQUIRED_FILES[0]).write_bytes(b'changed')
            raise original
        report={}
        with self.assertRaises(subprocess.TimeoutExpired) as caught:gate.collect(self.output,report,runner=runner)
        self.assertIs(caught.exception,original);self.assertIn('postcheck_error',report)
        self.assertEqual((self.output/'metadata.stderr.log').read_bytes(),b'first stderr')

    def test_spoofed_helper_contract_file_set_or_hash_refuses_once(self):
        for kind in ('contract','hash','duplicate'):
            with self.subTest(kind=kind):
                calls=[]
                def runner(command,**options):
                    calls.append(command);result=self.runner(command,**options);p=Path(command[command.index('-OutputPath')+1]);j=json.loads(p.read_bytes())
                    if kind=='contract':j['signature_verified']=True
                    elif kind=='hash':j['files'][0]['sha256_after']='0'*64
                    else:j['files'][-1]=j['files'][0]
                    p.write_text(json.dumps(j));return result
                with self.assertRaises(RuntimeError):gate.collect(self.output,{},runner=runner)
                self.assertEqual(len(calls),1)

    def test_metadata_request_mutation_cannot_relabel_signature_payload(self):
        def runner(command,**options):
            result=self.runner(command,**options)
            Path(command[command.index('-RequestPath')+1]).write_bytes(b'changed request')
            return result
        report={}
        with self.assertRaisesRegex(RuntimeError,'metadata request changed'):gate.collect(self.output,report,runner=runner)
        self.assertIn('postcheck_error',report)
        self.assertNotIn('collection_completed',report)

    def test_missing_fixed_powershell_stops_before_input_or_metadata_access(self):
        self.ps.unlink();runner=mock.Mock();report={}
        with mock.patch.object(gate,'probe') as probe:
            with self.assertRaisesRegex(RuntimeError,'no install/fallback'):gate.collect(self.output,report,runner=runner)
            probe.assert_not_called()
        runner.assert_not_called()

    def test_input_byte_bound_and_post_read_path_replacement_refuse(self):
        source=self.install/gate.REQUIRED_FILES[0]
        with mock.patch.object(gate,'MAX_FILE',8),mock.patch.object(gate.os,'open') as opened:
            with self.assertRaisesRegex(RuntimeError,'byte bound'):gate.stable_read(source)
            opened.assert_not_called()
        native=gate.os.fstat;count=[]
        def fstat(descriptor):
            value=native(descriptor);count.append(True)
            if len(count)==2:
                replacement=self.root/'same-bytes.dll';replacement.write_bytes(source.read_bytes());replacement.replace(source)
            return value
        with mock.patch.object(gate.os,'fstat',side_effect=fstat):
            with self.assertRaisesRegex(RuntimeError,'path identity changed'):gate.stable_read(source)

    def known_runtime(self):
        return dict(os_name='nt', platform='win32', implementation='cpython',
                    version_info=[3,14,7,'final',0], version='portable fixture only', word_bits=64)

    def probed_stat(self, **changes):
        # Exact primitive values from root observation f22def2a..., no live input.
        fields=dict(st_dev=4217245827768940497,st_ino=1125899907056588,st_mode=33206,st_size=1112960,
                    st_mtime_ns=1758898084000000000,st_ctime_ns=1758898084000000000,
                    st_file_attributes=32,st_birthtime_ns=1758898084000000000,st_reparse_tag=0,st_nlink=1)
        fields.update(changes)
        return SimpleNamespace(**fields)

    def synthetic_stable_read(self, observation, *, path_after=None, handle_after=None):
        source=self.install/gate.REQUIRED_FILES[0]
        before=self.probed_stat(st_size=source.stat().st_size)
        opened=self.probed_stat(st_size=before.st_size,st_ctime_ns=1780227286818338600)
        final_path=self.probed_stat(**dict(vars(before),**(path_after or {})))
        final_handle=self.probed_stat(**dict(vars(opened),**(handle_after or {})))
        with mock.patch.object(gate,'runtime_identity',return_value=self.known_runtime()), \
                mock.patch.object(gate,'parent_identity',return_value=[]), \
                mock.patch.object(gate.os,'stat',side_effect=[before,final_path]), \
                mock.patch.object(gate.os,'fstat',side_effect=[opened,final_handle]):
            return gate.stable_read(source,observation=observation)

    def test_exact_root_ctime_pair_has_narrow_evidence_backed_comparison(self):
        before=self.probed_stat();opened=self.probed_stat(st_ctime_ns=1780227286818338600);record={}
        with mock.patch.object(gate,'runtime_identity',return_value=self.known_runtime()):
            self.assertTrue(gate.path_handle_match(before,opened,observation=record))
        self.assertEqual(before.st_ctime_ns,1758898084000000000)
        self.assertEqual(opened.st_ctime_ns,1780227286818338600)
        decision=record['path_handle_comparison']
        self.assertTrue(decision['accepted']);self.assertEqual(decision['differing_fields'],['ctime_ns'])
        self.assertTrue(all(decision['requirements'].values()))

    def test_observed_stable_read_keeps_raw_channels_hash_and_same_channel_fingerprint(self):
        record={};fingerprint,data=self.synthetic_stable_read(record)
        self.assertEqual(record['status'],'complete');self.assertTrue(record['descriptor_closed'])
        self.assertEqual(fingerprint['sha256'],hashlib.sha256(data).hexdigest())
        self.assertEqual(fingerprint['stat']['ctime_ns'],1758898084000000000)
        self.assertEqual(fingerprint['handle_stat']['ctime_ns'],1780227286818338600)
        self.assertEqual(record['before']['raw_fields']['st_ctime_ns'],1758898084000000000)
        self.assertEqual(record['opened']['raw_fields']['st_ctime_ns'],1780227286818338600)
        self.assertEqual(record['comparison_differences']['after_handle_vs_opened'],{})
        decoded=json.loads(json.dumps(record))
        self.assertEqual(decoded['before']['raw_fields']['st_dev'],4217245827768940497)

    def test_other_runtime_missing_birthtime_or_other_difference_refuses(self):
        for kind in ('OS','platform','implementation','patch','prerelease','bits','missing-path-birth','missing-handle-birth',
                     'zero-birth','unequal-birth','path-ctime-not-birth','device','file_id','mode','size','mtime','attributes','missing-attrs','link','tag'):
            with self.subTest(kind=kind):
                runtime=self.known_runtime();before=self.probed_stat();opened=self.probed_stat(st_ctime_ns=1780227286818338600)
                if kind=='OS':runtime['os_name']='posix'
                elif kind=='platform':runtime['platform']='darwin'
                elif kind=='implementation':runtime['implementation']='pypy'
                elif kind=='patch':runtime['version_info']=[3,14,8,'final',0]
                elif kind=='prerelease':runtime['version_info']=[3,14,7,'candidate',1]
                elif kind=='bits':runtime['word_bits']=32
                elif kind=='missing-path-birth':del before.st_birthtime_ns
                elif kind=='missing-handle-birth':del opened.st_birthtime_ns
                elif kind=='zero-birth':before.st_birthtime_ns=opened.st_birthtime_ns=0
                elif kind=='unequal-birth':opened.st_birthtime_ns+=1
                elif kind=='path-ctime-not-birth':before.st_ctime_ns+=1
                elif kind=='device':opened.st_dev+=1
                elif kind=='file_id':opened.st_ino+=1
                elif kind=='mode':opened.st_mode^=128
                elif kind=='size':opened.st_size+=1
                elif kind=='mtime':opened.st_mtime_ns+=1
                elif kind=='attributes':opened.st_file_attributes^=1
                elif kind=='missing-attrs':del opened.st_file_attributes
                elif kind=='link':opened.st_nlink+=1
                else:opened.st_reparse_tag=1
                record={}
                with mock.patch.object(gate,'runtime_identity',return_value=runtime):
                    self.assertFalse(gate.path_handle_match(before,opened,observation=record))
                self.assertFalse(record['path_handle_comparison']['accepted'])

    def test_same_channel_ctime_birthtime_or_other_fields_still_refuse_with_raw_values(self):
        for channel,field,value,stage in (
                ('handle','st_ctime_ns',1780227286818338601,'after_handle_check'),
                ('path','st_ctime_ns',1758898084000000001,'after_path_check'),
                ('handle','st_birthtime_ns',1758898084000000001,'after_handle_check'),
                ('path','st_birthtime_ns',1758898084000000001,'after_path_check'),
                ('handle','st_mtime_ns',1758898084000000001,'after_handle_check'),
                ('path','st_file_attributes',33,'after_path_check'),
                ('handle','st_nlink',2,'after_handle_check'),
                ('path','st_reparse_tag',1,'after_path_check')):
            with self.subTest(channel=channel,field=field):
                record={};options={'handle_after' if channel=='handle' else 'path_after':{field:value}}
                with self.assertRaises(RuntimeError):self.synthetic_stable_read(record,**options)
                key='after_handle' if channel=='handle' else 'after_path'
                self.assertEqual(record[key]['raw_fields'][field],value)
                self.assertEqual(record['failed_stage'],stage);self.assertTrue(record['descriptor_closed'])
                self.assertEqual(record['status'],'failed');self.assertNotIn('sha256',record)

    def test_failed_first_DLL_open_comparison_is_attached_before_metadata_and_json_safe(self):
        source=self.install/gate.REQUIRED_FILES[0];identity=source.stat().st_ino;native_fstat=gate.os.fstat
        def mismatch(descriptor):
            actual=native_fstat(descriptor)
            if actual.st_ino!=identity:return actual
            values={key:getattr(actual,key) for key in gate.RAW_STAT_FIELDS if hasattr(actual,key)}
            values['st_mode']^=128
            return SimpleNamespace(**values)
        report={};runner=mock.Mock()
        with mock.patch.object(gate.os,'fstat',side_effect=mismatch):
            with self.assertRaisesRegex(RuntimeError,'between path stat and open'):gate.collect(self.output,report,runner=runner)
        runner.assert_not_called();self.assertNotIn('metadata_attempted',report)
        self.assertNotIn('before',report['files'][0])
        record=report['files'][0]['stable_reads']['before']
        self.assertEqual(record['failed_stage'],'opened_check')
        self.assertEqual(record['opened']['comparison_fields']['mode'],record['before']['comparison_fields']['mode']^128)
        self.assertNotIn('after_handle',record);self.assertNotIn('after_path',record)
        (self.output/'partial.json').write_text(json.dumps(report))
        self.assertEqual(json.loads((self.output/'partial.json').read_text())['files'][0]['stable_reads']['before']['status'],'failed')

    def test_opened_handle_change_time_across_whole_metadata_collection_is_still_strict(self):
        source=self.install/gate.REQUIRED_FILES[0];native_stat=gate.os.stat;native_fstat=gate.os.fstat
        original=native_stat(source,follow_symlinks=False);count=[]
        def path_stat(path,*args,**kwargs):
            value=native_stat(path,*args,**kwargs)
            if Path(path)!=source:return value
            fields={key:getattr(value,key) for key in gate.RAW_STAT_FIELDS if hasattr(value,key)}
            fields.update(st_ctime_ns=1758898084000000000,st_birthtime_ns=1758898084000000000,
                          st_file_attributes=0,st_reparse_tag=0)
            return SimpleNamespace(**fields)
        def handle_stat(descriptor):
            value=native_fstat(descriptor)
            if value.st_ino!=original.st_ino:return value
            count.append(True)
            fields={key:getattr(value,key) for key in gate.RAW_STAT_FIELDS if hasattr(value,key)}
            fields.update(st_ctime_ns=1780227286818338600+(len(count)>2),st_birthtime_ns=1758898084000000000,
                          st_file_attributes=0,st_reparse_tag=0)
            return SimpleNamespace(**fields)
        report={}
        with mock.patch.object(gate,'runtime_identity',return_value=self.known_runtime()), \
                mock.patch.object(gate.os,'stat',side_effect=path_stat),mock.patch.object(gate.os,'fstat',side_effect=handle_stat):
            with self.assertRaisesRegex(RuntimeError,'fixed source stat/hash changed'):gate.collect(self.output,report,runner=self.runner)
        row=report['files'][0]
        self.assertEqual(row['before']['stat'],row['after']['stat'])
        self.assertEqual(row['before']['sha256'],row['after']['sha256'])
        self.assertNotEqual(row['before']['handle_stat']['ctime_ns'],row['after']['handle_stat']['ctime_ns'])
        self.assertNotIn('collection_completed',report)

    def test_observation_does_not_add_filesystem_reads_or_change_success_bytes(self):
        source=self.install/gate.REQUIRED_FILES[0];native_stat=gate.os.stat;native_fstat=gate.os.fstat
        traces=[];results=[]
        for observation in (None,{}):
            calls=[]
            def path_stat(*args,**kwargs):calls.append(('stat',str(args[0])));return native_stat(*args,**kwargs)
            def handle_stat(*args,**kwargs):calls.append(('fstat',));return native_fstat(*args,**kwargs)
            with mock.patch.object(gate.os,'stat',side_effect=path_stat),mock.patch.object(gate.os,'fstat',side_effect=handle_stat):
                results.append(gate.stable_read(source,observation=observation))
            traces.append(calls)
        self.assertEqual(traces[0],traces[1]);self.assertEqual(results[0],results[1])

    def test_static_source_contract_has_no_CAD_loader_search_or_network_paths(self):
        tree=ast.parse(SCRIPT.read_text());imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]+[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        self.assertFalse(any(x and x.split('.')[0] in ('ctypes','win32com','pythoncom','urllib','requests','socket') for x in imports))
        names=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse(set(names)&{'rglob','glob','walk','iterdir','LoadLibrary','Dispatch','GetActiveObject'})
        helper=SCRIPT.with_name('inspect-installed-glb-exporter-metadata.ps1').read_text()
        for forbidden in ('-ComObject','Get-AuthenticodeSignature','CheckSignature(','.Build(', 'LoadFrom(', 'LoadLibrary', 'Invoke-WebRequest','Start-Process','Set-ExecutionPolicy','Add-Type -Path','-TypeDefinition','DllImport', 'WinVerifyTrust','X509Chain','Get-ChildItem'):
            self.assertNotIn(forbidden,helper)
        self.assertIn('$cms.Decode(',helper);self.assertIn('FileVersionInfo]::GetVersionInfo',helper)
        self.assertIn('$blocked + [System.IO.Path]::DirectorySeparatorChar',helper)
        self.assertIn('[System.IO.FileMode]::CreateNew',helper)
        self.assertIn('$bytes.Length -gt 16777216',helper)
        self.assertNotIn("'\\\\'",helper)
        self.assertEqual(gate.REQUIRED_FILES,('sldgltfu.dll','spiop/files/code/bin/SPAXGLTFBase.dll','spiop/files/code/bin/SPAXGLTFVisualization.dll','spiop/files/code/bin/VisGltf.dll'))


if __name__=='__main__':unittest.main()
