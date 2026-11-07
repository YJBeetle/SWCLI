from preference_guard_fakes import preference_peer
"""Portable tests execute the real fixed reader; they are not native calibration."""

from collections import Counter
from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
import inspect
import json
import os
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.document_annotations import ANNOTATION_FIELDS
from swcli.document_display_options import DISPLAY_FIELDS
from swcli.document_drafting_standard import (
    BASE_STANDARD_OPTIONS, CALIBRATED_DRAFTING_TRANSITIONS, DRAFTING_DEFAULTS_PROFILE,
    DRAFTING_STANDARDS, drafting_standard_observation,
)
from swcli.hosts import windows_document_drafting_standard as adapter
from swcli.hosts.native_trace import trace_native_request
from swcli.operation_schemas import OPERATION_CATALOG


class DocumentDraftingStandardTests(unittest.TestCase):
    def setUp(self):
        self.modified, self.stamp = False, 19
        self.native = {
            ('Integer', 13, 0): 7,
            ('Integer', 38, 0): 1, ('Integer', 39, 0): 3, ('Integer', 40, 0): 1,
            ('Toggle', 375, 0): False, ('Double', 113, 0): 0.00635,
            ('Integer', 265, 100): 1, ('Integer', 15, 100): 4,
            ('Toggle', 57, 0): False, ('Double', 30, 0): 0.1,
            ('Integer', 42, 0): 4, ('Integer', 43, 0): 1, ('Integer', 41, 0): 3,
            ('Integer', 145, 0): 33023, ('Integer', 146, 0): 16512,
            ('Integer', 148, 0): 0, ('Integer', 147, 0): 95,
            ('Toggle', 138, 0): True,
        }
        for option in (103, 301, 303, 302):
            self.native['Integer', 13, option] = 7
        self.font = SimpleNamespace(
            TypeFaceName='Arial', CharHeight=0.0035, CharHeightInPts=12,
            Bold=False, Italic=False, Underline=False, Strikeout=False,
            BackWards=False, UpsideDown=False, Vertical=False,
            WidthFactor=1.0, CharSpacingFactor=1.0, Escapement=0.0,
            LineSpacing=0.0015, LineLength=0.0, ObliqueAngle=0.0,
            IsHeightSpecifiedInPts=False,
        )
        self.extension = SimpleNamespace(GetUserPreferenceTextFormat=mock.Mock(return_value=self.font))
        for family in ('Integer', 'Double', 'Toggle'):
            setattr(self.extension, 'GetUserPreference'+family, mock.Mock(
                side_effect=lambda preference, option, family=family:self.native[family,preference,option]))
            setattr(self.extension, 'SetUserPreference'+family, mock.Mock(side_effect=self.apply))
        self.units = [0, 1, 0, 2, 0]
        self.document = SimpleNamespace(
            GetType=lambda:1, GetUpdateStamp=lambda:self.stamp,
            GetSaveFlag=lambda:self.modified, GetUnits=mock.Mock(spec=(),side_effect=lambda:tuple(self.units)),
            GetActiveConfiguration=lambda:SimpleNamespace(Name='Default'),
            IsOpenedReadOnly=lambda:False, IsOpenedViewOnly=lambda:False,
            SketchManager=SimpleNamespace(ActiveSketch=None), Extension=self.extension,
            SetSaveFlag=mock.Mock(side_effect=lambda:setattr(self,'modified',True)),
        )
        self.document.GetTitle = lambda: 'target'
        self.document.GetPathName = lambda: ''
        self.foreground=preference_peer()
        self.app=SimpleNamespace(ActiveDoc=self.foreground,
            IsSame=lambda first,second:int(first is second),ActivateDoc3=mock.Mock(),
            SetUserPreferenceIntegerValue=mock.Mock())

    def apply(self, preference, option, value):
        self.native['Integer',preference,option]=value
        for spec in BASE_STANDARD_OPTIONS.values():
            self.native['Integer',13,spec['option']]=value
        self.font.Bold=True
        return True

    def read(self):
        return adapter.read_document_drafting_standard_windows(app=self.app,document=self.document)

    def expected(self):
        result=self.read()
        self.assertTrue(result['ok'],result)
        return {key:deepcopy(result[key]) for key in ('standard','observed_defaults')}

    def reset_getters(self):
        for family in ('Integer','Double','Toggle'):
            getattr(self.extension,'GetUserPreference'+family).reset_mock()
        self.extension.GetUserPreferenceTextFormat.reset_mock()
        self.document.GetUnits.reset_mock()

    def edit(self, value='iso', expected=None, *, calibrated=True):
        if expected is None:expected=self.expected()
        transitions=tuple((kind,source,target,DRAFTING_DEFAULTS_PROFILE)
                          for kind in (1,2,3) for source,target in ((7,2),(2,7))) if calibrated else ()
        # Portable object fakes explicitly simulate the host-scope guard; these
        # tests supply no native Windows calibration evidence.
        with mock.patch.object(adapter,'CALIBRATED_DRAFTING_TRANSITIONS',transitions), mock.patch.object(
                adapter, '_require_calibrated_native_host', return_value=None):
            return adapter.set_document_drafting_standard_windows(
                app=self.app,document=self.document,value=value,expected_snapshot=expected)

    def assert_no_mutation(self):
        for family in ('Integer','Double','Toggle'):
            getattr(self.extension,'SetUserPreference'+family).assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.app.SetUserPreferenceIntegerValue.assert_not_called()

    def drawing(self):
        sketch,template=object(),object()
        sheet=SimpleNamespace(GetName=lambda:'Sheet1',GetTemplateSketch=lambda:template)
        view=SimpleNamespace(GetName2=lambda:'Sheet1',GetSketch=lambda:sketch,
                             GetReferencedModelName=lambda:'')
        self.document.GetType=lambda:3
        self.document.GetCurrentSheet=lambda:sheet
        self.document.GetFirstView=lambda:view
        self.document.GetEditSheet=lambda:True
        self.document.ActiveDrawingView=None
        self.document.SketchManager.ActiveSketch=sketch
        return template

    def test_no_callable_parameter_registered_operations_and_forced_uncalibrated_gate(self):
        for function in (adapter.read_document_drafting_standard_windows,adapter.set_document_drafting_standard_windows):
            self.assertNotIn('snapshot_reader',inspect.signature(function).parameters)
        self.assertIn('document.drafting-standard',OPERATION_CATALOG)
        self.assertIn('document.drafting-standard-set',OPERATION_CATALOG)
        self.assertTrue(OPERATION_CATALOG['document.drafting-standard'].selected_document)
        self.assertTrue(OPERATION_CATALOG['document.drafting-standard-set'].lease_guarded)
        self.assertEqual(OPERATION_CATALOG['document.drafting-standard-set'].parameters['x-swcli-context']['expected_update_stamp'],'required')
        result=self.edit(calibrated=False)
        self.assertFalse(result['ok'],result)
        self.assert_no_mutation()

    def test_exact_official_base_option_catalog(self):
        self.assertEqual({key:spec['option'] for key,spec in BASE_STANDARD_OPTIONS.items()},
            {'geometric_tolerance':103,'detail_view':301,'auxiliary_view':303,'section_view':302})
        self.assertEqual(DRAFTING_STANDARDS,{'ansi':1,'iso':2,'din':3,'jis':4,'bsi':5,'gost':6,'gb':7,'custom':8})

    def test_real_fixed_reader_schema_types_normalization_and_exact_getter_pairs(self):
        result=self.read();self.assertTrue(result['ok'],result)
        observed=result['observed_defaults']
        self.assertEqual(observed['profile'],'drafting-defaults-v1')
        self.assertEqual(observed['document_type'],1)
        self.assertEqual(observed['coverage']['annotations'],list(ANNOTATION_FIELDS))
        self.assertEqual(observed['coverage']['display'],list(DISPLAY_FIELDS))
        self.assertEqual(len(observed['annotation_font']['font']),17)
        self.assertEqual(len(observed['annotation_font']['native_font']),17)
        self.assertEqual(observed['annotation_font']['font']['height_mm'],3.5)
        self.assertEqual(observed['annotation_font']['native_font']['CharHeight'],0.0035)
        self.assertEqual(observed['annotations']['bent_leader.length_mm'],{'value':6.35,'native_value':0.00635})
        self.assertEqual(observed['display']['grid.major_spacing_mm'],{'value':100.0,'native_value':0.1})
        self.assertEqual(len(observed['length_units']['native_units']),5)
        integers=Counter(call.args for call in self.extension.GetUserPreferenceInteger.call_args_list)
        expected={(13,0),(13,103),(13,301),(13,303),(13,302),(38,0),(39,0),(40,0),
                  (265,100),(15,100),(42,0),(43,0),(41,0),(145,0),(146,0),(148,0),(147,0)}
        self.assertEqual(integers,Counter({pair:1 for pair in expected}))
        self.extension.GetUserPreferenceTextFormat.assert_called_once_with(19,0)
        self.document.GetUnits.assert_called_once()
        self.assert_no_mutation()

    def test_real_helpers_emit_flat_trace_41_model_36_drawing_boundaries(self):
        from swcli.hosts import (windows_document_annotation_fonts as font,
            windows_document_annotations as annotation,windows_document_display_options as display,
            windows_document_units as units, windows as windows)
        for drawing in (False,True):
            with self.subTest(drawing=drawing):
                self.setUp()
                if drawing:self.drawing()
                calls=[];active=False
                def traced(stage,name,call):
                    nonlocal active
                    self.assertFalse(active,'nested native trace wrapper')
                    active=True
                    try:result=call()
                    finally:active=False
                    calls.append((stage,name));return result
                with mock.patch.object(adapter,'native_call',side_effect=traced),\
                     mock.patch.object(font,'native_call',side_effect=traced),\
                     mock.patch.object(annotation,'native_call',side_effect=traced),\
                     mock.patch.object(display,'native_call',side_effect=traced),\
                     mock.patch.object(units,'native_call',side_effect=traced),\
                     mock.patch.object(windows,'native_call',side_effect=traced):
                    result=self.read()
                self.assertTrue(result['ok'],result)
                self.assertEqual(sum(stage!='read' for stage,_ in calls),36 if drawing else 41)
                self.assertEqual(sum(name.startswith('ITextFormat.') for _,name in calls),17)

    def test_drawing_real_reader_omits_plane_and_preserves_sheet_identity(self):
        self.drawing();result=self.read();self.assertTrue(result['ok'],result)
        observed=result['observed_defaults']
        self.assertEqual(len(observed['display']),5)
        self.assertEqual(observed['document_type'],3)
        for call in self.extension.GetUserPreferenceInteger.call_args_list:
            self.assertNotIn(call.args[0],(145,146,147,148))
        self.extension.GetUserPreferenceToggle.assert_any_call(57,0)
        self.assert_no_mutation()

    def test_actual_native_trace_records_are_flat_and_have_unique_ordered_terminals(self):
        for drawing in (False,True):
            with self.subTest(drawing=drawing):
                self.setUp()
                if drawing:self.drawing()
                stream=StringIO()
                with mock.patch.dict(os.environ,{'SWCLI_TRACE_NATIVE_CALLS':'1'}),redirect_stderr(stream):
                    with trace_native_request('portable-fixed-profile','document.drafting-standard'):
                        result=self.read()
                self.assertTrue(result['ok'],result)
                rows=[json.loads(line) for line in stream.getvalue().splitlines()]
                self.assertEqual((rows[0]['stage'],rows[0]['phase']),('operation','begin'))
                self.assertEqual((rows[-1]['stage'],rows[-1]['phase']),('operation','end'))
                active=None;sequence=0;data_getters=0
                for row in rows[1:-1]:
                    if row['phase']=='begin':
                        self.assertIsNone(active,'overlapping actual native trace records')
                        sequence+=1;self.assertEqual(row['sequence'],sequence)
                        active=(row['sequence'],row['stage'],row['call'])
                        data_getters+=int(row['stage']!='read')
                    else:
                        self.assertEqual(row['phase'],'end')
                        self.assertEqual((row['sequence'],row['stage'],row['call']),active)
                        active=None
                self.assertIsNone(active)
                self.assertEqual(data_getters,36 if drawing else 41)

    def test_base_custom_and_unknown_int32_remain_readable(self):
        self.native['Integer',13,103]=8;self.native['Integer',13,301]=999
        result=self.read();self.assertTrue(result['ok'],result)
        self.assertEqual(result['observed_defaults']['base_standards']['geometric_tolerance'],{'value':'custom','native_value':8})
        self.assertEqual(result['observed_defaults']['base_standards']['detail_view'],{'value':'other','native_value':999})
        self.assert_no_mutation()

    def test_invalid_native_types_in_each_real_domain_fail_closed(self):
        defects=(lambda:self.native.update({('Integer',13,0):True}),
            lambda:self.native.update({('Integer',13,103):2**31}),
            lambda:self.native.update({('Toggle',375,0):1}),
            lambda:self.native.update({('Double',30,0):float('nan')}),
            lambda:setattr(self.font,'Bold',1),lambda:self.units.__setitem__(0,True))
        for defect in defects:
            with self.subTest(defect=defect):
                self.setUp();defect();self.assertFalse(self.read()['ok']);self.assert_no_mutation()

    def test_incomplete_profile_cas_is_rejected_without_getters_or_setters(self):
        baseline=self.expected()
        defects=(lambda s:s.pop('standard'),lambda s:s['observed_defaults'].pop('length_units'),
            lambda s:s['observed_defaults']['annotation_font']['native_font'].pop('Bold'),
            lambda s:s['observed_defaults']['display'].pop('grid.display'),
            lambda s:s['observed_defaults']['base_standards'].pop('section_view'),
            lambda s:s['observed_defaults']['annotations'].pop('zero.leading'),
            lambda s:s['observed_defaults']['coverage']['display'].pop(),
            lambda s:s['observed_defaults'].update(profile='arbitrary-four-fake-dicts'))
        for defect in defects:
            with self.subTest(defect=defect):
                snapshot=deepcopy(baseline);defect(snapshot);self.reset_getters()
                result=self.edit(expected=snapshot);self.assertFalse(result['ok'],result)
                self.extension.GetUserPreferenceInteger.assert_not_called();self.assert_no_mutation()

    def test_whole_fixed_profile_cas_rejects_every_domain_drift_and_bool_int_alias(self):
        baseline=self.expected()
        defects=(lambda s:s['standard'].update(value='iso',native_value=2),
            lambda s:s['observed_defaults']['annotation_font']['native_font'].update(Bold=0),
            lambda s:s['observed_defaults']['annotations']['zero.leading'].update(native_value=2),
            lambda s:s['observed_defaults']['length_units']['native_units'].update(significant_digits=3),
            lambda s:s['observed_defaults']['display']['grid.display'].update(native_value=0),
            lambda s:s['observed_defaults']['base_standards']['section_view'].update(value='iso',native_value=2))
        for defect in defects:
            with self.subTest(defect=defect):
                snapshot=deepcopy(baseline);defect(snapshot)
                result=self.edit(expected=snapshot);self.assertFalse(result['ok'],result)
                self.assertEqual(result['error']['type'],'DocumentDraftingStandardConflict')
                self.assert_no_mutation()

    def test_expected_snapshot_cannot_be_rewritten_by_a_later_getter_to_hide_drift(self):
        expected=self.expected()
        def font(*args):
            self.font.Bold=True
            expected['observed_defaults']['annotation_font']['native_font']['Bold']=True
            expected['observed_defaults']['annotation_font']['font']['bold']=True
            return self.font
        self.extension.GetUserPreferenceTextFormat.side_effect=font
        result=self.edit(expected=expected)
        self.assertFalse(result['ok'],result)
        self.assertEqual(result['error']['type'],'DocumentDraftingStandardConflict')
        self.assert_no_mutation()

    def test_known_noop_has_complete_cas_and_zero_writes_even_without_calibration(self):
        result=self.edit(value='gb',calibrated=False)
        self.assertTrue(result['ok'],result);self.assertFalse(result['changed']);self.assert_no_mutation()

    def test_transition_gate_is_exact_kind_source_target_and_profile(self):
        expected=self.expected()
        for key in ((2,7,2,DRAFTING_DEFAULTS_PROFILE),(1,2,7,DRAFTING_DEFAULTS_PROFILE),(1,7,2,'other-profile')):
            with self.subTest(key=key),mock.patch.object(adapter,'CALIBRATED_DRAFTING_TRANSITIONS',(key,)):
                result=adapter.set_document_drafting_standard_windows(app=self.app,document=self.document,value='iso',expected_snapshot=expected)
                self.assertFalse(result['ok'],result);self.assert_no_mutation()

    def test_one_standard_setter_allows_observed_font_and_substandard_coupling(self):
        result=self.edit();self.assertTrue(result['ok'],result)
        self.assertTrue(result['observed_defaults_changed'])
        self.assertFalse(result['before']['observed_defaults']['annotation_font']['native_font']['Bold'])
        self.assertTrue(result['after']['observed_defaults']['annotation_font']['native_font']['Bold'])
        self.assertEqual(result['after'],result['final'])
        self.extension.SetUserPreferenceInteger.assert_called_once_with(13,0,2)
        self.document.SetSaveFlag.assert_called_once()

    def test_failed_false_nonbool_exception_never_retries_or_rolls_back(self):
        for returned in (False,1,None,RuntimeError('native failure')):
            with self.subTest(returned=returned):
                self.setUp();expected=self.expected()
                def failed(*args):
                    self.apply(*args)
                    if isinstance(returned,Exception):raise returned
                    return returned
                self.extension.SetUserPreferenceInteger.side_effect=failed
                result=self.edit(expected=expected);self.assertFalse(result['ok'],result)
                self.assertEqual(result['mutation'],{'attempted':True,'may_have_changed':True})
                self.extension.SetUserPreferenceInteger.assert_called_once_with(13,0,2)
                self.assertEqual(self.native['Integer',13,0],2);self.document.SetSaveFlag.assert_not_called()

    def test_true_setter_wrong_roundtrip_keeps_observation(self):
        self.extension.SetUserPreferenceInteger.side_effect=lambda *args:True
        result=self.edit();self.assertFalse(result['ok'],result)
        self.assertEqual(result['after']['standard']['native_value'],7)
        self.document.SetSaveFlag.assert_not_called()

    def test_custom_unknown_source_and_arbitrary_targets_never_write(self):
        for native in (8,999):
            self.native['Integer',13,0]=native
            result=self.edit();self.assertFalse(result['ok'],result);self.assert_no_mutation()
        self.native['Integer',13,0]=7;expected=self.expected()
        for value in ('custom','other','ISO','arbitrary.sldstd',2,True,None):
            result=self.edit(value=value,expected=expected);self.assertFalse(result['ok'],result);self.assert_no_mutation()

    def test_metadata_getter_foreground_or_edit_drift_cannot_be_hidden(self):
        for writing in (False,True):
            for editing in (False,True):
                with self.subTest(writing=writing,editing=editing):
                    self.setUp();expected=self.expected();self.reset_getters()
                    def stamp():
                        if editing:self.document.SketchManager.ActiveSketch=object()
                        else:self.app.ActiveDoc=object()
                        return self.stamp
                    self.document.GetUpdateStamp=stamp
                    result=self.edit(expected=expected) if writing else self.read()
                    self.assertFalse(result['ok'],result)
                    self.extension.GetUserPreferenceInteger.assert_not_called();self.assert_no_mutation()

    def test_readonly_transition_during_real_font_read_rejects_before_setter(self):
        for name in ('IsOpenedReadOnly','IsOpenedViewOnly'):
            with self.subTest(name=name):
                self.setUp();expected=self.expected()
                def font(*args):setattr(self.document,name,lambda:True);return self.font
                self.extension.GetUserPreferenceTextFormat.side_effect=font
                result=self.edit(expected=expected);self.assertFalse(result['ok'],result);self.assert_no_mutation()

    def test_active_model_sketch_or_drawing_format_blocks_actual_change(self):
        self.document.SketchManager.ActiveSketch=object()
        result=self.edit();self.assertFalse(result['ok'],result);self.assert_no_mutation()
        self.setUp();template=self.drawing();self.document.SketchManager.ActiveSketch=template
        result=self.edit();self.assertFalse(result['ok'],result);self.assert_no_mutation()

    def test_postsetter_getter_state_drift_is_not_repaired(self):
        expected=self.expected()
        def font(*args):
            if self.native['Integer',13,0]==2:self.stamp+=1
            return self.font
        self.extension.GetUserPreferenceTextFormat.side_effect=font
        result=self.edit(expected=expected);self.assertFalse(result['ok'],result)
        self.assertIn('after',result);self.document.SetSaveFlag.assert_not_called()
        self.extension.SetUserPreferenceInteger.assert_called_once()

    def test_final_fixed_profile_drift_never_triggers_second_saveflag(self):
        expected=self.expected();reads=0
        def font(*args):
            nonlocal reads
            reads+=1
            if reads==3:self.font.Italic=True
            return self.font
        self.extension.GetUserPreferenceTextFormat.side_effect=font
        result=self.edit(expected=expected);self.assertFalse(result['ok'],result)
        self.assertIn('final',result);self.document.SetSaveFlag.assert_called_once()
        self.extension.SetUserPreferenceInteger.assert_called_once()

    def test_already_dirty_document_needs_no_extra_saveflag(self):
        self.modified=True;result=self.edit();self.assertTrue(result['ok'],result)
        self.document.SetSaveFlag.assert_not_called()


if __name__=='__main__':unittest.main()
