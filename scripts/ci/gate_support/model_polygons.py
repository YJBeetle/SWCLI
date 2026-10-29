"""Installed public polygon cases; independent fixture oracles, no COM access."""
import hashlib
import json
import math
from pathlib import PureWindowsPath

from swcli.result_schemas import validate_operation_result
from gate_support.model_checks import LEASE_TTL_SECONDS, near, require

PROFILES = {
    'triangle': [(-10, -5), (10, -5), (-10, 10)],
    'ell': [(-10, -5), (10, -5), (10, 0), (-5, 0), (-5, 10), (-10, 10)],
}


def verify_polygon_metrics(metrics, shape, mode, reverse, transform):
    require(shape in PROFILES and mode in ('boss', 'cut'), 'unknown polygon fixture')
    perimeter, cx = (60, -10 + 20 / 3) if shape == 'triangle' else (70, -2.5)
    volume, surface = (1500, 300 + perimeter * 10) if mode == 'boss' else (11250, 3800 + perimeter * 5)
    require(type(metrics['solid_body_count']) is int and metrics['solid_body_count'] == 1,
            'polygon fixture changed solid count')
    near(metrics['volume_mm3'], volume, 'polygon analytic volume mismatch')
    near(metrics['surface_area_mm2'], surface, 'polygon analytic surface mismatch')
    target = [cx, 0, 5] if mode == 'boss' else [-750 * cx / 11250, 0, (60000 - 1875) / 11250]
    if reverse:
        target[2] *= -1
    require(len(transform) == 16 and all(type(v) in (int, float) and math.isfinite(v) for v in transform),
            'polygon transform is incomplete/nonfinite')
    # SOLIDWORKS row-vector rotation, translation in meters, uniform scale.
    # This convention was independently checked with native MathPoint in the
    # internal 48-case proof. Here only the installed public receipt is used.
    vector = [metrics['centroid_mm'][axis] for axis in 'xyz']
    for i, expected in enumerate(target):
        actual = sum(vector[j] * transform[j * 3 + i] for j in range(3)) * transform[12] + transform[9 + i] * 1000
        near(actual, expected, 'polygon centroid/direction mismatch')


def verify_polygon_segments(observed, points):
    require(observed['geometry_complete'] is True and observed['editing'] is False
            and observed['segment_count'] == observed['profile_segment_count'] == len(points),
            'polygon public sketch observation is incomplete')
    expected = {tuple(sorted((i, (i+1) % len(points)))) for i in range(len(points))}
    edges = set()
    for segment in observed['segments']:
        geometry = segment['geometry']
        require(segment['construction'] is False and geometry['kind'] == 'line', 'polygon has extra/nonline geometry')
        pair = []
        for key in ('start_mm', 'end_mm'):
            point = geometry[key]
            near(point['z'], 0, 'polygon endpoint outside sketch XY', 1e-6)
            matches = [i for i, p in enumerate(points)
                       if math.dist((point['x'], point['y']), p) <= 1e-6]
            require(len(matches) == 1, 'polygon endpoint changed or is ambiguous')
            pair.append(matches[0])
        edge = tuple(sorted(pair))
        require(edge not in edges, 'polygon contains duplicate edges')
        edges.add(edge)
    require(edges == expected, 'polygon edges do not form the requested cycle')


class PolygonCases:
    def polygon_model(self):
        evidence = self.record['polygon_cases'] = []
        for shape in PROFILES:
            for winding in ('ccw', 'cw'):
                for mode in ('boss', 'cut'):
                    for plane in ('front', 'top', 'right'):
                        for reverse in (False, True):
                            case = dict(shape=shape, winding=winding, mode=mode, plane=plane,
                                        reverse=reverse, success=False)
                            evidence.append(case)
                            self._polygon_case(case)
                            self.require_empty()
                            case['success'] = True

    def _polygon_case(self, case):
        shape, winding, mode, plane, reverse = (case[k] for k in ('shape', 'winding', 'mode', 'plane', 'reverse'))
        points = PROFILES[shape][::(-1 if winding == 'cw' else 1)]
        args = ['sketch', 'polygon', '--plane', plane, '--vertices-mm', json.dumps(points)]
        document, foreground = self.create(), self.create()
        self.command('document', 'lease', 'acquire', '--ttl-seconds', LEASE_TTL_SECONDS, document=document)
        if mode == 'cut':
            base = self.rectangle(document, plane=plane)
            self.feature(document, base['sketch']['sketch_id'], depth=10, reverse=reverse)
        before = self.command('document', 'inspect', document=document)['document']
        self.command(*args, document=document, session=self.session+'-contender', expected_error='DocumentLeaseConflict')
        self.write(*args, '--if-update-stamp', before['update_stamp']+1,
                   document=document, expected_error='DocumentUpdateConflict')
        require(self.command('document', 'inspect', document=document)['document'] == before,
                'polygon refused write changed document state')
        made = case['sketch_creation'] = self.write(*args, '--if-update-stamp', before['update_stamp'], document=document)
        self.background(made, document)
        validate_operation_result('sketch.polygon', made)
        require(not made.get('warnings'), 'polygon creation left restoration warnings')
        sketch_id = made['sketch']['sketch_id']
        self.command('sketch', 'inspect', sketch_id, document=foreground, expected_error='SketchNotFound')
        observed = self.command('sketch', 'inspect', sketch_id, document=document)
        verify_polygon_segments(observed, points)
        if mode == 'cut':
            before = self.command('document', 'inspect', document=document)['document']
            self.write('feature', 'cut-extrude', sketch_id, '--through-all', document=document,
                       expected_error='UnsupportedDimensionProfile')
            require(self.command('document', 'inspect', document=document)['document'] == before,
                    'unsupported polygon through-all changed state')
        arguments = ['feature', 'extrude' if mode == 'boss' else 'cut-extrude', sketch_id,
                     '--depth-mm', 10 if mode == 'boss' else 5]
        if reverse:
            arguments.append('--reverse')
        feature = case['feature_creation'] = self.write(*arguments, document=document)
        self.background(feature, document)
        require(not feature.get('warnings') and feature['rebuilt'] is True
                and feature['diagnostics']['healthy'] is True and feature['diagnostics']['truncated'] is False
                and feature['bodies']['count'] == 1, 'polygon solid creation is incomplete or left restoration warnings')
        feature_id = feature['feature']['feature_id']
        before = self.command('document', 'inspect', document=document)['document']
        refusal = case['depth_refusal'] = self.write('feature', 'set-depth', feature_id, '--depth-mm', 12,
                   document=document, expected_error='UnsupportedDepthProfile', timeout_seconds=self.depth_request_timeout_seconds)
        require(all(refusal['mutation'][flag] is False for flag in
                    ('staging_attempted', 'configuration_scope_applied', 'commit_attempted', 'committed'))
                and self.command('document', 'inspect', document=document)['document'] == before,
                'unsupported polygon depth edit staged, committed or changed state')
        transform = made['model_to_sketch_transform']
        case['geometry'] = self.measure(document)['metrics']
        verify_polygon_metrics(case['geometry'], shape, mode, reverse, transform)
        self._polygon_definition(document, feature_id, mode, reverse)
        stem = '-'.join(('polygon', shape, winding, mode, plane, 'reverse' if reverse else 'forward'))
        host_path = str(PureWindowsPath(self.host_directory) / (stem+'.SLDPRT'))
        path = self.directory / (stem+'.SLDPRT')
        saved = self.write('document', 'save-as', host_path, document=document)
        require(saved['save_errors'] == 0 and saved['save_warnings'] is None and path.is_file()
                and saved['document']['modified'] is False, 'polygon native save failed')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.close(document)
        opened = self.command('document', 'open', host_path, '--read-only')
        require(opened['api_errors'] == opened['api_warnings'] == 0
                and PureWindowsPath(opened['document']['path']) == PureWindowsPath(host_path), 'polygon reopen failed')
        reopened = opened['document']['document_id']
        require(reopened != document, 'polygon reopen reused retired document handle')
        self.command('sketch', 'inspect', sketch_id, document=reopened, expected_error='SketchNotFound')
        self.command('feature', 'inspect', feature_id, document=reopened, expected_error='FeatureNotFound')
        listed = self.command('feature', 'list', document=reopened)
        kind = 'boss-extrude' if mode == 'boss' else 'cut-extrude'
        candidates = [f for f in listed['features'] if f['kind'] == kind]
        require(listed['count'] == len(listed['features']) == (1 if mode == 'boss' else 2)
                and len(candidates) == 1 and candidates[0]['feature_id'] != feature_id, 'fresh polygon feature discovery failed')
        self._polygon_definition(reopened, candidates[0]['feature_id'], mode, reverse)
        sketches = self.command('sketch', 'list', document=reopened)
        candidates = [s for s in sketches['sketches'] if s['name'] == made['sketch']['name']]
        # Names locate candidates only; exact fresh handle geometry proves identity.
        require(len(candidates) == 1 and candidates[0]['sketch_id'] != sketch_id, 'fresh polygon sketch discovery failed')
        observed = self.command('sketch', 'inspect', candidates[0]['sketch_id'], document=reopened)
        verify_polygon_segments(observed, points)
        case['reopened_geometry'] = self.measure(reopened)['metrics']
        verify_polygon_metrics(case['reopened_geometry'], shape, mode, reverse, transform)
        diagnostic = case['reopened_diagnostics'] = self.command('document', 'diagnose', document=reopened)
        require(diagnostic['diagnostics']['healthy'] is True and diagnostic['diagnostics']['truncated'] is False
                and diagnostic['needs_rebuild'] == 0, 'polygon reopen is not healthy/clean')
        require(self.command('document', 'inspect', document=reopened)['document']['modified'] is False
                and hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'polygon read-only reopen changed saved bytes/state')
        case.update(file_sha256=digest, native_path=host_path)
        self.close(reopened)
        self.close(foreground)

    def _polygon_definition(self, document, feature_id, mode, reverse):
        result = self.command('feature', 'inspect', feature_id, document=document)
        definition = result['definition']
        require(definition['end_condition'] == 0 and definition['both_directions'] is False
                and definition['thin'] is False and definition['reverse_direction'] is (reverse if mode == 'boss' else not reverse)
                and result['observation']['unchanged'] is True, 'polygon blind feature definition changed')
        near(definition['depth_mm'], 10 if mode == 'boss' else 5, 'polygon native depth changed', 1e-6)
