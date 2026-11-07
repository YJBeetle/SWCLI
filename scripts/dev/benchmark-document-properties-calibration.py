"""Portable serialization/count microbenchmark, never Windows native evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import tempfile
import time
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('calibrate-document-properties.py')
spec = importlib.util.spec_from_file_location('_docprops_benchmark', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def benchmark(calls, rows):
    results = []
    for mode in ('forced-precall-serialization', 'revision-checkpoint'):
        with tempfile.TemporaryDirectory(prefix='swcli-report-bench-') as folder:
            c = module.Calibration.__new__(module.Calibration)
            c.output = Path(folder)
            c.started, c.cleanup_mode = time.monotonic(), False
            c.event = lambda row: None  # isolate report CPU; no trace/native/disk timing claim
            c.report = {'scope': 'portable synthetic report', 'reads': [
                {'value': 'x' * 128, 'nested': {'stamp': i, 'state': [1, i, False, 'Default']}}
                for i in range(rows)]}
            c.persist()
            original_bytes = (c.output / 'report.json').read_bytes()
            if mode == 'forced-precall-serialization':
                c.checkpoint = c.persist  # previous pre-native serialization behavior
            started = time.perf_counter()
            with patch.object(module.json, 'dumps', wraps=module.json.dumps) as dumps:
                for _ in range(calls):
                    assert c.call('synthetic-read', lambda: 7) == 7
                serializations = dumps.call_count
            elapsed = time.perf_counter() - started
            assert (c.output / 'report.json').read_bytes() == original_bytes
            assert serializations == (calls if mode == 'forced-precall-serialization' else 0)
            results.append({'mode': mode, 'calls': calls, 'report_rows': rows,
                            'report_bytes': len(original_bytes), 'report_json_dumps_calls': serializations,
                            'wall_seconds': elapsed, 'unchanged_report_sha256': hashlib.sha256(original_bytes).hexdigest()})
    return {'scope': 'portable report CPU/count microbenchmark; trace fsync omitted; no COM',
            'full_acceptance_eligible': False, 'windows_speedup_established': False,
            'python': platform.python_version(), 'platform': platform.platform(),
            'calibrator_sha256': hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
            'identity_count_regression': {'four_distinct_stable_documents': {'previous': 16, 'current': 10},
                                          'proof': 'portable permutations/fault tests, fresh native-identity simulation'},
            'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--calls', type=int, default=250)
    parser.add_argument('--rows', type=int, default=2000)
    args = parser.parse_args()
    if args.calls <= 0 or args.rows <= 0:
        parser.error('positive calls/rows required')
    result = benchmark(args.calls, args.rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
