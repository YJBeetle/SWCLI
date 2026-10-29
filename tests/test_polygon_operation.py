"""Public polygon contracts: malformed data never reaches the CAD worker."""
import contextlib
from copy import deepcopy
import io
import math
import unittest
from unittest import mock

from swcli.cli import build_parser, _typed_operation, main
from swcli.operation_schemas import validate_operation_request, OPERATION_CATALOG
from swcli.result_schemas import validate_operation_result, OperationResultInvalid
from swcli.hosts.windows_polygons import observe_polygon_sketch
from swcli.polygon_geometry import validate_polygon
from test_windows_polygons import sketch, POINTS


def receipt():
    return dict(action='sketch.polygon', ok=True, plane='front', coordinate_system='sketch-local',
        model_to_sketch_transform=[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
        dimensions=dict(unit='millimeter', vertices_mm=deepcopy(POINTS)),
        sketch=dict(sketch_id='s-ab12cd', name='Sketch1', type='ProfileFeature',
                    constraint_status=2, dimensions_created=False), editing=False,
        geometry_verification=observe_polygon_sketch(sketch(), validate_polygon(POINTS)),
        document=dict(title='Part1', path='', type=1, modified=True, update_stamp=1))


class PolygonOperationTests(unittest.TestCase):
    def test_cli_converts_pairs_preserving_order_and_write_context(self):
        args = build_parser().parse_args(['sketch', 'polygon', '--plane', 'right',
            '--vertices-mm', '[[0,0],[20,0],[0,15]]', '--document', 'd-ab12cd',
            '--if-update-stamp', '0', '--lease', 'l-ab12cd34ef56', '--json'])
        self.assertEqual(_typed_operation(args), ('sketch.polygon',
            dict(plane='right', vertices_mm=POINTS), True, 'd-ab12cd', 0, 'l-ab12cd34ef56'))
        spec = OPERATION_CATALOG['sketch.polygon']
        self.assertTrue(spec.lease_guarded and spec.temporary_activation and spec.selected_document)

    def test_cli_invalid_vertices_fail_before_transport(self):
        for text in ('null', '{}', '[[true,0],[20,0],[0,15]]', '[[0,0],[20,0],[0,15],[0,0]]',
                     '[[0,0],[1,1],[0,1],[1,0]]', '[[0,0],[NaN,0],[0,15]]',
                     '[[0,0],[20,0],[0,15,0]]', '[["0",0],[20,0],[0,15]]'):
            with self.subTest(text=text), contextlib.redirect_stderr(io.StringIO()), \
                 mock.patch('swcli.cli.call_daemon') as call, self.assertRaises(SystemExit):
                main(['sketch', 'polygon', '--plane', 'front', '--vertices-mm', text])
            call.assert_not_called()

    def test_nested_protocol_validation_and_geometric_refusal(self):
        valid = dict(plane='front', vertices_mm=deepcopy(POINTS))
        self.assertEqual(validate_operation_request('sketch.polygon', valid), valid)
        invalid = [None, (), {}, [], POINTS[:2], POINTS * 22,
            [dict(x=True, y=0), *POINTS[1:]], [dict(x='0', y=0), *POINTS[1:]],
            [dict(x=math.inf, y=0), *POINTS[1:]], [dict(x=10**1000, y=0), *POINTS[1:]],
            [dict(x=0), *POINTS[1:]], [dict(x=0, y=0, z=0), *POINTS[1:]],
            [[0, 0], *POINTS[1:]], [dict(x=None, y=0), *POINTS[1:]],
            POINTS + POINTS[:1], [dict(x=0,y=0),dict(x=1,y=1),dict(x=0,y=1),dict(x=1,y=0)]]
        for points in invalid:
            with self.subTest(points=str(points)[:80]), self.assertRaises(ValueError):
                validate_operation_request('sketch.polygon', dict(plane='front', vertices_mm=points))

    def test_invalid_nested_request_never_resolves_or_activates_a_document(self):
        from swcli.daemon.operations import execute_operation
        app, registry = mock.Mock(), mock.Mock()
        with self.assertRaises(ValueError):
            execute_operation(app, 'sketch.polygon', dict(plane='front', vertices_mm=[dict(x=True,y=0),*POINTS[1:]]),
                              documents=registry, document_id='d-ab12cd')
        self.assertEqual(app.mock_calls, [])
        self.assertEqual(registry.mock_calls, [])

    def test_success_requires_consistent_closed_cycle_and_metadata(self):
        validate_operation_result('sketch.polygon', receipt())
        def no_name(r): r['sketch'].pop('name')
        def shift_vertex(r): r['geometry_verification']['actual_vertices_mm'][0]['x'] += .01
        def centroid(r): r['geometry_verification']['centroid_mm']['x'] += .01
        for mutation in (no_name, shift_vertex, centroid,
                lambda r:r.update(editing=True),
                lambda r:r['geometry_verification'].update(segment_count=4),
                lambda r:r['geometry_verification'].update(native_closed=False),
                lambda r:r['geometry_verification'].update(signed_area_mm2=-150),
                lambda r:r['geometry_verification'].update(perimeter_mm=59),
                lambda r:r['geometry_verification'].update(absolute_tolerance_mm=.1)):
            result=receipt(); mutation(result)
            with self.subTest(mutation=mutation), self.assertRaises(OperationResultInvalid):
                validate_operation_result('sketch.polygon', result)
        validate_operation_result('sketch.polygon', dict(action='sketch.polygon', ok=False,
            error=dict(type='NativeFailure', message='second line failed'), sketch=dict(sketch_id='s-ab12cd')))
