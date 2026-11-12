import copy
import ctypes
import hashlib
import importlib.util
from pathlib import Path
import stat
import unittest

spec=importlib.util.spec_from_file_location('file_observer',Path(__file__).with_name('file_forensics.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
DATA=b'native-data';SHA=hashlib.sha256(DATA).hexdigest()
ID=dict(VolumeSerialNumber=42,FileId128_bytes_hex=bytes(range(1,17)).hex())
PYROW=dict(st_dev=42,st_ino=int.from_bytes(bytes(range(1,17)),'little'),st_mode=stat.S_IFREG|0o444,
           st_size=len(DATA),st_atime_ns=11,st_mtime_ns=22,st_ctime_ns=33,st_birthtime_ns=33,
           st_file_attributes=33,st_reparse_tag=0,st_nlink=1)
NATIVE=dict(id_before=ID,basic=dict(CreationTime=101,LastAccessTime=102,LastWriteTime=103,ChangeTime=104,FileAttributes=33),
            standard=dict(AllocationSize=4096,EndOfFile=len(DATA),NumberOfLinks=1,DeletePending=0,Directory=0),
            opened_path=r'\\?\C:\Workspace\copy\MarkingJig.REND.SLDASM',id_after=ID)

class Fake:
    def __init__(self):
        self.opened=[];self.closed=[];self.offset=0;self.read_calls=0;self.fault=None;self.close_fault=None
        self.py_change=lambda row,channel:None;self.native_change=lambda row,fd:None
    def open(self,path):
        fd=len(self.opened)+1;self.opened.append(fd);return fd
    def close(self,fd):
        self.closed.append(fd)
        if self.close_fault==fd:raise RuntimeError('injected close failure')
    def path(self,path):
        row=copy.deepcopy(PYROW);self.py_change(row,'path');return row
    def held(self,fd):
        row=copy.deepcopy(PYROW);row['st_ctime_ns']=44;self.py_change(row,'held');return row
    def native(self,fd,row,step):
        source=copy.deepcopy(NATIVE);self.native_change(source,fd)
        for name in source:
            row[name]=step(name,lambda name=name:self.get(source,name))
    def get(self,row,name):
        if self.fault==name:raise OSError('injected native info failure')
        return row[name]
    def read(self,fd,count):
        self.read_calls+=1;data=DATA[self.offset:self.offset+count];self.offset+=len(data);return data

class Tests(unittest.TestCase):
    def run_capture(self,backend=None,sha=SHA):
        b=backend or Fake();r=m.collect(b,r'C:\Workspace\copy\MarkingJig.REND.SLDASM',sha)
        return b,r
    def stopped(self,b):
        b,r=self.run_capture(b);self.assertFalse(r['complete']);self.assertIsNotNone(r['first_error']);self.assertIn(1,b.closed);return r
    def test_three_channels_two_fixed_rounds_readonly_and_full_identity(self):
        b,r=self.run_capture();self.assertTrue(r['complete']);self.assertFalse(r['admission_or_CAS_replacement'])
        self.assertEqual(r['hash'],dict(bytes_read=len(DATA),sha256=SHA));self.assertEqual(len(r['snapshots']),2)
        self.assertEqual(b.opened,[1,2,3]);self.assertCountEqual(b.closed,b.opened)
        self.assertEqual(r['snapshots'][0]['raw_python_cross_channel_differences']['st_ctime_ns'],dict(path=33,held=44))
        self.assertEqual(r['same_channel_changes'],{});self.assertEqual(r['application_or_CAD_calls'],0)
    def test_win32_layout_sizes_offsets_and_full_128_bit_id(self):
        self.assertEqual([ctypes.sizeof(t) for t in (m.Basic,m.Standard,m.FileID)],[40,24,24])
        self.assertEqual((m.Basic.ChangeTime.offset,m.Basic.FileAttributes.offset),(24,32))
        self.assertEqual((m.Standard.DeletePending.offset,m.Standard.Directory.offset),(20,21))
        self.assertEqual(m.FileID.FileId.offset,8);self.assertEqual(ctypes.sizeof(m.FileID().FileId),16)
    def test_no_write_create_delete_or_normalized_path_flags(self):
        self.assertEqual((m.GENERIC_READ,m.SHARE_READ_WRITE,m.OPEN_EXISTING,m.OPEN_REPARSE_POINT_NORMAL,m.FILE_NAME_OPENED),
                         (0x80000000,3,3,0x200080,8))
    def test_wrong_same_named_file_id_refused_before_hash(self):
        b=Fake()
        def mutate(row,fd):
            if fd!=1:row['id_before']=row['id_after']=dict(ID,FileId128_bytes_hex='ff'*16)
        b.native_change=mutate;r=self.stopped(b);self.assertEqual(b.read_calls,0)
    def test_volume_mismatch_refused_before_hash(self):
        b=Fake();b.native_change=lambda row,fd:row['id_before'].update(VolumeSerialNumber=99)
        self.stopped(b);self.assertEqual(b.read_calls,0)
    def test_zero_or_incomplete_full_id_never_accepted(self):
        for raw in ('00'*16,'12',None):
            with self.subTest(raw=raw):
                b=Fake()
                def mutate(row,fd):row['id_before']=row['id_after']=dict(ID,FileId128_bytes_hex=raw)
                b.native_change=mutate;self.stopped(b);self.assertEqual(b.read_calls,0)
    def test_python_identity_and_all_non_ctime_fields_are_strict(self):
        for field in set(m.FIELDS)-{'st_ctime_ns'}:
            with self.subTest(field=field):
                b=Fake()
                def mutate(row,channel):
                    if channel=='held':row[field]+=1
                b.py_change=mutate;self.stopped(b);self.assertEqual(b.read_calls,0)
    def test_within_held_ctime_one_ns_change_not_tolerated_or_called_content_write(self):
        b=Fake()
        def mutate(row,channel):
            if channel=='held' and b.offset:row['st_ctime_ns']+=1
        b.py_change=mutate;r=self.stopped(b)
        self.assertIn('not inferred to be a content write',r['first_error']['message'])
        self.assertEqual(r['hash']['sha256'],SHA);self.assertIn('python_held',r['same_channel_changes'])
    def test_raw_win32_each_time_field_change_is_retained(self):
        for field in ('CreationTime','LastAccessTime','LastWriteTime','ChangeTime'):
            with self.subTest(field=field):
                b=Fake()
                def mutate(row,fd):
                    if b.offset:row['basic'][field]+=1
                b.native_change=mutate;r=self.stopped(b)
                self.assertEqual(r['same_channel_changes']['win32_held']['after']['basic'][field],NATIVE['basic'][field]+1)
    def test_readonly_hardlink_reparse_missing_state_refused(self):
        for field,value in (('st_nlink',2),('st_file_attributes',32),('st_reparse_tag',1),('st_size',None)):
            with self.subTest(field=field,value=value):
                b=Fake();b.py_change=lambda row,channel:row.update({field:value});self.stopped(b);self.assertEqual(b.read_calls,0)
    def test_native_directory_delete_pending_and_size_mismatch_stop(self):
        for key,value in (('Directory',1),('DeletePending',1),('EndOfFile',len(DATA)+1),('NumberOfLinks',2)):
            with self.subTest(key=key):
                b=Fake();b.native_change=lambda row,fd:row['standard'].update({key:value});self.stopped(b)
    def test_allocation_size_is_raw_not_assumed_equal_or_greater_than_file_length(self):
        b=Fake();b.native_change=lambda row,fd:row['standard'].update(AllocationSize=0)
        b,r=self.run_capture(b);self.assertTrue(r['complete']);self.assertEqual(r['snapshots'][0]['win32_held']['standard']['AllocationSize'],0)
    def test_native_failure_preserves_partial_fields_and_stops_no_hash(self):
        b=Fake();b.fault='standard';r=self.stopped(b)
        self.assertIn('basic',r['snapshots'][0]['win32_held']);self.assertNotIn('standard',r['snapshots'][0]['win32_held'])
        self.assertEqual(b.read_calls,0);self.assertEqual(len(r['snapshots']),1)
    def test_first_native_error_survives_held_close_failure(self):
        b=Fake();b.fault='standard';b.close_fault=1;r=self.stopped(b)
        self.assertEqual(r['first_error']['type'],'OSError');self.assertEqual(r['cleanup_errors'][0]['stage'],'close-held')
    def test_reopened_close_failure_stops_before_hash(self):
        b=Fake();b.close_fault=2;r=self.stopped(b);self.assertEqual(b.read_calls,0)
        self.assertEqual(r['cleanup_errors'][0]['stage'],'close-reopened')
    def test_wrong_content_hash_stops_no_second_snapshot(self):
        b,r=self.run_capture(sha='00'*32);self.assertFalse(r['complete']);self.assertEqual(len(r['snapshots']),1)
        self.assertEqual(r['hash']['sha256'],SHA);self.assertEqual(r['first_error']['message'],'source content hash differs')
    def test_shortened_content_stops_and_releases(self):
        b=Fake();b.read=lambda fd,size:b'';r=self.stopped(b)
        self.assertEqual(r['hash']['bytes_read'],0);self.assertEqual(len(r['snapshots']),1)
    def test_growing_source_eof_not_discarded(self):
        b=Fake();original=b.read
        b.read=lambda fd,size:b'x' if b.offset==len(DATA) else original(fd,size)
        r=self.stopped(b);self.assertIn('grew',r['first_error']['message'])
    def test_intermediate_reports_have_raw_time_domain_and_call_order(self):
        saved=[];b=Fake();r=m.collect(b,'test',SHA,persist=lambda row:saved.append(copy.deepcopy(row)))
        self.assertGreater(len(saved),10);self.assertTrue(r['complete'])
        self.assertEqual([r['sequence'] for r in r['timeline']],list(range(len(r['timeline']))))
        self.assertTrue(all(type(row['wall_unix_ns']) is int and type(row['monotonic_ns']) is int for row in r['timeline']))
    def test_path_is_private_fixed_top_copy_without_unc_device_or_ADS(self):
        m.valid_path(r'C:\Workspace\scope\MarkingJig.REND.SLDASM')
        for path in (r'\\server\share\MarkingJig.REND.SLDASM',r'\\?\C:\Workspace\MarkingJig.REND.SLDASM',r'C:\elsewhere\MarkingJig.REND.SLDASM',r'C:\Workspace\..\MarkingJig.REND.SLDASM',r'C:\Workspace\MarkingJig.REND.SLDASM:stream',r'C:\Workspace\other.SLDASM'):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):m.valid_path(path)

if __name__=='__main__':unittest.main()
