"""Metadata classification must not hide geometry, duplicate it, or bypass the native roundtrip."""
from types import SimpleNamespace
import sys
import unittest
from unittest import mock
import test_step_sketch_readback_candidate as fixture

candidate=fixture.candidate
CONTAINERS=('FavoriteFolder','HistoryFolder','SelectionSetFolder','SensorFolder','InkMarkupFolder','NotesAreaFtrFolder')


def forbid_container_measurement(*args):raise AssertionError('container must not be measured as sketch geometry')


def folder(kind,identity,child=None):
    return SimpleNamespace(GetID=identity,Name='renamed metadata',GetTypeName2=kind,
        GetNextFeature=None,GetFirstSubFeature=child,GetNextSubFeature=None,
        GetSpecificFeature2=forbid_container_measurement,GetErrorCode2=forbid_container_measurement)


def surround(doc,sketch,kinds=CONTAINERS):
    nodes=[folder(kind,100+i) for i,kind in enumerate(kinds)]
    for parent,child in zip(nodes,nodes[1:]+[sketch]):parent.GetFirstSubFeature=child
    doc.FirstFeature=nodes[0]
    return nodes


class MetadataTraversalTests(unittest.TestCase):
    def read(self,doc,geometry='wireframe',evidence=None):
        with mock.patch.dict(sys.modules,fixture.native_modules()):
            return candidate.read_wireframe(fixture.load(),doc,{} if evidence is None else evidence,fixture.call,geometry)

    def test_exact_containers_keep_nested_12_and_18_segments_and_health_checks(self):
        for kind in CONTAINERS:
            for geometry in ('wireframe','wireframe-sketches'):
                with self.subTest(kind=kind,geometry=geometry):
                    doc,sketch,segments=fixture.document(fixture.wire_expected_lengths(geometry));node=folder(kind,23,sketch);doc.FirstFeature=node
                    result=self.read(doc,geometry)
                    self.assertTrue(result['complete']);self.assertEqual(result['lengths_mm'],fixture.wire_expected_lengths(geometry))
                    rows=result['feature_inventory'];self.assertEqual([(r['feature_id'],r['parent_id'],r['depth']) for r in rows],[(23,None,0),(17,23,1)])
                    self.assertNotIn('feature_health',rows[0]);sketch.GetErrorCode2.assert_called_once();segments.assert_called_once()

    def test_all_top_level_containers_and_alias_subtrees_deduplicate_native_ids(self):
        doc,sketch,segments=fixture.document();nodes=[folder(k,100+i,sketch) for i,k in enumerate(CONTAINERS)]
        for parent,next_node in zip(nodes,nodes[1:]+[sketch]):parent.GetNextFeature=next_node
        doc.FirstFeature=nodes[0];result=self.read(doc)
        self.assertEqual(len(result['feature_inventory']),7);self.assertEqual(result['segment_count'],12)
        self.assertEqual([r['kind'] for r in result['feature_inventory'][:-1]],list(CONTAINERS))
        sketch.GetErrorCode2.assert_called_once();segments.assert_called_once()

    def test_unknown_geometry_beneath_each_container_fails_even_after_complete_top_level_vector(self):
        for kind in CONTAINERS:
            with self.subTest(kind=kind):
                doc,valid,segments=fixture.document();_,unknown,unread=fixture.document(kind='RefCurve');unknown.GetID=18
                node=folder(kind,23,unknown);valid.GetNextFeature=node;e={}
                with self.assertRaisesRegex(RuntimeError,'unexpected feature type RefCurve'):self.read(doc,evidence=e)
                self.assertEqual(e['segment_count'],12);self.assertFalse(e['complete']);segments.assert_called_once();unread.assert_not_called()
                unknown.GetErrorCode2.assert_not_called();self.assertEqual(e['feature_inventory'][-1]['parent_id'],23)
                self.assertIn('RefCurve',e['first_error']['message'])

    def test_no_folder_wildcard_case_folding_display_name_or_endtag_escape(self):
        for kind in ('UnknownFolder','GeometryFolder','FavoriteFolder2','favoritefolder','SelectionSet','InkMarkup','NotesAreaFtr'):
            for display in ('Favorites','Notes1___EndTag___'):
                with self.subTest(kind=kind,display=display):
                    doc,sketch,segments=fixture.document();node=folder(kind,23,sketch);node.Name=display;doc.FirstFeature=node;e={}
                    with self.assertRaisesRegex(RuntimeError,'unexpected feature type'):self.read(doc,evidence=e)
                    self.assertFalse(e['complete']);self.assertEqual(e['segment_count'],0);segments.assert_not_called();sketch.GetErrorCode2.assert_not_called()

    def test_nested_empty_error_and_incomplete_geometry_are_still_refused(self):
        for values,code in (([],0),([10]*2+[30]*4+[40]*3,0),(fixture.wire_expected_lengths('wireframe'),1)):
            with self.subTest(values=len(values),code=code):
                doc,sketch,segments=fixture.document(values,code=code);surround(doc,sketch);e={}
                with self.assertRaises(RuntimeError):self.read(doc,evidence=e)
                self.assertFalse(e['complete']);self.assertIn('first_error',e)
                if code:segments.assert_not_called()
                elif not values:self.assertEqual(e['segment_count'],0)
                else:self.assertEqual(e['segment_count'],9);self.assertEqual(e['total_length_mm'],260)

    def test_metadata_subtree_cycles_and_depth_limits_still_stop(self):
        doc,sketch,segments=fixture.document();node=folder('FavoriteFolder',23,sketch);doc.FirstFeature=node;sketch.GetNextSubFeature=sketch;e={}
        with self.assertRaisesRegex(RuntimeError,'sibling cycle'):self.read(doc,evidence=e)
        self.assertFalse(e['complete']);segments.assert_not_called()
        doc,sketch,segments=fixture.document();surround(doc,sketch,['FavoriteFolder']*66);e={}
        with self.assertRaisesRegex(RuntimeError,'safety limit'):self.read(doc,evidence=e)
        self.assertFalse(e['complete']);self.assertEqual(e['segment_count'],0);segments.assert_not_called()


class MetadataRoundtripTests(unittest.TestCase):
    def roundtrip(self,*,unknown_reopened=False,**options):
        original=fixture.document;documents=[]
        def with_containers(*args,**kwargs):
            doc,sketch,segments=original(*args,**kwargs);surround(doc,sketch);documents.append(doc)
            if unknown_reopened and len(documents)==2:
                unknown=folder('UnexpectedGeometryFolder',500);unknown.Name='Favorites';sketch.GetNextSubFeature=unknown
            return doc,sketch,segments
        with mock.patch.object(fixture,'document',side_effect=with_containers):
            result=fixture.SketchRoundtripTests.run_roundtrip(self,null_candidate=True,neutral_free_candidate=True,**options)
        return result

    def test_nested_metadata_keeps_single_null_import_save_readonly_reopen_both_vectors(self):
        for geometry in ('wireframe','wireframe-sketches'):
            with self.subTest(geometry=geometry):
                case,exc,reads,app,live=self.roundtrip(kind=geometry)
                self.assertIsNone(exc);self.assertTrue(case['success']);self.assertEqual(reads,2);self.assertIsNone(live['document'])
                self.assertEqual(app.LoadFile4.call_count,1);self.assertEqual(app.CloseDoc.call_count,2)
                self.assertTrue(case['imported_reopen']['read_only']);self.assertTrue(case['sketch_observer_preferences']['restored'])
                self.assertEqual(case['imported_native_sha256'],fixture.hashlib.sha256(b'original native').hexdigest())
                for key in ('imported_geometry','reopened_imported_geometry'):
                    self.assertTrue(case[key]['complete']);self.assertEqual(case[key]['lengths_mm'],fixture.wire_expected_lengths(geometry))
                    self.assertEqual(len(case[key]['feature_inventory']),7)

    def test_unknown_reopened_descendant_preserves_partial_vector_and_fails(self):
        case,exc,reads,app,live=self.roundtrip(unknown_reopened=True)
        self.assertIsNotNone(exc);self.assertIn('UnexpectedGeometryFolder',str(exc));self.assertFalse(case.get('success',False));self.assertEqual(reads,2)
        e=case['reopened_imported_geometry'];self.assertFalse(e['complete']);self.assertEqual(e['segment_count'],12)
        self.assertTrue(case['imported_geometry']['complete']);self.assertTrue(case['sketch_observer_preferences']['restored']);self.assertIsNotNone(live['document'])

    def test_metadata_does_not_bypass_reopened_health_hash_readonly_or_restore_failures(self):
        for options in ({'reopened_health':1},{'mutate_native':True},{'mutate_step':True},
                        {'reopen_readonly':False},{'save_error':1},{'restore_fail':'swImportFreeCurves'}):
            with self.subTest(options=options):
                case,exc,reads,app,live=self.roundtrip(**options)
                self.assertIsNotNone(exc);self.assertFalse(case.get('success',False));self.assertEqual(app.LoadFile4.call_count,1)
                if 'restore_fail' in options:self.assertFalse(case['sketch_observer_preferences']['restored'])
                else:self.assertTrue(case['sketch_observer_preferences']['restored'])


if __name__=='__main__':unittest.main()
