import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts.native_trace import native_call, trace_native_request
from swcli.hosts.windows import _com_value


class NativeTraceTests(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.output = mock.patch('swcli.hosts.native_trace.sys.stderr', self.stream)
        self.output.start()
        self.addCleanup(self.output.stop)
        self.environment = mock.patch.dict(os.environ, {'SWCLI_TRACE_NATIVE_CALLS': '1'})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def records(self):
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]

    def test_toggle_is_explicit_and_off_by_default(self):
        for toggle in (None, '', '0', 'true'):
            with self.subTest(toggle=toggle):
                os.environ.pop('SWCLI_TRACE_NATIVE_CALLS', None)
                if toggle is not None:
                    os.environ['SWCLI_TRACE_NATIVE_CALLS'] = toggle
                function = mock.Mock(return_value=object())
                with trace_native_request('req-1', 'sketch.rectangle'):
                    result = native_call('create', 'CreateCenterRectangle', function)
                self.assertIs(result, function.return_value)
                function.assert_called_once_with()
                self.assertEqual(self.records(), [])

    def test_calls_outside_request_including_idle_probes_are_silent(self):
        self.assertEqual(_com_value(SimpleNamespace(RevisionNumber='33.5.0'), 'RevisionNumber'), '33.5.0')
        self.assertEqual(self.records(), [])

    def test_begin_is_flushed_before_native_invocation_and_end_after_return(self):
        stream = mock.Mock(spec=io.StringIO, wraps=self.stream)
        exact_result = object()

        def function():
            last = self.records()[-1]
            self.assertEqual(last['phase'], 'begin')
            self.assertEqual(last['call'], 'CreateCenterRectangle')
            self.assertEqual(stream.flush.call_count, 2)
            return exact_result

        with mock.patch('swcli.hosts.native_trace.sys.stderr', stream):
            with trace_native_request('req-1', 'sketch.rectangle'):
                self.assertIs(native_call('create', 'CreateCenterRectangle', function), exact_result)
        events = self.records()
        self.assertEqual([e['phase'] for e in events], ['begin', 'begin', 'end', 'end'])
        self.assertEqual([e['sequence'] for e in events], [0, 1, 1, 0])
        self.assertTrue(all(e['request_id'] == 'req-1' for e in events))
        self.assertTrue(all(e['operation'] == 'sketch.rectangle' for e in events))
        self.assertGreaterEqual(events[2]['duration_ms'], 0)
        self.assertEqual(stream.flush.call_count, 4)

    def test_native_exception_identity_is_retained_without_argument_or_result_leaks(self):
        failure = RuntimeError('private native failure text')
        function = mock.Mock(side_effect=failure)
        with self.assertRaises(RuntimeError) as caught:
            with trace_native_request('req-fail', 'sketch.rectangle'):
                native_call('sketch-enter', 'InsertSketch', function)
        self.assertIs(caught.exception, failure)
        self.assertEqual([e['phase'] for e in self.records()], ['begin', 'begin', 'error', 'error'])
        self.assertEqual(self.records()[2]['exception_type'], 'RuntimeError')
        self.assertNotIn('private native failure text', self.stream.getvalue())
        native_call('after', 'outside', lambda: None)
        self.assertEqual(len(self.records()), 4)

    def test_baseexception_is_not_swallowed_and_context_resets(self):
        with self.assertRaises(KeyboardInterrupt):
            with trace_native_request('req-fail', 'sketch.rectangle'):
                native_call('create', 'CreateCenterRectangle', mock.Mock(side_effect=KeyboardInterrupt))
        self.assertEqual(self.records()[-1]['phase'], 'error')
        native_call('after', 'outside', lambda: None)
        self.assertEqual(len(self.records()), 4)

    def test_nested_calls_have_distinct_matching_sequence_numbers(self):
        with trace_native_request('req-1', 'sketch.rectangle'):
            native_call('verify', 'geometry', lambda: _com_value(SimpleNamespace(X=1), 'X'))
        events = self.records()
        self.assertEqual([e['sequence'] for e in events], [0, 1, 2, 2, 1, 0])
        self.assertEqual(events[2]['call'], 'X')

    def test_nested_request_and_error_restore_parent_context(self):
        with trace_native_request('outer', 'sketch.rectangle'):
            try:
                with trace_native_request('inner', 'sketch.circle'):
                    raise ValueError('test')
            except ValueError:
                pass
            native_call('create', 'rectangle', lambda: None)
        events = self.records()
        self.assertEqual(events[-3]['request_id'], 'outer')
        self.assertEqual(events[-3]['sequence'], 1)

    def test_broken_diagnostic_stream_does_not_change_native_return_or_exception(self):
        for member in ('write', 'flush'):
            with self.subTest(member=member):
                stream = mock.Mock(spec=io.StringIO)
                getattr(stream, member).side_effect = OSError('log unavailable')
                with mock.patch('swcli.hosts.native_trace.sys.stderr', stream):
                    with trace_native_request('req-1', 'sketch.rectangle'):
                        self.assertEqual(native_call('create', 'rectangle', lambda: 7), 7)
                    failure = ValueError('native failure')
                    with self.assertRaises(ValueError) as caught:
                        with trace_native_request('req-2', 'sketch.rectangle'):
                            native_call('create', 'rectangle', mock.Mock(side_effect=failure))
                    self.assertIs(caught.exception, failure)

    def test_com_property_method_and_dispatch_objects_keep_existing_binding_semantics(self):
        class Dispatch:
            _oleobj_ = object()

            def __call__(self):
                raise AssertionError('must not invoke an IDispatch property')

        dispatch = Dispatch()
        obj = SimpleNamespace(property=8, method=lambda: 9, dispatch=dispatch)
        with trace_native_request('req-1', 'sketch.rectangle'):
            self.assertEqual(_com_value(obj, 'property'), 8)
            self.assertEqual(_com_value(obj, 'method'), 9)
            self.assertIs(_com_value(obj, 'dispatch'), dispatch)
        self.assertEqual([e['call'] for e in self.records() if e['stage'] == 'read' and e['phase'] == 'begin'],
                         ['property', 'method', 'dispatch'])


if __name__ == '__main__':
    unittest.main()
