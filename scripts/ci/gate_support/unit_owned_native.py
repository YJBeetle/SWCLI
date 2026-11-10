"""CI units only: one retained, identity-verified native process handle."""
from datetime import datetime,timezone
import ntpath
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
        # Persist raw observation BEFORE any PID/image/creation predicate can fail.
        if observe:
            emitted=True;observation['capture_status']['phase']='persisting';observe(deepcopy(observation))
        observation['capture_status']['phase']='validating'
        validate_identity(identity,pid,launched,observed,expected_image)
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
