"""CI units only: one retained, identity-verified native process handle."""
from datetime import datetime,timezone
import ntpath
import os
import base64
import sys
from copy import deepcopy

EXPECTED_CI_IMAGE=r'C:\Program Files\SOLIDWORKS\SLDWORKS.exe'


def require(value,message):
    if not value:raise RuntimeError(message)


def process_identity(handle,*,observation=None):
    import ctypes
    from ctypes import wintypes
    import win32process
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    query=kernel.QueryFullProcessImageNameW;query.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)];query.restype=wintypes.BOOL
    image=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(image))
    if observation is not None:
        observation['image_query']=dict(api='QueryFullProcessImageNameW',argtypes=['HANDLE','DWORD','LPWSTR','PDWORD'],restype='BOOL',flags=0,input_capacity_chars=len(image),ctypes_bytes=dict(HANDLE=ctypes.sizeof(wintypes.HANDLE),DWORD=ctypes.sizeof(wintypes.DWORD),BOOL=ctypes.sizeof(wintypes.BOOL),wchar=ctypes.sizeof(ctypes.c_wchar)),byteorder=sys.byteorder)
    success=bool(query(int(handle),0,image,ctypes.byref(size)))
    error_code=None if success else ctypes.get_last_error()
    if observation is not None:
        count=min(len(image),int(size.value)+1)
        observation['image_query'].update(success=success,last_error=error_code,returned_chars=int(size.value),image=image.value,image_repr=repr(image.value),image_length_py_chars=len(image.value),image_length_utf16_units=len(image.value.encode('utf-16-le',errors='surrogatepass'))//2,nul_at_returned_index=(image[size.value]=='\0' if size.value<len(image) else None),buffer_prefix_b64=base64.b64encode(ctypes.string_at(ctypes.addressof(image),count*ctypes.sizeof(ctypes.c_wchar))).decode('ascii'))
    if not success:raise ctypes.WinError(error_code)
    created=win32process.GetProcessTimes(handle)['CreationTime']
    return dict(pid=win32process.GetProcessId(handle),image=image.value,creation_utc=created.astimezone(timezone.utc).isoformat(),creation_timestamp=created.timestamp())


def image_path_identity(image,expected_image,*,observation):
    """Collect OS expansion + file identity; never infer an alias from its spelling."""
    import ctypes
    from ctypes import wintypes
    observation.update(raw_image=image,expected_image=expected_image,representation='raw-query-image retained; admission compares OS-expanded full path plus same-file evidence')
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        expand=kernel.GetLongPathNameW;expand.argtypes=[wintypes.LPCWSTR,wintypes.LPWSTR,wintypes.DWORD];expand.restype=wintypes.DWORD
        buffer=ctypes.create_unicode_buffer(32768)
        query=observation['expansion']=dict(api='GetLongPathNameW',argtypes=['LPCWSTR','LPWSTR','DWORD'],restype='DWORD',input_capacity_chars=len(buffer),ctypes_bytes=dict(DWORD=ctypes.sizeof(wintypes.DWORD),wchar=ctypes.sizeof(ctypes.c_wchar)),byteorder=sys.byteorder)
        returned=int(expand(image,buffer,len(buffer)));last_error=ctypes.get_last_error() if returned==0 else None
        expanded=buffer.value;units=len(expanded.encode('utf-16-le',errors='surrogatepass'))//2
        query.update(returned_chars=returned,last_error=last_error,expanded_image=expanded,expanded_image_repr=repr(expanded),image_length_py_chars=len(expanded),image_length_utf16_units=units,nul_at_returned_index=(buffer[returned]=='\0' if returned<len(buffer) else None),buffer_prefix_b64=base64.b64encode(ctypes.string_at(ctypes.addressof(buffer),min(len(buffer),returned+1)*ctypes.sizeof(ctypes.c_wchar))).decode('ascii'))
        if returned==0:raise ctypes.WinError(last_error)
        require(returned<len(buffer),'native expanded image exceeded the single bounded buffer; no retry')
        require(returned==units and query['nul_at_returned_index'] is True,'native expanded image length or NUL differs')
        for role,path in (('raw',image),('expected',expected_image)):
            value=os.stat(path);observation[role+'_stat']=dict(device=value.st_dev,inode=value.st_ino)
        observation['samefile']=os.path.samefile(image,expected_image)
        raw=observation['raw_stat'];expected=observation['expected_stat']
        observation['recorded_file_ids_match']=raw==expected
        observation['file_ids_available']=all(type(value['device']) is int and value['device']>=0 and type(value['inode']) is int and value['inode']>0 for value in (raw,expected))
        return expanded
    except BaseException as error:
        observation['error']=dict(type=type(error).__name__,message=str(error),errno=getattr(error,'errno',None),winerror=getattr(error,'winerror',None))
        raise


def validate_identity(identity,pid,launched,observed,expected_image):
    require(identity['pid']==pid,'native retained handle PID differs')
    require(ntpath.normcase(ntpath.normpath(identity['image']))==ntpath.normcase(ntpath.normpath(expected_image)),'native full image differs from this CI installation')
    require(launched<=identity['creation_timestamp']<=observed,'native creation time is outside this run startup window')


def capture(pid,launched,expected_image=EXPECTED_CI_IMAGE,*,terminate_right=True,observe=None):
    import win32api
    import win32con
    # QUERY_LIMITED_INFORMATION + TERMINATE + SYNCHRONIZE, only this proven PID.
    handle=win32api.OpenProcess(win32con.SYNCHRONIZE|0x1000|(win32con.PROCESS_TERMINATE if terminate_right else 0),False,pid)
    observation=dict(requested_pid=pid,expected_image=expected_image,expected_image_repr=repr(expected_image),launch_timestamp=launched,terminate_right=terminate_right,capture_status=dict(phase='reading'))
    emitted=False
    try:
        identity=process_identity(handle,observation=observation);observed=datetime.now(timezone.utc).timestamp()
        observation.update(observed_identity=identity,observed_timestamp=observed,comparison_inputs=dict(actual_image_normalized=ntpath.normcase(ntpath.normpath(identity['image'])),expected_image_normalized=ntpath.normcase(ntpath.normpath(expected_image))))
        path_evidence=observation['image_path_identity']={};observation['capture_status']['phase']='resolving-image-path'
        expanded=image_path_identity(identity['image'],expected_image,observation=path_evidence)
        admission_identity={**identity,'image':expanded}
        path_evidence['expanded_matches_expected']=ntpath.normcase(ntpath.normpath(expanded))==ntpath.normcase(ntpath.normpath(expected_image))
        observation.update(admission_identity=admission_identity,identity_image_representation='returned/retained identity.image is raw Query output; admission_identity.image is OS-expanded',expanded_image_normalized=ntpath.normcase(ntpath.normpath(expanded)))
        # Persist raw/expanded/stat evidence BEFORE admitting this retained handle.
        if observe:
            emitted=True;observation['capture_status']['phase']='persisting';observe(deepcopy(observation))
        observation['capture_status']['phase']='validating'
        validate_identity(admission_identity,pid,launched,observed,expected_image)
        require(path_evidence['samefile'] is True and path_evidence['recorded_file_ids_match'] is True and path_evidence['file_ids_available'] is True,'native image paths do not prove the same installed file')
        observation['capture_status']['phase']='verified'
        return handle,identity
    except BaseException as error:
        observation['capture_status'].update(error_type=type(error).__name__,error_message=str(error))
        error.identity_observation=observation
        if observe and not emitted:
            try:observe(deepcopy(observation))
            except BaseException as evidence_error:error.identity_observation_error=str(evidence_error)
        try:handle.Close()
        except BaseException as close_error:error.identity_handle_close_error=str(close_error)
        raise


def exited(handle):
    import win32event
    return win32event.WaitForSingleObject(handle,0)==win32event.WAIT_OBJECT_0


def terminate(handle,identity):
    import win32api
    # Recheck the same retained handle, never reopen or search for a substitute PID.
    require(process_identity(handle)==identity,'native retained handle identity changed')
    win32api.TerminateProcess(handle,1)
