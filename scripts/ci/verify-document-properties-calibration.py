"""Branch-only owned Windows standards calibration; internal evidence, never acceptance.

One new owned host; optional separate GB fixture group then original standards
group of 36 planned transitions. Each group retains its own 600/1800s limits.
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
            'group_design': 'optional independent GB fixture preparation, then one original 36-transition group; each group 1800s'}


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


def verify_group_report(report, driver, pid, stage):
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
    checked(report.get('stage') == stage and report.get('full_acceptance_eligible') is False,
            'unexpected evidence scope')


def verify_complete_report(report, driver, pid):
    verify_group_report(report, driver, pid, 'standards')
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


def verify_prepared_report(report, driver, pid):
    verify_group_report(report, driver, pid, 'standards-prepare')
    cases = report.get('cases', [])
    checked([case.get('kind') for case in cases] == ['part', 'assembly', 'drawing'],
            'three ordered fixture kinds required')
    inputs = report.get('prepared_native_inputs', {})
    checked(set(inputs) == {'part', 'assembly', 'drawing'}, 'three prepared inputs required')
    setters = 0
    for case in cases:
        checked(case.get('success') is True and len(case.get('writes', [])) == 1, 'fixture preparation incomplete')
        row = case['writes'][0]
        source, target = row.get('source'), row.get('target')
        count = row.get('native_setter_calls')
        checked(type(source) is int and 1 <= source <= 7 and type(target) is int and target == 7
                and row.get('target_name') == 'gb' and type(count) is int,
                'fixture named source/GB target differs')
        checked(row.get('success') is True and row.get('plan_index') == 1
                and ((source != 7 and count == 1 and row.get('native_return') is True)
                     or (source == 7 and count == 0 and row.get('native_return') is None
                         and row.get('mutation') == {'attempted': False, 'may_have_changed': False})),
                'fixture setter failed, repeated or unexpected no-op mutation')
        profiles = [row.get(key) for key in ('final', 'saved_profile', 'readonly_profile')]
        checked(all(type(profile) is dict and profile and profile.get('standard') == {'value': 'gb', 'native_value': 7}
                    for profile in profiles)
                and len({json.dumps(profile, sort_keys=True, allow_nan=False) for profile in profiles}) == 1,
                'prepared GB save/readonly profile differs')
        item = inputs[case['kind']]
        checked(item.get('kind') == case['kind'] and item.get('path') == row.get('saved', {}).get('path')
                and item.get('sha256') == row.get('saved', {}).get('sha256')
                and re.fullmatch('[0-9a-f]{64}', item.get('sha256', '')) is not None
                and item.get('profile') == profiles[-1], 'prepared input lineage differs')
        if case['kind'] == 'part':
            checked(case.get('geometry_initial') is not None
                    and item.get('geometry_initial') == case['geometry_initial']
                    and row.get('saved_geometry') is not None and row.get('reopened_geometry') is not None,
                    'prepared part geometry evidence missing')
        setters += count
    return inputs, setters


def run_groups(output, swconst, drawing_template, context, pid, packet, driver, pump, call, case,
               *, part_template, assembly_template, prepare_gb_inputs):
    def group(name, stage, prepared_inputs=None):
        child_output = output / name
        args = SimpleNamespace(output=str(child_output), source_root=str(ROOT),
            script=str(ROOT / 'scripts/dev/calibrate-document-properties.py'),
            python=driver.default_python(), attach_pid=pid, stage=stage, swconst=str(swconst),
            drawing_template=str(drawing_template), part_template=str(part_template) if part_template else None,
            assembly_template=str(assembly_template) if assembly_template else None,
            prepared_inputs=str(prepared_inputs) if prepared_inputs else None,
            font_typeface=None, isolated_host=True, owned_interface_data=packet)
        code = call(name + '-driver', lambda: run_driver_with_pump(driver, args, pump))
        receipt = json.loads((output / (name + '-driver') / 'driver.json').read_text(encoding='utf-8'))
        case.setdefault('groups', []).append({'group': name, 'driver': receipt, 'context': context})
        checked(code == 0, name + ' failed; retain original driver/report/trace; no retry')
        native_report = json.loads((child_output / 'report.json').read_text(encoding='utf-8'))
        return native_report, receipt

    prepared_path = None
    if prepare_gb_inputs:
        preparation, receipt = group('standards-prepare', 'standards-prepare')
        inputs, setters = verify_prepared_report(preparation, receipt, pid)
        for item in inputs.values():
            path = Path(item['path'])
            checked(path.is_file() and not path.is_symlink()
                    and (output / 'standards-prepare').resolve() in path.resolve().parents
                    and hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'],
                    'prepared native input bytes/path differ')
        prepared_path = output / 'prepared-inputs.json'
        prepared_path.write_text(json.dumps({'format': 'owned-prepared-gb-v1', 'attach_pid': pid,
            'script_sha256': preparation['script_sha256'], 'inputs': inputs}, indent=2) + '\n', encoding='utf-8')
        case['fixture_preparation_setters'] = setters
    native_report, receipt = group('standards-36', 'standards', prepared_path)
    case['completed_transitions'] = verify_complete_report(native_report, receipt, pid)
    case['group'] = 'standards-36'
    case['expected_transitions'] = 36
    case['driver'] = receipt
    case['context'] = context


def run_owned(output, swconst, drawing_template, context, *, part_template, assembly_template, prepare_gb_inputs=False):
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
            run_groups(output, swconst, drawing_template, context, pid, packet, driver,
                       pythoncom.PumpWaitingMessages, call, case, part_template=part_template,
                       assembly_template=assembly_template, prepare_gb_inputs=prepare_gb_inputs)

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
    parser.add_argument('--part-template', type=Path)
    parser.add_argument('--assembly-template', type=Path)
    parser.add_argument('--prepare-gb-inputs', action='store_true')
    args = parser.parse_args(argv)
    context = source_context(args.expected_head)
    if args.check_context:
        print(json.dumps(context))
        return 0
    checked(all(value is not None for value in (args.output_dir, args.swconst, args.drawing_template))
            and (args.prepare_gb_inputs or (args.part_template is not None and args.assembly_template is not None)),
            'output, installed TLB, drawing and explicit GB inputs or separate preparation required')
    context['fixture_preparation_required'] = args.prepare_gb_inputs
    output = args.output_dir.resolve()
    workspace = Path(r'C:\Workspace').resolve()
    checked(workspace in output.parents and output != workspace, 'output must be below C:\\Workspace')
    checked(all(path.is_file() and not path.is_symlink() for path in (args.swconst, args.drawing_template, args.part_template, args.assembly_template) if path is not None), 'installed official inputs missing')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    (output / 'template-selection.json').write_text(json.dumps({'success': True, 'source': 'separate-owned-GB-preparation' if args.prepare_gb_inputs else 'explicit-installed-GB',
        'part': str(args.part_template.resolve()) if args.part_template else None, 'assembly': str(args.assembly_template.resolve()) if args.assembly_template else None,
        'drawing': str(args.drawing_template.resolve())}, indent=2)+'\n', encoding='utf-8')
    try:
        return run_owned(output, args.swconst.resolve(), args.drawing_template.resolve(), context,
                         part_template=args.part_template.resolve() if args.part_template else None,
                         assembly_template=args.assembly_template.resolve() if args.assembly_template else None,
                         prepare_gb_inputs=args.prepare_gb_inputs)
    finally:
        manifest(output, context)


if __name__ == '__main__':
    raise SystemExit(main())
