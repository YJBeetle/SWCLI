"""Portable faults/count regressions. No test supplies Windows native acceptance."""
import ast
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_document_properties_calibration import Calibration, Doc, fixture, module, SOURCE


def durable_fixture(folder):
    c = fixture()
    c.output = Path(folder)
    del c.persist, c.call, c.read_font
    c.events = []
    c.event = c.events.append
    c.persist()
    return c


class ReportRevisionFaults(unittest.TestCase):
    def test_unchanged_native_reads_do_not_walk_or_serialize_report(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            c.report['large_history'] = [{'value': 'x' * 128} for _ in range(10000)]
            c.report_changed()
            c.persist()
            with patch.object(module.json, 'dumps', wraps=module.json.dumps) as dumps:
                for _ in range(250):
                    self.assertEqual(c.call('read', lambda: 7), 7)
                self.assertEqual(dumps.call_count, 0)
            self.assertEqual(len(c.events), 500)  # begin/terminal still emitted

    def test_nested_alias_and_setdefault_intent_are_durable_before_native(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            row = {'observations': [], 'mutation': {'attempted': False}}
            c.report.setdefault('cases', []).append(row)
            c.report_changed()
            c.call('first-read', lambda: None)
            row['observations'].append({'nested': {'value': 42}})
            row['mutation'].update(attempted=True, may_have_changed=True)
            c.report_changed()
            expected = copy.deepcopy(c.report)
            def native():
                self.assertEqual(json.loads((c.output / 'report.json').read_text()), expected)
            c.call('setter-once', native)
            self.assertIs(c.report['cases'][0], row)

    def test_failed_replace_does_not_advance_revision_or_enter_native(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            previous_revision, previous_bytes = c._persisted_report_revision, c._persisted_report_bytes
            c.report['intent'] = {'attempted': True}
            c.report_changed()
            entered = []
            with patch.object(Path, 'replace', side_effect=PermissionError('replace failed')) as replace:
                with self.assertRaisesRegex(PermissionError, 'replace failed'):
                    c.call('set', lambda: entered.append(True))
                self.assertEqual(replace.call_count, 1)
            self.assertEqual(entered, [])
            self.assertEqual(c._persisted_report_revision, previous_revision)
            self.assertEqual(c._persisted_report_bytes, previous_bytes)
            self.assertFalse(c.events[-1]['native_started'])
            self.assertIsNone(c.events[-1]['native_seconds'])
            c.checkpoint()  # recover report I/O only; never repeat native
            saved = json.loads((c.output / 'report.json').read_text())
            self.assertEqual(saved['first_call_failure']['message'], 'replace failed')

    def test_native_failure_and_secondary_io_preserve_first_cause(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            entered = []
            def fail():
                entered.append(True)
                raise ValueError('native first cause')
            with patch.object(Path, 'replace', side_effect=OSError('secondary I/O')):
                with self.assertRaisesRegex(ValueError, 'native first cause'):
                    c.call('setter', fail)
            first = copy.deepcopy(c.report['first_call_failure'])
            self.assertEqual(first['report_persist_failure']['message'], 'secondary I/O')
            self.assertTrue(first['native_started'])
            self.assertFalse(first['native_completed'])
            c.call('cleanup-read', lambda: None)
            self.assertEqual(c.report['first_call_failure'], first)
            self.assertEqual(entered, [True])
            self.assertEqual(json.loads((c.output / 'report.json').read_text())['first_call_failure'], first)

    def test_font_reader_aliases_flush_previous_observation_before_next_getter(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            doc = Doc()
            original = c.com_value
            observed = []
            def get(obj, name):
                if name in module.FONT_MEMBERS:
                    saved = json.loads((c.output / 'report.json').read_text())['reads']['font']
                    self.assertEqual(list(saved), observed)
                    observed.append(name)
                    if name == 'Italic':
                        raise ValueError('getter fault')
                return original(obj, name)
            c.com_value = get
            with self.assertRaisesRegex(ValueError, 'getter fault'):
                c.read_font(doc, 'font')
            saved = json.loads((c.output / 'report.json').read_text())
            self.assertEqual(list(saved['reads']['font']), observed[:-1])
            self.assertEqual(saved['first_call_failure']['message'], 'getter fault')

    def test_rhs_native_checkpoint_cannot_hide_subsequent_report_assignment(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            row = c.report.setdefault('row', {})
            c.report_changed()
            row['value'] = c.call('getter', lambda: 42)
            c.report_changed()  # invalidation belongs AFTER the RHS/native call
            c.call('next', lambda: self.assertEqual(json.loads((c.output / 'report.json').read_text())['row']['value'], 42))

    def test_explicit_persist_keeps_legacy_forced_observation_and_equal_bytes_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            c.report['external-diagnostic'] = 42  # explicit persist still sees it
            c.persist()
            c.report_changed()  # same bytes, new revision
            with patch.object(Path, 'replace', side_effect=AssertionError('redundant replace')):
                c.checkpoint()
            self.assertEqual(c._persisted_report_revision, c._report_revision)

    def test_trace_begin_and_terminal_still_fsync_for_cached_report(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            with (Path(folder) / 'trace.jsonl').open('w') as c.trace:
                del c.event
                with patch.object(module.os, 'fsync', wraps=module.os.fsync) as fsync:
                    c.call('read', lambda: 42)
                    self.assertEqual(fsync.call_count, 2)

    def test_mutation_sites_invalidate_after_statement_including_aliases(self):
        # Conservative source audit: all subscript writes and container mutators
        # in instance methods invalidate, even local containers that may alias
        # evidence. This catches future unmarked nested/alias edits without
        # replacing plain dict/list objects or losing caller row aliases.
        source = SOURCE.read_text()
        lines = source.splitlines()
        tree = ast.parse(source)
        mutators = {'append', 'extend', 'update', 'setdefault', 'pop', 'remove', 'clear',
                    'insert', 'sort', 'reverse', 'popitem', 'difference_update',
                    'intersection_update', 'symmetric_difference_update'}
        count = 0
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef) or cls.name != 'Calibration':
                continue
            for method in cls.body:
                if not isinstance(method, ast.FunctionDef) or not method.args.args or method.args.args[0].arg != 'self':
                    continue
                for statement in ast.walk(method):
                    if not isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Delete)):
                        continue
                    targets = getattr(statement, 'targets', [getattr(statement, 'target', None)])
                    write = any(isinstance(n, ast.Subscript) or
                                (isinstance(n, ast.Attribute) and ast.unparse(n) == 'self.report')
                                for t in targets if t is not None for n in ast.walk(t))
                    mutate = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                 and n.func.attr in mutators for n in ast.walk(statement))
                    if method.name == 'identity_catalog' and ast.get_source_segment(source, statement) == 'unmatched.pop(match)':
                        continue  # fresh local matching pool, never a report alias
                    if write or mutate:
                        count += 1
                        self.assertEqual(lines[statement.end_lineno].strip(), 'self.report_changed()',
                                         f'{method.name}:{statement.lineno} must invalidate after mutation')
        self.assertGreater(count, 100)


class NativeIdentityBijection(unittest.TestCase):
    def catalog(self, expected, actual):
        c = fixture()
        c.app.docs = list(actual)
        calls = []
        def native_same(app, first, second):
            calls.append((first.token, second.token))
            return first.token == second.token  # fresh Python proxies, native identity only
        c.native_same = native_same
        return c, calls

    @staticmethod
    def proxy(token):
        from types import SimpleNamespace
        return SimpleNamespace(token=token, title='same-title')

    def test_every_catalog_permutation_is_bijective_without_title_or_python_identity(self):
        expected = [self.proxy(i) for i in range(4)]
        for order in itertools.permutations(range(4)):
            actual = [self.proxy(i) for i in order]
            c, calls = self.catalog(expected, actual)
            self.assertEqual(c.identity_catalog(expected, 'fresh'), actual)
            self.assertLessEqual(len(calls), 16)

    def test_stable_four_object_catalog_uses_ten_comparisons_and_refreshes(self):
        expected = [self.proxy(i) for i in range(4)]
        c, calls = self.catalog(expected, [self.proxy(i) for i in range(4)])
        c.identity_catalog(expected, 'first')
        self.assertEqual(len(calls), 10)  # 6 expected-distinct + 4 consuming matches
        c.app.docs[-1] = self.proxy(99)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            c.identity_catalog(expected, 'second')
        self.assertGreater(len(calls), 10)

    def test_duplicate_expected_or_actual_missing_and_foreign_are_rejected(self):
        for expected_tokens, actual_tokens, error in (
            ([0, 0], [0, 1], 'duplicate expected'),
            ([0, 0], [0, 0], 'duplicate expected'),
            ([0, 1], [0, 0], 'identity changed'),
            ([0, 1], [1, 1], 'identity changed'),
            ([0, 1], [0, 2], 'identity changed'),
            ([0, 1], [0], 'count'),
            ([0], [0, 1], 'count'),
        ):
            with self.subTest(expected=expected_tokens, actual=actual_tokens):
                expected, actual = ([self.proxy(i) for i in tokens] for tokens in (expected_tokens, actual_tokens))
                c, calls = self.catalog(expected, actual)
                with self.assertRaisesRegex(RuntimeError, error):
                    c.identity_catalog(expected, 'fault')

    def test_count_disagreement_and_native_identity_error_fail_closed(self):
        expected = [self.proxy(0)]
        c, _ = self.catalog(expected, [self.proxy(0)])
        c.app.GetDocumentCount = lambda: 2
        with self.assertRaisesRegex(RuntimeError, 'count'):
            c.identity_catalog(expected, 'bad-count')
        c.app.GetDocumentCount = lambda: 1
        c.native_same = lambda *args: (_ for _ in ()).throw(ValueError('IsSame fault'))
        with self.assertRaisesRegex(ValueError, 'IsSame fault'):
            c.identity_catalog(expected, 'error')


class SplitTiming(unittest.TestCase):
    def test_native_body_time_is_separate_and_wrapper_budget_stays_conservative(self):
        with tempfile.TemporaryDirectory() as folder:
            c = durable_fixture(folder)
            clock = [0.0]
            c.started = 0
            c.event = lambda row: (c.events.append(row), clock.__setitem__(0, clock[0] + 2))
            c.checkpoint = lambda: clock.__setitem__(0, clock[0] + 7)
            def native():
                clock[0] += 3
                return 42
            with patch.object(module.time, 'monotonic', side_effect=lambda: clock[0]):
                self.assertEqual(c.call('read', native), 42)
            row = c.events[-1]
            self.assertEqual(row['begin_trace_seconds'], 2)
            self.assertEqual(row['checkpoint_seconds'], 7)
            self.assertEqual(row['native_seconds'], 3)
            self.assertEqual(row['elapsed_seconds'], 12)
            self.assertTrue(row['native_completed'])
            c.events.clear()
            clock[0] = 0
            c.checkpoint = lambda: clock.__setitem__(0, clock[0] + 598)
            with patch.object(module.time, 'monotonic', side_effect=lambda: clock[0]):
                with self.assertRaisesRegex(RuntimeError, '600-second'):
                    c.call('slow-wrapper', native)
            self.assertEqual(c.events[-1]['native_seconds'], 3)
            self.assertGreaterEqual(c.events[-1]['elapsed_seconds'], 600)
