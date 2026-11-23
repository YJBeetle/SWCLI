"""Windows fixtures for the fixed partial-revolve rejection controls."""
import hashlib
import math
from pathlib import Path
from unittest import mock

from .revolve_controls import INJECTED_MESSAGE, require_clean_control_save
from .revolve_direction import require, require_clean_reopen, require_native_ok
from .revolve_direction_native import NativeBackend


class NativeControlsBackend(NativeBackend):
    def prepare_refusal(self, name, case, fixture):
        from swcli.hosts.windows_documents import open_windows_document_with_handle
        from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
        from swcli.hosts.windows_sketches import _features

        fixture.update(self.fixture(case))
        if name == 'private-read-only':
            saved = fixture['saved'] = self.save(case, filename='read-only-profile.SLDPRT')
            require_clean_control_save(saved, 'read-only fixture save')
            self.close()
            opened, self.document = open_windows_document_with_handle(saved['path'], app=self.app, read_only=True)
            self.close_attempted = False
            fixture['opened'] = opened
            require_clean_reopen(opened)
            require(self.document is not None and self.value(self.document, 'IsOpenedReadOnly') is True,
                    'fixture did not reopen read-only')
            candidates = [f for f in _features(self.document) if self.value(f, 'GetTypeName2') == 'ProfileFeature']
            require(len(candidates) == 1, 'read-only fixture lacks one unabsorbed profile')
            self.sketch = candidates[0]
        elif name == 'private-existing-solid':
            result, extrusion = extrude_sketch_windows_with_handle(
                app=self.app, document=self.document, sketch_feature=self.sketch, depth_mm=10, merge=False)
            fixture['extrusion'] = result
            require_native_ok(result, 'solid fixture extrusion')
            require(extrusion is not None and len(tuple(self.document.GetBodies2(0, False) or ())) == 1,
                    'fixture did not create exactly one existing solid')
            fixture['target_sketch'] = self.add_rectangle(case)
        elif name == 'private-offset-plane':
            fixture['offset_sketch'] = self.offset_rectangle(case)

    def add_rectangle(self, case):
        from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle

        x0, y0, x1, y1 = case['bounds_mm']
        result, self.sketch = create_rectangle_sketch_windows_with_handle(app=self.app, document=self.document,
            plane=case['plane'], width_mm=x1-x0, height_mm=y1-y0, center_x_mm=(x0+x1)/2, center_y_mm=(y0+y1)/2)
        require_native_ok(result, 'control rectangle')
        require(self.sketch is not None, 'control rectangle did not return an exact handle')
        return result

    def offset_rectangle(self, case):
        from swcli.hosts import windows_sketches
        from swcli.hosts.windows_feature_inspection import _same

        # InsertRefPlane takes a constraint bitmask and distance in meters.
        # Verify the installed enum before calling this fixture-only constructor.
        typelib = self.pythoncom.LoadTypeLib(str(self.swconst))
        distance = []
        for index in range(typelib.GetTypeInfoCount()):
            info = typelib.GetTypeInfo(index)
            if info.GetDocumentation(-1)[0] != 'swRefPlaneReferenceConstraints_e':
                continue
            for offset in range(info.GetTypeAttr().cVars):
                desc = info.GetVarDesc(offset)
                if info.GetDocumentation(desc[0])[0] == 'swRefPlaneReferenceConstraint_Distance':
                    distance.append(desc.value)
        require(distance == [8], 'installed distance plane constraint differs from SW2025 API')
        old_planes = [f for f in windows_sketches._features(self.document) if self.value(f, 'GetTypeName2') == 'RefPlane']
        plane = windows_sketches._standard_plane(self.document, 'front')
        require(plane is not None and plane.Select2(False, 0) is True, 'could not select the origin front plane')
        created = self.value(self.document, 'FeatureManager').InsertRefPlane(distance[0], .01, 0, 0., 0, 0.)
        require(created is not None, 'SOLIDWORKS did not create the 10 mm offset fixture plane')
        self.document.ClearSelection2(True)
        matches = [f for f in windows_sketches._features(self.document)
                   if self.value(f, 'GetTypeName2') == 'RefPlane' and
                   not any(_same(self.app, f, old) for old in old_planes)]
        require(len(matches) == 1, 'offset fixture did not add exactly one native plane feature')
        with mock.patch.object(windows_sketches, '_standard_plane', return_value=matches[0]):
            result = self.add_rectangle(case)
        sketch = self.value(self.sketch, 'GetSpecificFeature2')
        frame = list(self.value(self.value(sketch, 'ModelToSketchTransform'), 'ArrayData'))
        require(len(frame) == 16 and math.isclose(abs(frame[11]), .01, rel_tol=0, abs_tol=1e-10)
                and all(abs(v) <= 1e-10 for v in frame[9:11]), 'fixture sketch is not on the real 10 mm offset')
        return dict(sketch=result, transform=frame, constraint=distance[0], distance_m=.01)

    def snapshot(self):
        from swcli.hosts.windows_feature_inspection import _same, _state
        from swcli.hosts.windows_sketches import _features

        state, edit, foreground = _state(self.app, self.document)
        path = self.value(self.document, 'GetPathName')
        return dict(state=state, editing=edit is not None, foreground_same=_same(self.app, foreground, self.document),
            read_only=self.value(self.document, 'IsOpenedReadOnly'),
            selected=self.value(self.document, 'SelectionManager').GetSelectedObjectCount2(-1),
            body_count=len(tuple(self.document.GetBodies2(-1, False) or ())),
            features=[(self.value(f, 'Name'), self.value(f, 'GetTypeName2')) for f in _features(self.document)],
            path=path, file_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None)

    def refusal(self, name, case, row):
        from swcli.hosts.native_trace import trace_native_request
        from swcli.hosts.windows_revolves import _calibrate_revolve_windows_with_handle

        with trace_native_request(name, 'feature.revolve.refusal-control'):
            if name.startswith('public-'):
                self.public_refusal(name, case, row)
                return
            bounds = list(case['bounds_mm'])
            if name == 'private-stale-profile':
                bounds[2] += 1
            result, feature = _calibrate_revolve_windows_with_handle(app=self.app, document=self.document,
                sketch_feature=self.sketch, expected_profile_mm=bounds, axis_mm=case['axis_mm'],
                angle_deg=case['angle_deg'], constants=self.constants, rotation_sign=case['rotation_sign'],
                axis_direction=-1 if name == 'private-reversed-axis' else case['axis_direction'])
            row.update(receipt=result, feature_handle_retained=feature is not None, dispatcher_exception=False)

    def public_refusal(self, name, case, row):
        from swcli.daemon.documents import DocumentLeaseConflict, DocumentRegistry, SketchNotFound
        from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
        from swcli.result_schemas import validate_operation_result

        registry = DocumentRegistry(self.app)
        entry = registry.register(self.document)
        sketch_id = registry.register_sketch(entry, self.sketch)
        lease = registry.acquire_lease(entry, session_id='revolve-control-owner', ttl_seconds=600)
        stamp = registry.describe(entry, session_id='revolve-control-owner')['update_stamp']
        if name == 'public-missing-sketch':
            sketch_id = 's-000000' if sketch_id != 's-000000' else 's-000001'
        values = dict(sketch_id=sketch_id, expected_profile_mm=case['bounds_mm'], axis_mm=case['axis_mm'],
                      angle_deg=case['angle_deg'])
        row.update(feature_handle_retained=False, dispatcher_exception=False)
        try:
            receipt = execute_operation(self.app, 'feature.revolve', values, documents=registry,
                session_id='competing-revolve-control' if name == 'public-wrong-lease' else 'revolve-control-owner',
                document_id=entry.document_id, expected_update_stamp=stamp+1 if name == 'public-stale-stamp' else stamp,
                lease_id=lease['lease_id'])
        except (DocumentLeaseConflict, DocumentUpdateConflict, SketchNotFound) as error:
            row.update(receipt=dict(ok=False, error=dict(type=type(error).__name__, message=str(error))),
                       dispatcher_exception=True)
        else:
            row['receipt'] = receipt
            validate_operation_result('feature.revolve', receipt)

    def create_partial(self, case, row):
        from swcli.hosts import windows_revolves

        with mock.patch.object(windows_revolves, 'observe_revolve_definition', side_effect=RuntimeError(INJECTED_MESSAGE)):
            creation, retained = self.create(case)
        row.update(creation=creation, feature_handle_retained=retained)

    def preserved_partial(self):
        from swcli.hosts.windows_documents import _diagnose_features
        from swcli.hosts.windows_feature_inspection import _same
        from swcli.hosts.windows_measurements import measure_part_windows
        from swcli.hosts.windows_sketches import _features

        features = [f for f in _features(self.document) if self.value(f, 'GetTypeName2') == 'Revolution']
        return dict(exact_handle_matches=len(features) == 1 and _same(self.app, features[0], self.feature),
            body_count=len(tuple(self.document.GetBodies2(-1, False) or ())),
            measurement=measure_part_windows(document=self.document), diagnostics=_diagnose_features(self.document, 500))
