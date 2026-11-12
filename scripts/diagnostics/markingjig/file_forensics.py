"""Standalone zero-CAD Windows file observation. No application imports at import/run.
Not an admission/CAS replacement. All timestamps are raw and never normalized.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat
import sys
import time

SOURCE = 'MarkingJig.REND.SLDASM'
SOURCE_SHA = '80bfa9d4bc453277dc0ba4dd9dbdf8f0d315a090aa3bab429843b1f9bc308530'
MAX_BYTES = 64*1024*1024
GENERIC_READ, SHARE_READ_WRITE, OPEN_EXISTING = 0x80000000, 3, 3
OPEN_REPARSE_POINT_NORMAL, FILE_NAME_OPENED = 0x200080, 8
FIELDS = ('st_dev','st_ino','st_mode','st_size','st_atime_ns','st_mtime_ns','st_ctime_ns',
          'st_birthtime_ns','st_file_attributes','st_reparse_tag','st_nlink')


class Basic(C.Structure):
    _fields_ = [('CreationTime',C.c_int64),('LastAccessTime',C.c_int64),
                ('LastWriteTime',C.c_int64),('ChangeTime',C.c_int64),('FileAttributes',C.c_uint32)]


class Standard(C.Structure):
    _fields_ = [('AllocationSize',C.c_int64),('EndOfFile',C.c_int64),('NumberOfLinks',C.c_uint32),
                ('DeletePending',C.c_uint8),('Directory',C.c_uint8)]


class FileID(C.Structure):
    _fields_ = [('VolumeSerialNumber',C.c_uint64),('FileId',C.c_uint8*16)]


def require(ok, message):
    if not ok:raise RuntimeError(message)


def stat_row(value):
    return {name:getattr(value,name,None) for name in FIELDS}


def record_error(error):
    return dict(type=type(error).__name__,message=str(error),winerror=getattr(error,'winerror',None),
                errno=getattr(error,'errno',None))


def valid_path(raw):
    p=PureWindowsPath(raw)
    require(type(raw) is str and p.is_absolute() and p.drive=='C:' and len(p.parts)>2 and
            p.parts[1]=='Workspace' and p.name==SOURCE and '..' not in p.parts and
            not any(':' in part for part in p.parts[1:]), 'fixed private C:\\Workspace top copy required')


def valid_output(raw):
    p=PureWindowsPath(raw)
    require(p.is_absolute() and p.drive=='C:' and len(p.parts)>2 and p.parts[1]=='Workspace' and
            '..' not in p.parts and p.suffix=='.json' and not any(':' in part for part in p.parts[1:]),
            'new private C:\\Workspace ordinary JSON output required; ADS refused')


class NativeBackend:
    """Only kernel32 reads plus CRT read descriptor. Loading is explicit, Windows-only."""
    def __init__(self):
        require(sys.platform=='win32' and sys.implementation.name=='cpython' and
                sys.version_info[:3]==(3,14,7) and C.sizeof(C.c_void_p)==8,'reviewed Windows CPython3.14.7 64-bit required')
        import msvcrt
        self.transfer_cleanup_errors=[]
        self.crt=msvcrt;self.k=C.WinDLL('kernel32',use_last_error=True)
        self.k.CreateFileW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p]
        self.k.CreateFileW.restype=C.c_void_p
        self.k.CloseHandle.argtypes=[C.c_void_p];self.k.CloseHandle.restype=C.c_int32
        self.k.GetFileInformationByHandleEx.argtypes=[C.c_void_p,C.c_int32,C.c_void_p,C.c_uint32]
        self.k.GetFileInformationByHandleEx.restype=C.c_int32
        self.k.GetFinalPathNameByHandleW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_uint32,C.c_uint32]
        self.k.GetFinalPathNameByHandleW.restype=C.c_uint32
        require((C.sizeof(Basic),C.sizeof(Standard),C.sizeof(FileID))==(40,24,24),'Win32 ABI layout differs')

    def path(self, raw):return stat_row(os.stat(raw,follow_symlinks=False))
    def held(self, fd):return stat_row(os.fstat(fd))
    def read(self, fd, size):return os.read(fd,size)
    def close(self, fd):os.close(fd)

    def open(self, raw):
        for p in (Path(raw),*Path(raw).parents):
            info=os.stat(p,follow_symlinks=False)
            require(not stat.S_ISLNK(info.st_mode) and not (getattr(info,'st_file_attributes',0)&0x400), 'source/parent reparse or symlink refused')
        handle=self.k.CreateFileW(raw,GENERIC_READ,SHARE_READ_WRITE,None,OPEN_EXISTING,OPEN_REPARSE_POINT_NORMAL,None)
        if handle==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
        try:return self.crt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
        except BaseException:
            if not self.k.CloseHandle(handle):
                self.transfer_cleanup_errors.append(dict(stage='CloseHandle-after-failed-CRT-transfer',winerror=C.get_last_error()))
            raise

    def native(self, fd, row, step):
        handle=self.crt.get_osfhandle(fd)
        def get(kind, structure):
            value=structure()
            if not self.k.GetFileInformationByHandleEx(handle,kind,C.byref(value),C.sizeof(value)):
                raise C.WinError(C.get_last_error())
            if structure is FileID:
                return dict(VolumeSerialNumber=value.VolumeSerialNumber,FileId128_bytes_hex=bytes(value.FileId).hex())
            return {name:int(getattr(value,name)) for name,kind in structure._fields_}
        row['id_before']=step('FileIdInfo-before',lambda:get(18,FileID))
        row['basic']=step('FileBasicInfo',lambda:get(0,Basic))
        row['standard']=step('FileStandardInfo',lambda:get(1,Standard))
        def opened_path():
            buf=C.create_unicode_buffer(32768)
            length=self.k.GetFinalPathNameByHandleW(handle,buf,len(buf),FILE_NAME_OPENED)
            if not length:raise C.WinError(C.get_last_error())
            require(length<len(buf),'opened path exceeds bounded buffer; no alternate path query')
            return buf.value
        row['opened_path']=step('GetFinalPathNameByHandleW-FILE_NAME_OPENED',opened_path)
        row['id_after']=step('FileIdInfo-after',lambda:get(18,FileID))


def identity_checks(row):
    path,held=row['python_path'],row['python_held']
    for value in (path,held):
        require(all(type(value.get(k)) is int for k in FIELDS),'incomplete Python stat fields')
        require(stat.S_ISREG(value['st_mode']) and 0<value['st_size']<=MAX_BYTES and value['st_nlink']==1 and
                value['st_dev']>0 and value['st_ino']>0 and value['st_file_attributes']&1 and
                not value['st_file_attributes']&0x400 and value['st_reparse_tag']==0,'not ordinary independent readonly source')
    # ctime stays raw; every other Python field is compared exactly.
    for key in FIELDS:
        if key=='st_ctime_ns':continue
        require(path[key]==held[key],'Python identity/state channel disagreement: '+key)
    first=row['win32_held']['id_before']
    require(type(first['VolumeSerialNumber']) is int and first['VolumeSerialNumber']>0 and
            type(first['FileId128_bytes_hex']) is str and len(first['FileId128_bytes_hex'])==32 and
            int(first['FileId128_bytes_hex'],16)>0,'full Win32 ID unavailable')
    for native in (row['win32_held'],row['win32_path_reopen']):
        require(native['id_before']==native['id_after']==first,'same physical file identity not proven')
        basic,standard=native['basic'],native['standard']
        require(standard['DeletePending']==standard['Directory']==0 and standard['NumberOfLinks']==1 and
                standard['AllocationSize']>=0 and standard['EndOfFile']>0,'unsafe FileStandardInfo')
        require(basic['FileAttributes']==held['st_file_attributes'] and
                standard['EndOfFile']==held['st_size'] and standard['NumberOfLinks']==held['st_nlink'],'Win32/Python attributes/size/links differ')
    # Integer/byte layout check only: no timestamp conversion or path normalization.
    require(first['VolumeSerialNumber']==held['st_dev'] and
            int.from_bytes(bytes.fromhex(first['FileId128_bytes_hex']),'little')==held['st_ino'],'Win32/Python full file identity mapping differs')
    row['physical_identity_proven']=True
    row['raw_python_cross_channel_differences']={k:dict(path=path[k],held=held[k]) for k in FIELDS if path[k]!=held[k]}


def deltas(first, second):
    return {key:dict(before=first[key],after=second[key]) for key in
            ('python_path','python_held','win32_held','win32_path_reopen') if first[key]!=second[key]}


def collect(backend, path, expected_sha, report=None, persist=lambda _:None):
    report={} if report is None else report
    report.update(schema='swcli.file-three-channel-forensics.v1',path=path,expected_sha256=expected_sha,
                  application_or_CAD_calls=0,admission_or_CAS_replacement=False,complete=False,
                  snapshots=[],timeline=[],first_error=None,cleanup_errors=[],hash=dict(bytes_read=0))
    fd=None
    def step(name, function):
        event=dict(sequence=len(report['timeline']),operation=name,wall_unix_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),phase='begin')
        report['timeline'].append(event);persist(report)
        try:result=function()
        except BaseException as error:
            event['phase']='error';event['error']=record_error(error)
            event['end_wall_unix_ns']=time.time_ns();event['end_monotonic_ns']=time.monotonic_ns();persist(report);raise
        event['phase']='end';event['end_wall_unix_ns']=time.time_ns();event['end_monotonic_ns']=time.monotonic_ns();persist(report)
        return result
    def snapshot(label):
        row=dict(label=label);report['snapshots'].append(row)
        row['python_path']=step(label+':os.stat-no-follow',lambda:backend.path(path))
        row['python_held']=step(label+':os.fstat-held',lambda:backend.held(fd))
        row['win32_held']={};backend.native(fd,row['win32_held'],lambda name,fn:step(label+':held:'+name,fn))
        reopened=None;body_error=None
        try:
            reopened=step(label+':CreateFileW-reopen-readonly',lambda:backend.open(path))
            row['win32_path_reopen']={};backend.native(reopened,row['win32_path_reopen'],lambda name,fn:step(label+':reopen:'+name,fn))
        except BaseException as error:
            body_error=error;raise
        finally:
            if reopened is not None:
                try:step(label+':close-reopened',lambda:backend.close(reopened))
                except BaseException as error:
                    report['cleanup_errors'].append(dict(stage='close-reopened',error=record_error(error)))
                    if body_error is None:raise
        identity_checks(row);persist(report);return row
    try:
        report['python_path_before_open']=step('os.stat-before-open',lambda:backend.path(path))
        fd=step('CreateFileW-held-readonly',lambda:backend.open(path))
        before=snapshot('before-read')
        require(report['python_path_before_open']==before['python_path'],'path metadata changed while establishing hold')
        digest=hashlib.sha256();remaining=before['python_held']['st_size']
        while remaining:
            block=step('read-held-source',lambda:backend.read(fd,min(65536,remaining)))
            require(type(block) is bytes and 0<len(block)<=remaining,'source shortened/invalid read')
            remaining-=len(block);report['hash']['bytes_read']+=len(block);digest.update(block)
        require(step('read-held-EOF',lambda:backend.read(fd,1))==b'','source grew during read')
        report['hash']['sha256']=digest.hexdigest();persist(report)
        require(report['hash']['sha256']==expected_sha,'source content hash differs')
        after=snapshot('after-read');report['same_channel_changes']=deltas(before,after)
        require(not report['same_channel_changes'],'source metadata changed; not inferred to be a content write')
        require(not report['cleanup_errors'],'reopen cleanup failed')
        report['complete']=True
    except BaseException as error:report['first_error']=record_error(error)
    finally:
        if fd is not None:
            try:step('close-held',lambda:backend.close(fd))
            except BaseException as error:report['cleanup_errors'].append(dict(stage='close-held',error=record_error(error)))
        report['cleanup_errors'].extend(getattr(backend,'transfer_cleanup_errors',[]))
        report['complete']=report['complete'] and not report['cleanup_errors'];persist(report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();valid_path(args.path)
    require(args.sha256==SOURCE_SHA,'only pinned top MarkingJig readonly copy approved by this tool')
    valid_output(str(args.output))
    for parent in args.output.parents:
        info=os.stat(parent,follow_symlinks=False)
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                not getattr(info,'st_file_attributes',0)&0x400,'output parent reparse/symlink refused')
    # No source file or Win32 API is touched until explicit platform/path arguments pass.
    backend=NativeBackend();report=dict(python=sys.version,python_executable=sys.executable,
        kernel_open=dict(access=GENERIC_READ,share=SHARE_READ_WRITE,disposition=OPEN_EXISTING,flags=OPEN_REPARSE_POINT_NORMAL),
        raw_time_units=dict(Win32='signed 100ns FILETIME ticks since1601 UTC; never converted',Python='raw *_ns from stat_result; no cross-channel ctime interpretation'),
        explicit_source_write_calls=0,implicit_OS_access_time_updates_not_suppressed=True,window='two fixed snapshots bracketing one bounded hash read; no wait, hook or CAD action')
    with args.output.open('x',encoding='utf-8') as output:
        def persist(value):
            output.seek(0);json.dump(value,output,indent=2);output.write('\n');output.truncate();output.flush()
        collect(backend,args.path,args.sha256,report,persist)
    return 0 if report['complete'] else 1


if __name__=='__main__':raise SystemExit(main())
