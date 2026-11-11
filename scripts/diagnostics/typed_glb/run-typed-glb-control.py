"""Review candidate only. Wrap the pinned baseline; change only its GLB call binding.

Default operation is a zero-GLB identity handshake. A separate --mode invoke run
is the one native call experiment, subject to the coordinator's prior review.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from zipfile import ZipFile
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge_control as bridge

BASELINE_SHA = '282d75cb4a4097dac4077bb7e70af68d8278c351880d0887ce8220ba46cd36d2'
ARCHIVE_SHA = '06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53'
HEAD = '70d8c9ecf3c02b099ca9c2cc64fe1880061cea44'


def load_baseline(path):
    path = Path(path).resolve()
    bridge.require(bridge.digest(path) == BASELINE_SHA, 'baseline driver changed')
    archive = path.parent / 'getter-source-70d8c9e.zip'
    source = path.parent / 'source-70d8c9e'
    bridge.require(bridge.digest(archive) == ARCHIVE_SHA, 'pinned source archive changed')
    with ZipFile(archive) as packed:
        for item in packed.infolist():
            name = Path(item.filename)
            bridge.require(not name.is_absolute() and '..' not in name.parts and '\\' not in item.filename,
                           'unsafe source archive path')
            if not item.is_dir():
                bridge.require((source / name).read_bytes() == packed.read(item), 'pinned extracted source differs: ' + item.filename)
    spec = importlib.util.spec_from_file_location('immutable_hidden_glb_baseline', path)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    bridge.require(baseline.HEAD == HEAD and baseline.SOURCE.resolve() == source.resolve(), 'baseline source identity differs')
    # Baseline BASE/SOURCE remain pinned above. Only the child entry point is redirected.
    baseline.__file__ = str(Path(__file__).resolve())
    return baseline


def install_call_control(baseline, helper, mode, provenance):
    original_run = baseline.module.harness.run
    def controlled_run(output, constants, visible, **kwargs):
        bridge.require(visible is False and kwargs['case_plan'] == [('part', 'front', False)], 'fixture/host plan differs')
        original_case = kwargs['case_runner']
        def case_runner(app, output, constants, plane, reverse, call, case, report, live, **case_kwargs):
            from swcli.hosts import windows_documents
            from swcli.hosts.native_trace import native_call
            original_save = windows_documents.save_as3
            attempts = []
            control = dict(provenance=provenance, mode=mode, binding_entries=0, producer={}, preparation_only=True,
                           ci_acceptance=False, public_acceptance=False)
            report['typed_glb_control'] = control
            report['native_call_worker_pid'] = os.getpid()
            def typed_save(document, output_name, *, receipt, stage='save-as'):
                if Path(output_name).suffix.upper() != '.GLB':
                    return original_save(document, output_name, receipt=receipt, stage=stage)
                bridge.require(stage == 'document-export' and not attempts, 'only one GLB document-export entry permitted')
                bridge.require(re.fullmatch(r'\.component-export\.[0-9a-f]{32}\.swcli\.GLB', Path(output_name).name)
                               and Path(output_name).parent == output, 'original GLB staging string differs')
                bridge.require(len(case.get('outputs', [])) == 3 and
                               [row['format'] for row in case['outputs']] == ['STL', '3MF', 'AMF']
                               and all(row['result'].get('ok') is True for row in case['outputs']), 'prior exports incomplete')
                attempts.append(output_name)
                control['binding_entries'] = len(attempts)
                receipt['save_attempted'] = False
                for key in ('api_saved', 'save_errors', 'save_warnings'):
                    receipt.pop(key, None)
                def invoke():
                    return bridge.invoke_existing(app, document, output_name, output/'component.SLDPRT',
                                                  case['source_sha256'], helper, output/'typed-glb', mode, control['producer'],
                                                  report['host']['process_id'])
                try:
                    # This Python trace names the external bridge, never a fictitious Python COM save.
                    result = native_call(stage, 'CSharpBridge.SaveAs3' if mode == 'invoke' else 'CSharpBridge.IdentityOnly', invoke)
                finally:
                    # Preserve a real native normal-return receipt even when a later bridge check failed.
                    r = control['producer'].get('helper_result') or control['producer'].get('helper_durable') or {}
                    if r.get('save_attempts') == 1:
                        receipt['save_attempted'] = True
                        for key in ('api_saved', 'save_errors', 'save_warnings'):
                            if r.get(key) is not None:
                                receipt[key] = r[key]
                if mode == 'identity':
                    control['identity_only_accepted'] = result.get('success') is True and result.get('save_attempts') == 0
                    raise RuntimeError('typed identity preflight finished at zero GLB saves; fixture stopped for review')
                return bridge.adapt_result(result, receipt)
            windows_documents.save_as3 = typed_save
            try:
                return original_case(app, output, constants, plane, reverse, call, case, report, live, **case_kwargs)
            finally:
                windows_documents.save_as3 = original_save
        kwargs['case_runner'] = case_runner
        return original_run(output, constants, visible, **kwargs)
    baseline.module.harness.run = controlled_run


def offline_audit(output, mode):
    """No COM. A native-success receipt still requires the original strict BIN parser."""
    report_path = output / 'report.json'
    if not report_path.exists():
        return dict(success=False, error='fixture report absent', mode=mode)
    report = json.loads(report_path.read_text(encoding='utf-8'))
    control = report.get('typed_glb_control', {})
    producer = control.get('producer', {})
    helper = producer.get('helper_result') or producer.get('helper_durable') or {}
    rows = []
    stderr = output / 'worker.stderr.log'
    if stderr.exists():
        for line in stderr.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('{'):
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    native = [row for row in rows if row.get('event') == 'swcli.native-call']
    counts = {fmt: sum(row.get('phase') == 'begin' and row.get('request_id') == 'local-export-'+fmt
                       and row.get('call') == 'IModelDocExtension.SaveAs3' for row in native)
              for fmt in ('STL', '3MF', 'AMF', 'GLB')}
    attempts = 0 if mode == 'identity' else 1
    helper_rows = []
    producer_path = None
    for candidate in output.rglob('typed-glb/producer.json'):
        bridge.require(producer_path is None, 'more than one typed bridge attempt')
        producer_path = candidate
    helper_trace_ok = False
    helper_file_ok = False
    if producer_path is not None:
        helper_path = producer_path.parent / 'helper.json'
        trace_path = producer_path.parent / 'helper-native.jsonl'
        helper_file_ok = (helper_path.exists() and trace_path.exists()
                          and bridge.digest(helper_path) == producer.get('helper_receipt_sha256')
                          and bridge.digest(trace_path) == producer.get('helper_trace_sha256')
                          and json.loads(helper_path.read_bytes()) == helper
                          and json.loads(producer_path.read_bytes()) == producer)
        if trace_path.exists():
            helper_rows = [json.loads(line) for line in trace_path.read_text(encoding='utf-8-sig').splitlines()]
            helper_trace_ok = (len(helper_rows) == 2*attempts and
                               all(row.get('event') == 'typed-glb.native-call' and row.get('helper_pid') == producer.get('helper_pid') for row in helper_rows)
                               and [row.get('phase') for row in helper_rows] == ([] if attempts == 0 else ['begin','end'])
                               and (not attempts or helper_rows[0].get('call') == 'IModelDocExtension.SaveAs3'))
    supervisor_path = output / 'local-supervisor.json'
    supervisor = json.loads(supervisor_path.read_text(encoding='utf-8')) if supervisor_path.exists() else {}
    owned_cleanup_ok = supervisor.get('pids_before') == [] and supervisor.get('pids_after') == []
    forbidden = [row for row in native if row.get('phase') == 'begin' and
                 ('SetUserPreference' in row.get('call','') or row.get('call') in
                  ('SldWorks.CommandInProgress.enter','SldWorks.CommandInProgress.restore',
                   'IModelDoc2.SaveAs','IModelDoc2.SaveAs2','IModelDoc2.SaveAs3'))]
    export_rows = [row for row in native if row.get('request_id','').startswith('local-export-')]
    worker_ok = bool(export_rows) and all(row.get('worker_pid') == report.get('native_call_worker_pid') for row in export_rows)
    bridge_rows = [row for row in export_rows if row.get('call') == ('CSharpBridge.IdentityOnly' if mode == 'identity' else 'CSharpBridge.SaveAs3')]
    bridge_trace_ok = [row.get('phase') for row in bridge_rows] == ['begin','end']
    accepted = (counts == {'STL': 1, '3MF': 1, 'AMF': 1, 'GLB': 0} and control.get('binding_entries') == 1
                and producer.get('success') is True and producer.get('marshal_cleanup_known') is True
                and helper.get('identity_accepted') is True and helper.get('save_attempts') == attempts
                and report.get('cleanup_errors') == [] and helper_file_ok and helper_trace_ok
                and owned_cleanup_ok and worker_ok and bridge_trace_ok and not forbidden)
    phases = ['handshake'] if mode == 'identity' else ['handshake','before-save','after-normal-return']
    identity_checks = helper.get('identity_checks', [])
    accepted = accepted and [row.get('phase') for row in identity_checks] == phases and all(
        row.get('document_iunknown_same') is True and row.get('extension_iunknown_same') is True
        and type(row.get('foreground_same')) is int and row['foreground_same'] == 1 for row in identity_checks)
    accepted = accepted and helper.get('before') == producer.get('expected')
    accepted = accepted and type(helper.get('save_attempts')) is int
    accepted = accepted and helper.get('helper_pid') == producer.get('helper_pid') and helper.get('python_worker_pid') == report.get('native_call_worker_pid')
    accepted = accepted and producer.get('python_worker_pid') == report.get('native_call_worker_pid')
    accepted = accepted and producer.get('expected', {}).get('pid') == report.get('host', {}).get('process_id')
    accepted = accepted and supervisor.get('report_sha256') == bridge.digest(report_path)
    if mode == 'identity':
        accepted = accepted and control.get('identity_only_accepted') is True
    else:
        accepted = accepted and report.get('success') is True and helper.get('post_state_accepted') is True
        arguments = helper.get('arguments') or {}
        accepted = accepted and arguments.get('name') == producer.get('output') and arguments.get('version') == 0 and arguments.get('options') == 1
        accepted = accepted and helper.get('after') == helper.get('before')
        accepted = accepted and helper.get('api_saved') is True and type(helper.get('save_errors')) is int and helper['save_errors'] == 0 and type(helper.get('save_warnings')) is int
        accepted = accepted and bool(report.get('cases', [{}])[0].get('glb_mesh'))
    return dict(success=bool(accepted), mode=mode, report_sha256=bridge.digest(report_path),
                helper_first_error=helper.get('first_error'), helper_hresult=helper.get('hresult'),
                python_modern_save_counts=counts, helper_save_attempts=helper.get('save_attempts'),
                python_worker_pid=report.get('native_call_worker_pid'), helper_pid=producer.get('helper_pid'),
                supervisor_launch_pid=supervisor.get('worker_pid'), helper_trace_accepted=helper_trace_ok,
                durable_helper_and_producer_accepted=helper_file_ok, owned_cleanup_accepted=owned_cleanup_ok,
                ci_acceptance=False, public_acceptance=False,
                identity_only_is_export_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'helper', 'output'):
        parser.add_argument('--'+name, default=os.environ.get('SWCLI_TYPED_'+name.upper()))
    parser.add_argument('--mode', choices=('identity', 'invoke'), default=os.environ.get('SWCLI_TYPED_MODE', 'identity'))
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    bridge.require(all((args.baseline, args.helper, args.output)), 'baseline/helper/new output paths required')
    for key in ('SWCLI_GLB_PLAIN_STAGING_CALIBRATION', 'SWCLI_IMAGE_QUALITY_CALIBRATION',
                'SWCLI_STL_CALIBRATION', 'SWCLI_STL_EXCLUSIVE_RUNNER'):
        bridge.require(not os.environ.get(key), 'other experimental control present: ' + key)
    baseline_path, helper, output = (Path(x).resolve() for x in (args.baseline, args.helper, args.output))
    build = bridge.verify_build(helper)
    baseline = load_baseline(baseline_path)
    bridge.require(output != baseline.OUT.resolve() and output.parent == baseline.BASE.resolve(),
                   'use a new sibling attempt directory beside the immutable baseline')
    baseline.OUT = output
    provenance = dict(baseline_sha256=BASELINE_SHA, archive_sha256=ARCHIVE_SHA, source_head=HEAD,
                      wrapper_sha256=bridge.digest(__file__), bridge_sha256=bridge.digest(bridge.__file__),
                      build=build, only_call_layer_changed=True, historical_closed_host_reused=False,
                      same_host_meaning='Python producer and C# consumer share the new attempt owned host/document')
    install_call_control(baseline, helper, args.mode, provenance)
    for key, value in (('BASELINE', baseline_path), ('HELPER', helper), ('OUTPUT', output), ('MODE', args.mode)):
        os.environ['SWCLI_TYPED_'+key] = str(value)
    status = baseline.main()
    if not args.worker and output.exists():
        audit = offline_audit(output, args.mode)
        with (output / 'typed-control-audit.json').open('x', encoding='utf-8') as file:
            json.dump(audit, file, indent=2)
            file.write('\n')
        # A zero-GLB handshake is intentionally not a passing fixture/export receipt.
        if args.mode == 'identity':
            return 0 if audit['success'] else 1
        return status if status else (0 if audit['success'] else 1)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
