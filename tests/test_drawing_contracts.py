import copy
import unittest

from swcli.cli import build_parser, _typed_operation
from swcli.operation_schemas import validate_operation_request, OPERATION_CATALOG
from swcli.result_schemas import validate_operation_result, OperationResultInvalid


class DrawingContracts(unittest.TestCase):
    def test_create_conditions(self):
        validate_operation_request('document.create', {'type': 'drawing', 'template': 'x.DRWDOT', 'projection': 'first-angle'})
        for value in ({'type': 'drawing'}, {'type': 'drawing', 'template': 'x'},
                      {'projection': 'first-angle'}, {'type': 'part', 'projection': 'third-angle'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_operation_request('document.create', value)

    def test_cli(self):
        args = build_parser().parse_args(['drawing', 'standard-views', 'd-abc123', '--configuration', 'Default', '--document', 'd-xyz123', '--lease', 'l-abcdefgh1234', '--if-update-stamp', '4'])
        payload = _typed_operation(args)
        self.assertEqual(payload[0], 'drawing.standard-views')
        self.assertEqual(payload[1], {'source_document_id': 'd-abc123', 'configuration': 'Default'})
        self.assertEqual(payload[3:], ('d-xyz123', 4, 'l-abcdefgh1234'))

    def test_request_guard(self):
        for source in ('active', 'current', 'd-a', ''):
            with self.assertRaises(ValueError):
                validate_operation_request('drawing.standard-views', {'source_document_id': source, 'configuration': 'Default'})
        self.assertTrue(OPERATION_CATALOG['drawing.standard-views'].lease_guarded)
        self.assertTrue(OPERATION_CATALOG['drawing.standard-views'].temporary_activation)

    def success(self):
        source = dict(path='C:\\box.SLDPRT', configuration='Default', type=1, modified=False, update_stamp=1, needs_rebuild=0)
        return dict(ok=True, action='drawing.standard-views', document=dict(title='Drawing', path='', type=3, modified=True, update_stamp=1),
                    source_document_id='d-abc123', source=source,
                    sheet=dict(name='Sheet1', properties=[0,0,1,1,1,1,1,0], format_path='', format_available=False, projection='first-angle'),
                    views=[dict(name=role, path=source['path'], configuration='Default', position=[0,0], outline=[0,0,1,1], scale=[1,1], transform=[0]*16, role=role) for role in ('front','top','left')],
                    mutation=dict(attempted=True, may_have_changed=True), rebuilt=True,
                    verification=dict(passed=True, source_unchanged=True, layout_verified=True),
                    diagnostics=dict(healthy=True, issues=[], issue_count=0, scanned_feature_count=1, truncated=False, limit=100), cleanup_errors=[])

    def test_success_and_semantics(self):
        value = self.success()
        matrices = ([1,0,0,0,1,0,0,0,1], [1,0,0,0,0,1,0,-1,0], [0,0,-1,0,1,0,1,0,0])
        for view, matrix, pos in zip(value['views'], matrices, ([.2,.6],[.2,.2],[.6,.6])):
            view.update(transform=list(matrix)+[0,0,0,1,0,0,0], position=pos,
                        outline=[pos[0]-.05,pos[1]-.05,pos[0]+.05,pos[1]+.05])
        validate_operation_result('drawing.standard-views', value)
        for mutate in (lambda x: x['views'][0].update(configuration='Other'),
                       lambda x: x['views'][0].update(transform=[0]*15),
                       lambda x: x['source'].update(modified=True),
                       lambda x: x['verification'].update(passed=False),
                       lambda x: x['views'][0].update(position=[float('nan'),0])):
            broken = copy.deepcopy(value)
            mutate(broken)
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result('drawing.standard-views', broken)

    def test_partial_failure_and_no_masquerade(self):
        value = dict(ok=False, action='drawing.standard-views', error=dict(type='NativeFailed', message='failure'), views=[])
        validate_operation_result('drawing.standard-views', value)
        value['ok'] = True
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result('drawing.standard-views', value)

    def test_native_drawing_create_evidence(self):
        fixture = self.success()
        result = dict(ok=True, action='document.create', created=True,
                      document=fixture['document'],
                      template=dict(ok=True, path='C:\\drawing.DRWDOT', source='explicit'),
                      sheet=fixture['sheet'], views=[], diagnostics=fixture['diagnostics'],
                      cleanup_errors=[], warnings=[dict(code='DrawingFormatUnavailable',
                          message='embedded format path is unavailable; retained unchanged')])
        validate_operation_result('document.create', result)
        for missing in ('ok', 'source'):
            broken = copy.deepcopy(result)
            del broken['template'][missing]
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result('document.create', broken)
