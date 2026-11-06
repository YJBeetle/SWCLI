"""Branch-only owned Windows standards calibration; internal evidence, never acceptance.

One new owned host; one standards group, 36 planned transitions, 600/1800s.
The hardened driver owns its worker. The STA owner pumps COM while it waits.
No local VM, arbitrary host attachment, retries, rollback or whitelist edits.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BRANCH_REF = 'refs/heads/codex/docprops-calibration-performance'


def checked(condition, message):
    if not condition:
        raise RuntimeError(message)


def source_context(expected_head, environ=None, checkout_head=None):
    env = os.environ if environ is None else environ
    checked(env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'manual dispatch required')
    checked(env.get('GITHUB_REPOSITORY') == 'YJBeetle/SWCLI', 'unexpected repository')
    checked(env.get('GITHUB_REF') == BRANCH_REF, 'dedicated branch required')
    checked(re.fullmatch('[0-9a-f]{40}', expected_head or '') is not None, 'exact expected head required')
    actual = (subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
              if checkout_head is None else checkout_head)
    checked(actual == expected_head == env.get('GITHUB_SHA'), 'dispatch/checkout/expected head mismatch')
    return {'source_head': actual, 'event': env['GITHUB_EVENT_NAME'], 'ref': env['GITHUB_REF'],
            'run_id': env.get('GITHUB_RUN_ID'), 'run_attempt': env.get('GITHUB_RUN_ATTEMPT'),
            'full_acceptance_eligible': False, 'native_timeout_seconds': 600, 'group_timeout_seconds': 1800,
            'group_design': 'one group: part/assembly/drawing, 12 transitions each, 36 total'}


def load_script(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_driver_with_pump(driver, args, pump):
    # driver.run uses no COM. All host COM ownership stays on the harness STA.
    # No second watchdog/timeout policy can kill or authorize an unrelated PID.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(driver.run, args)
        while not future.done():
            pump()
            time.sleep(.02)
        return future.result()


@contextmanager
def owned_interface_packet(pythoncom, app, evidence, call):
    # CoMarshalInterface(MSHCTX_LOCAL, TABLESTRONG): same-machine process
    # transfer. The original STA releases the strong table packet exactly once,
    # including authorization failure or worker termination. Not a ROT fallback.
    stream = pythoncom.CreateStreamOnHGlobal()
    marshaled = primary_failed = False
    evidence.update(marshaled=False, released=False)
    try:
        call('owned-interface.CoMarshalInterface', lambda: pythoncom.CoMarshalInterface(
            stream, pythoncom.IID_IDispatch, app._oleobj_, pythoncom.MSHCTX_LOCAL,
            pythoncom.MSHLFLAGS_TABLESTRONG))
        marshaled = evidence['marshaled'] = True
        stream.Seek(0, 0)
        packet = stream.Read(65537)
        checked(type(packet) is bytes and 0 < len(packet) <= 65536, 'owned interface packet exceeds bound')
        evidence['transfer_bytes'] = len(packet)  # never retain bytes or their repr
        yield packet
    except BaseException:
        primary_failed = True
        raise
    finally:
        if marshaled:
            try:
                stream.Seek(0, 0)
                call('owned-interface.CoReleaseMarshalData', lambda: pythoncom.CoReleaseMarshalData(stream))
                evidence['released'] = True
            except BaseException as error:
                evidence['release_failure'] = {'type': type(error).__name__, 'message': str(error)}
                if not primary_failed:
                    raise


def verify_complete_report(report, driver, pid):
    checked(driver.get('success') is True and driver.get('worker_authorized') is True,
            'hardened worker did not complete successfully')
    checked(driver.get('host_termination_attempted') is False
            and driver.get('automatic_retry') is False and driver.get('automatic_rollback') is False,
            'unexpected driver lifecycle policy')
    binding = report.get('owned_interface_binding', {})
    checked(binding.get('source') == 'parent-owned-COM-marshal'
            and binding.get('unmarshal_attempted') is True and binding.get('identity_verified') is True
            and driver.get('owned_interface_transfer_completed') is True, 'owned interface binding/transfer incomplete')
    checked(report.get('success') is True and report.get('cleanup_errors') == []
            and report.get('remaining_registered_test_documents') == [], 'incomplete native report/cleanup')
    checked(report.get('actual_attach_pid') == pid == driver.get('attach_pid')
            and report.get('manual_host_still_running') is True, 'owned host identity changed')
    checked(report.get('native_timeout_seconds') == driver.get('native_timeout_seconds') == 600
            and report.get('group_timeout_seconds') == driver.get('group_timeout_seconds') == 1800,
            'calibration budgets changed')
    checked(report.get('stage') == 'standards' and report.get('full_acceptance_eligible') is False,
            'unexpected evidence scope')
    cases = report.get('cases', [])
    checked([case.get('kind') for case in cases] == ['part', 'assembly', 'drawing'], 'three ordered document types required')
    transitions = 0
    for case in cases:
        checked(case.get('success') is True and type(case.get('successful_planned_transitions')) is int and case['successful_planned_transitions'] == 12
                and len(case.get('writes', [])) == 12, 'incomplete per-kind transitions')
        for index, row in enumerate(case['writes'], 1):
            checked(row.get('success') is True and type(row.get('plan_index')) is int and row['plan_index'] == index
                    and type(row.get('native_setter_calls')) is int and row['native_setter_calls'] == 1 and row.get('native_return') is True,
                    'setter failure, repetition or incomplete transition')
            profiles = [row.get(key) for key in ('final', 'saved_profile', 'readonly_profile')]
            checked(row.get('saved') and all(type(profile) is dict and profile for profile in profiles)
                    and len({json.dumps(profile, sort_keys=True, allow_nan=False) for profile in profiles}) == 1,
                    'save/readonly fixed profile persistence incomplete')
            transitions += 1
    checked(transitions == 36, 'full 36-transition coverage missing')
    return transitions


def run_owned(output, swconst, drawing_template, context):
    import pythoncom
    from swcli.hosts.windows import _com_value
    harness = load_script('_docprops_owned_harness', 'scripts/ci/verify-through-all-calibration.py')
    driver = load_script('_docprops_safe_driver', 'scripts/dev/run-document-properties-calibration.py')

    def case_runner(app, directory, constants, plane, reverse, call, case, report, live, *, profile_kind):
        # acquire_resident_app + checked(owned) + captured process handle have
        # already succeeded. UserControl is set ONLY on that new owned host,
        # before the calibrator takes its immutable baseline. Official API:
        # https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControl.html
        pid = report['host']['process_id']
        call('owned-host-user-control', lambda: setattr(app, 'UserControl', True))
        checked(_com_value(app, 'UserControl') is True and _com_value(app, 'GetProcessID') == pid,
                'owned host control/identity setup failed')
        binding = case['owned_interface'] = {}
        with owned_interface_packet(pythoncom, app, binding, call) as packet:
            child_output = output / 'standards-36'
            args = SimpleNamespace(output=str(child_output), source_root=str(ROOT),
                                   script=str(ROOT / 'scripts/dev/calibrate-document-properties.py'),
                                   python=driver.default_python(), attach_pid=pid, stage='standards',
                                   swconst=str(swconst), drawing_template=str(drawing_template),
                                   font_typeface=None, isolated_host=True, owned_interface_data=packet)
            code = call('standards-36-driver', lambda: run_driver_with_pump(driver, args, pythoncom.PumpWaitingMessages))
            receipt = json.loads((output / 'standards-36-driver/driver.json').read_text(encoding='utf-8'))
            case.update(context=context, driver=receipt, group='standards-36', expected_transitions=36)
            checked(code == 0, 'standards group failed; retain original driver/report/trace; no retry')
            native_report = json.loads((child_output / 'report.json').read_text(encoding='utf-8'))
            case['completed_transitions'] = verify_complete_report(native_report, receipt, pid)

        case['success'] = True

    return harness.run(output, swconst, True, case_runner=case_runner,
                       case_plan=[('standards-36', 'front', False)],
                       diagnostic_case='document-properties-performance-owned-standards-36')


def manifest(output, context):
    files = []
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'manifest.json':
            files.append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    sources = {}
    for name in ('scripts/dev/calibrate-document-properties.py', 'scripts/dev/run-document-properties-calibration.py',
                 'scripts/ci/verify-document-properties-calibration.py', 'scripts/ci/verify-through-all-calibration.py'):
        sources[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(json.dumps({**context, 'sources': sources, 'files': files}, indent=2) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--check-context', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--swconst', type=Path)
    parser.add_argument('--drawing-template', type=Path)
    args = parser.parse_args(argv)
    context = source_context(args.expected_head)
    if args.check_context:
        print(json.dumps(context))
        return 0
    checked(args.output_dir is not None and args.swconst is not None and args.drawing_template is not None,
            'output, installed official TLB and explicit drawing template required')
    output = args.output_dir.resolve()
    workspace = Path(r'C:\Workspace').resolve()
    checked(workspace in output.parents and output != workspace, 'output must be below C:\\Workspace')
    checked(args.swconst.is_file() and args.drawing_template.is_file(), 'installed official inputs missing')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    try:
        return run_owned(output, args.swconst.resolve(), args.drawing_template.resolve(), context)
    finally:
        manifest(output, context)


if __name__ == '__main__':
    raise SystemExit(main())
