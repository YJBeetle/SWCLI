"""External Windows watchdog for one owned mate group; no CAD retries/restarts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

NATIVE_SECONDS = 600
GROUP_SECONDS = 1800


def budget_failure(now, started, active_since):
    if now - started >= GROUP_SECONDS:
        return 'group-budget-1800-seconds'
    if active_since is not None and now - active_since >= NATIVE_SECONDS:
        return 'native-call-budget-600-seconds'
    return None


def active_call(path):
    active = None
    if path.is_file():
        # A final line may still be in flight. Never invent a completed call.
        for line in path.read_text(encoding='utf-8').splitlines():
            try: item=json.loads(line)
            except ValueError: continue
            if item.get('phase') == 'begin': active=item.get('time')
            elif item.get('phase') in ('end','error'): active=None
    return active


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--swconst',type=Path,required=True)
    args=parser.parse_args(argv)
    if sys.platform != 'win32':parser.error('Windows owned-host calibration only')
    args.output_dir.mkdir()
    output=args.output_dir.resolve()
    child_output=output/'native'
    started=time.time()
    host_handle=None
    host_pid=None
    failure=None
    import win32api
    import win32con
    import win32process
    # Dedicated hosted runner only: refuse preexisting CAD processes before
    # launching the script that also requires acquire_resident_app owned=True.
    probe=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        '@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count'],
        capture_output=True,text=True,timeout=30,check=True)
    if probe.stdout.strip() != '0':raise RuntimeError('preexisting SOLIDWORKS host; calibration refused')
    with (output/'stdout.log').open('w',encoding='utf-8') as stdout, (output/'stderr.log').open('w',encoding='utf-8') as stderr:
        process=subprocess.Popen([sys.executable,'-I',str(Path(__file__).with_name('verify-assembly-mates-calibration.py')),
                                  '--output-dir',str(child_output),'--swconst',str(args.swconst)],stdout=stdout,stderr=stderr)
        try:
            while process.poll() is None:
                report=child_output/'report.json'
                if host_handle is None and report.is_file():
                    try:state=json.loads(report.read_text(encoding='utf-8'))
                    except ValueError:state={}
                    host=state.get('host',{})
                    if host:
                        pid=host.get('process_id')
                        if type(pid) is not int or pid<=0:raise RuntimeError('owned host PID unavailable')
                        handle=win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION|win32con.PROCESS_VM_READ|
                            win32con.PROCESS_TERMINATE|win32con.SYNCHRONIZE,False,pid)
                        try:
                            image=win32process.GetModuleFileNameEx(handle,0)
                            created=win32process.GetProcessTimes(handle)['CreationTime'].timestamp()
                            if Path(image).name.casefold()!='sldworks.exe' or created<started:
                                raise RuntimeError('reported host is not a new owned SOLIDWORKS process')
                        except BaseException:
                            handle.Close();raise
                        host_handle,host_pid=handle,pid
                failure=budget_failure(time.time(),started,active_call(child_output/'trace.jsonl'))
                if failure:break
                time.sleep(.2)
        except BaseException as error:
            failure='supervisor-error: '+type(error).__name__+': '+str(error)
        finally:
            if failure:
                (output/'watchdog.json').write_text(json.dumps(dict(success=False,failure=failure,
                    native_seconds=NATIVE_SECONDS,group_seconds=GROUP_SECONDS,host_process_id=host_pid,
                    no_retry=True,no_host_restart=True),indent=2)+'\n',encoding='utf-8')
                # Exact captured handles only; never kill by process name.
                if process.poll() is None:process.terminate()
                if host_handle is not None:
                    import win32event
                    if win32event.WaitForSingleObject(host_handle,0)==win32event.WAIT_TIMEOUT:
                        win32api.TerminateProcess(host_handle,124)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
            if host_handle is not None:host_handle.Close()
    return 124 if failure else process.returncode


if __name__=='__main__':raise SystemExit(main())
