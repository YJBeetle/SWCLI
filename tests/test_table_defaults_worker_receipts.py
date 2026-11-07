"""Portable real handler/adapter/worker fault injection without a CAD process."""

from copy import deepcopy
import unittest
from unittest import mock

from swcli.daemon import operations, server
from tests import test_document_tables as fixtures


class TableWorkerReceiptTests(unittest.TestCase):
    def test_success_and_first_business_failure_retain_partial_receipts_through_worker(self):
        for business_failure in (False, True):
            with self.subTest(business_failure=business_failure):
                fixture = fixtures.DocumentTableTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                fixture.app.GetProcessID = lambda: 1234
                fixture.app.CommandInProgress = False
                before = fixture.read()['options']
                after = deepcopy(before)
                after['bom.box_border'] = dict(value='thick', native_value=2)
                receipt = dict(ok=not business_failure, action='document.table-option-set', field='bom.box_border',
                               before=before, mutation=dict(attempted=True, may_have_changed=True), native_returned=not business_failure)
                if business_failure:
                    receipt['error'] = dict(type='NativeTableFailure', message='first native business failure')
                else:
                    receipt.update(changed=True, options=after)
                state = dict(adapter_calls=0, descriptor_calls_after_adapter=0)
                original_describe = fixture.documents.describe
                def describe(*args, **kwargs):
                    if state['adapter_calls']:
                        state['descriptor_calls_after_adapter'] += 1
                        raise RuntimeError('post-adapter descriptor failed')
                    return original_describe(*args, **kwargs)
                def adapter(**kwargs):
                    state['adapter_calls'] += 1
                    return receipt
                request = dict(request_id='table-receipt-worker', operation='document.table-option-set',
                    parameters=dict(field='bom.box_border', value='thick', expected_options=before),
                    session_id='writer', document_id=fixture.entry.document_id, expected_update_stamp=7,
                    lease_id=fixture.lease, timeout_ms=600000)
                pythoncom, com_client = mock.Mock(), mock.Mock()
                responses, lifecycle = mock.Mock(), mock.Mock()
                with mock.patch.dict('sys.modules', {'pythoncom': pythoncom,
                        'win32com': mock.Mock(client=com_client), 'win32com.client': com_client}), \
                     mock.patch.object(server, 'acquire_resident_app', return_value=(fixture.app, True)) as acquire, \
                     mock.patch.object(server, 'wait_windows_host_ready', return_value=0), \
                     mock.patch.object(server, 'DocumentRegistry', return_value=fixture.documents), \
                     mock.patch.object(server, '_describe_app', return_value={'process_id': 1234}), \
                     mock.patch.object(server, '_wait_for_worker_request', side_effect=[request, None]) as wait, \
                     mock.patch.object(fixture.documents, 'describe', side_effect=describe), \
                     mock.patch.object(operations, 'set_document_table_option_windows', side_effect=adapter), \
                     mock.patch.object(server, 'validate_operation_result', wraps=server.validate_operation_result) as validate:
                    server._worker_main(mock.Mock(), responses, lifecycle, False, 120, False)
                self.assertEqual(state['adapter_calls'], 1)
                self.assertEqual(state['descriptor_calls_after_adapter'], 0 if business_failure else 1)
                acquire.assert_called_once()
                self.assertEqual(wait.call_count, 2)
                validate.assert_called_once()
                self.assertFalse(fixture.app.CommandInProgress)
                pythoncom.CoUninitialize.assert_called_once()
                responses.put.assert_called_once()
                response = responses.put.call_args.args[0]
                self.assertFalse(response['success'])
                self.assertEqual(response['request_id'], request['request_id'])
                self.assertEqual(response['result']['mutation'], dict(attempted=True, may_have_changed=True))
                self.assertNotIn('document', response['result'])
                self.assertEqual(response['result']['before'], before)
                if business_failure:
                    self.assertEqual(response['error']['code'], 'NativeTableFailure')
                    self.assertEqual(response['result']['error'], dict(type='NativeTableFailure', message='first native business failure'))
                else:
                    self.assertEqual(response['error']['code'], 'RuntimeError')
                    self.assertEqual(response['result']['error']['message'], 'post-adapter descriptor failed')
                    self.assertTrue(response['result']['changed'])
                    self.assertEqual(response['result']['options'], after)


class _CommandApp:
    def __init__(self, app, *, fail_enter=(), fail_restore=()):
        self.app = app
        self.fail_enter = fail_enter
        self.fail_restore = fail_restore
        self.value = False
        self.enters = 0
        self.restores = 0

    def __getattr__(self, name):
        return getattr(self.app, name)

    @property
    def CommandInProgress(self):
        return self.value

    @CommandInProgress.setter
    def CommandInProgress(self, value):
        if value:
            self.enters += 1
            if self.enters in self.fail_enter:
                raise OSError('command entry failed before dispatch')
        else:
            self.restores += 1
            if self.restores in self.fail_restore:
                raise OSError('command restoration failed')
        self.value = value


class TableWorkerLateFaultTests(unittest.TestCase):
    def fixture(self, *, noop=False):
        fixture = fixtures.DocumentTableTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.kind = 2
        fixture.app.GetProcessID = lambda: 1234
        if noop:
            fixture.native[202] = 1
        fixture.register()
        request = dict(request_id='table-worker-late-fault', operation='document.table-option-set',
            parameters=dict(field='bom.grid_border', value='normal', expected_options=fixture.read()['options']),
            session_id='writer', document_id=fixture.entry.document_id, expected_update_stamp=7,
            lease_id=fixture.lease, timeout_ms=600000)
        return fixture, request

    def worker(self, fixture, app, requests):
        from types import SimpleNamespace
        pythoncom, com_client = mock.Mock(), mock.Mock()
        responses, lifecycle = mock.Mock(), mock.Mock()
        # Execute the real handler, native table adapter, native_api_sequence,
        # result validator and worker. Only COM/bootstrap and native proof are fakes.
        with mock.patch.dict('sys.modules', {'pythoncom': pythoncom,
                'win32com': mock.Mock(client=com_client), 'win32com.client': com_client}), \
             mock.patch.object(server, 'acquire_resident_app', return_value=(app, True)), \
             mock.patch.object(server, 'wait_windows_host_ready', return_value=0), \
             mock.patch.object(server, 'DocumentRegistry', return_value=fixture.documents), \
             mock.patch.object(server, '_describe_app', return_value={'process_id': 1234}), \
             mock.patch.object(server, '_wait_for_worker_request', side_effect=requests) as wait, \
             mock.patch.object(fixtures.adapter, '_native_windows_runtime', return_value=True), \
             mock.patch.object(server, 'execute_operation', wraps=operations.execute_operation) as execute, \
             mock.patch.object(server, 'validate_operation_result', wraps=server.validate_operation_result) as validate:
            server._worker_main(mock.Mock(), responses, lifecycle, False, 120, False)
        pythoncom.CoUninitialize.assert_called_once()
        return SimpleNamespace(replies=[call.args[0] for call in responses.put.call_args_list],
            lifecycle=[call.args[0] for call in lifecycle.put.call_args_list], wait=wait, execute=execute, validate=validate)

    def test_real_adapter_success_and_first_native_failures_survive_real_restore_fault(self):
        from swcli.result_schemas import validate_operation_result
        for failure in (None, 'raise', 'false'):
            with self.subTest(failure=failure):
                fixture, request = self.fixture()
                if failure:
                    def native(preference, option, value):
                        fixture.native[preference] = value
                        if failure == 'raise':
                            raise RuntimeError('first native table failure')
                        return False
                    fixture.extension.SetUserPreferenceInteger.side_effect = native
                app = _CommandApp(fixture.app, fail_restore=(1,))
                pending = dict(request, request_id='queued-must-not-dispatch')
                run = self.worker(fixture, app, [request, pending, None])
                self.assertEqual(run.wait.call_count, 1)
                run.execute.assert_called_once()
                self.assertEqual(len(run.replies), 1)
                response = run.replies[0]
                self.assertFalse(response['success'])
                self.assertEqual(response['error']['code'], 'NativeCommandRestoreFailed')
                result = response['result']
                self.assertEqual(result['mutation'], dict(attempted=True, may_have_changed=True))
                validate_operation_result(request['operation'], result)
                self.assertEqual(result['before'], request['parameters']['expected_options'])
                if failure:
                    self.assertEqual(result['error']['type'], 'RuntimeError')
                    expected_message = ('first native table failure' if failure == 'raise'
                                        else 'native table setter did not return success')
                    self.assertEqual(result['error']['message'], expected_message)
                    self.assertEqual(result['error']['worker_error']['type'], 'NativeCommandRestoreFailed')
                    fixture.document.SetSaveFlag.assert_not_called()
                    if failure == 'false':
                        self.assertIs(result['native_returned'], False)
                else:
                    self.assertEqual(result['error']['type'], 'NativeCommandRestoreFailed')
                    self.assertTrue(result['changed'])
                    self.assertEqual(result['options']['bom.grid_border'], dict(value='normal', native_value=1))
                    self.assertIs(result['native_returned'], True)
                    fixture.document.SetSaveFlag.assert_called_once()
                fixture.extension.SetUserPreferenceInteger.assert_called_once_with(202, 0, 1)
                self.assertEqual(fixture.native[202], 1)
                events = [row for row in run.lifecycle if row.get('event') == 'host-disconnected']
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['error'], response['error'])
                self.assertEqual((app.enters, app.restores), (1, 1))
                self.assertTrue(app.CommandInProgress)

    def test_late_actual_schema_failure_drops_bad_descriptor_but_retains_known_receipt(self):
        import json
        from swcli.result_schemas import validate_operation_result
        fixture, request = self.fixture()
        original = fixture.documents.describe
        late_describes = []

        def corrupt_descriptor(*args, **kwargs):
            descriptor = original(*args, **kwargs)
            if fixture.extension.SetUserPreferenceInteger.called:
                late_describes.append(True)
                descriptor['title'] = object()
            return descriptor

        app = _CommandApp(fixture.app)
        with mock.patch.object(fixture.documents, 'describe', side_effect=corrupt_descriptor):
            run = self.worker(fixture, app, [request, None])
        response = run.replies[0]
        self.assertEqual(response['error']['code'], 'OperationResultInvalid')
        self.assertEqual(set(response['result']), {'ok', 'action', 'mutation', 'error'})
        self.assertEqual(response['result']['mutation'], dict(attempted=True, may_have_changed=True))
        validate_operation_result(request['operation'], response['result'])
        json.dumps(response, allow_nan=False)
        self.assertEqual(late_describes, [True])
        fixture.extension.SetUserPreferenceInteger.assert_called_once_with(202, 0, 1)
        fixture.document.SetSaveFlag.assert_called_once()
        self.assertFalse(app.CommandInProgress)
        self.assertFalse(any(row.get('event') == 'host-disconnected' for row in run.lifecycle))
        self.assertEqual(run.wait.call_count, 2)

    def test_first_native_error_survives_minimal_fallback_after_late_validator_corruption(self):
        from swcli.result_schemas import validate_operation_result
        fixture, request = self.fixture()

        def native(preference, option, value):
            fixture.native[preference] = value
            raise RuntimeError('first native failure before validator')

        fixture.extension.SetUserPreferenceInteger.side_effect = native
        injected = []

        def late_validator(operation, result):
            if not injected:
                injected.append(True)
                result['document'] = {'title': object()}
            validate_operation_result(operation, result)

        app = _CommandApp(fixture.app)
        with mock.patch.object(server, 'validate_operation_result', side_effect=late_validator):
            run = self.worker(fixture, app, [request, None])
        response = run.replies[0]
        result = response['result']
        self.assertEqual(response['error']['code'], 'OperationResultInvalid')
        self.assertEqual(set(result), {'ok', 'action', 'mutation', 'error'})
        self.assertEqual(result['mutation'], dict(attempted=True, may_have_changed=True))
        self.assertEqual(result['error']['message'], 'first native failure before validator')
        self.assertEqual(result['error']['worker_error']['type'], 'OperationResultInvalid')
        validate_operation_result(request['operation'], result)
        fixture.extension.SetUserPreferenceInteger.assert_called_once_with(202, 0, 1)
        fixture.document.SetSaveFlag.assert_not_called()

    def test_actual_noop_stays_clean_on_success_and_restore_failure(self):
        from swcli.result_schemas import validate_operation_result
        for restore_failure in (False, True):
            with self.subTest(restore_failure=restore_failure):
                fixture, request = self.fixture(noop=True)
                app = _CommandApp(fixture.app, fail_restore=(1,) if restore_failure else ())
                run = self.worker(fixture, app, [request, None])
                response = run.replies[0]
                self.assertIs(response['success'], not restore_failure)
                self.assertEqual(response['result']['mutation'], dict(attempted=False, may_have_changed=False))
                self.assertFalse(response['result']['changed'])
                validate_operation_result(request['operation'], response['result'])
                fixture.no_setters()
                self.assertFalse(fixture.modified)
                self.assertEqual(run.wait.call_count, 1 if restore_failure else 2)
                self.assertEqual(any(row.get('event') == 'host-disconnected' for row in run.lifecycle), restore_failure)

    def test_second_request_failing_before_dispatch_cannot_borrow_first_result(self):
        for failure in ('entry-and-restore', 'parameters'):
            with self.subTest(failure=failure):
                fixture, request = self.fixture()
                second = dict(request, request_id='second-request-never-dispatched')
                if failure == 'parameters':
                    second['parameters'] = None
                    app = _CommandApp(fixture.app)
                else:
                    app = _CommandApp(fixture.app, fail_enter=(2,), fail_restore=(2,))
                run = self.worker(fixture, app, [request, second, None])
                self.assertEqual(run.wait.call_count, 3 if failure == 'parameters' else 2)
                run.execute.assert_called_once()
                self.assertEqual(len(run.replies), 2)
                self.assertTrue(run.replies[0]['success'])
                self.assertEqual(run.replies[0]['result']['mutation'], dict(attempted=True, may_have_changed=True))
                self.assertEqual(run.replies[1]['request_id'], second['request_id'])
                self.assertEqual(run.replies[1]['error']['code'],
                                 'TypeError' if failure == 'parameters' else 'NativeCommandRestoreFailed')
                self.assertNotIn('result', run.replies[1])
                fixture.extension.SetUserPreferenceInteger.assert_called_once_with(202, 0, 1)
                fixture.document.SetSaveFlag.assert_called_once()
                self.assertEqual(sum(row.get('event') == 'host-disconnected' for row in run.lifecycle),
                                 0 if failure == 'parameters' else 1)

    def test_non_json_postflight_fields_degrade_to_minimal_first_error_receipt(self):
        import json
        from swcli.result_schemas import validate_operation_result
        operation = 'document.table-option-set'
        result = dict(ok=False, action=operation, mutation=dict(attempted=True, may_have_changed=True),
                      error=dict(type='NativeFailure', message='first failure'),
                      warnings=[dict(code='postflight', message='untrusted detail', detail=object())])
        from swcli.result_schemas import OperationResultInvalid
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result(operation, result)
        response = server._preserve_table_receipt(server._error_response('late', 'RuntimeError', 'late fault'),
                                                  operation, result, RuntimeError('late fault'))
        partial = response['result']
        self.assertEqual(set(partial), {'ok', 'action', 'mutation', 'error'})
        self.assertEqual(partial['error']['type'], 'NativeFailure')
        self.assertEqual(partial['error']['message'], 'first failure')
        self.assertEqual(partial['error']['worker_error'], dict(type='RuntimeError', message='late fault'))
        validate_operation_result(operation, partial)
        json.dumps(response, allow_nan=False)

    def test_invalid_native_error_text_keeps_receipt_with_visible_escape(self):
        from swcli.result_schemas import validate_operation_result
        operation = 'document.table-option-set'
        result = dict(ok=False, action=operation, mutation=dict(attempted=True, may_have_changed=True),
                      error=dict(type='NativeFailure', message='native \ud800'))
        response = server._preserve_table_receipt(server._error_response('text', 'RuntimeError', 'late validator'),
                                                  operation, result, RuntimeError('late validator'))
        partial = response['result']
        self.assertEqual(partial['error']['message'], 'native \\ud800')
        self.assertEqual(partial['error']['worker_error']['message'], 'late validator')
        self.assertEqual(partial['mutation'], dict(attempted=True, may_have_changed=True))
        validate_operation_result(operation, partial)

    def test_receipt_guard_requires_this_operation_action_and_exact_two_boolean_fields(self):
        operation = 'document.table-option-set'
        base = dict(ok=True, action=operation, mutation=dict(attempted=True, may_have_changed=True))
        for defect in ('other-operation', 'other-action', 'missing-action', 'numeric-flag', 'extra-flag', 'missing-flag'):
            with self.subTest(defect=defect):
                result = deepcopy(base)
                current_operation = operation
                if defect == 'other-operation': current_operation = 'document.table-options'
                if defect == 'other-action': result['action'] = 'document.property-set'
                if defect == 'missing-action': result.pop('action')
                if defect == 'numeric-flag': result['mutation']['attempted'] = 1
                if defect == 'extra-flag': result['mutation']['other'] = True
                if defect == 'missing-flag': result['mutation'].pop('may_have_changed')
                response = server._error_response('guard', 'RuntimeError', 'late fault')
                returned = server._preserve_table_receipt(response, current_operation, result, RuntimeError('late fault'))
                self.assertNotIn('result', returned)


if __name__ == '__main__':
    unittest.main()
