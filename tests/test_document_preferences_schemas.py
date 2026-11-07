"""Schema/semantic faults against real fixed-reader snapshots, without COM."""

from copy import deepcopy
import importlib.util
import inspect
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from swcli.document_annotation_fonts import (
    ANNOTATION_FONT_MEMBERS, annotation_font_native_normalizations, annotation_font_snapshot,
)
from swcli.document_display_options import DISPLAY_FIELDS, display_observation
from swcli.document_drafting_standard import drafting_defaults_coverage
from swcli import document_preferences_schemas as schemas


OPS=("document.annotation-font", "document.annotation-font-set", "document.display-options",
     "document.display-option-set", "document.drafting-standard", "document.drafting-standard-set")


class DocumentPreferenceSchemaTests(unittest.TestCase):
    def setUp(self):
        # Use the existing native-object fake, then call the real fixed reader.
        # No four-domain stand-in or hand-written successful snapshot is used.
        path=Path(__file__).with_name('test_document_drafting_standard.py')
        spec=importlib.util.spec_from_file_location('_drafting_schema_fixture',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.fixture=module.DocumentDraftingStandardTests();self.fixture.setUp()
        self.snapshot=self.fixture.expected()
        self.font=deepcopy(self.snapshot['observed_defaults']['annotation_font']['font'])
        self.native=deepcopy(self.snapshot['observed_defaults']['annotation_font']['native_font'])
        self.options=deepcopy(self.snapshot['observed_defaults']['display'])

    def reject_schema(self, value, schema):
        with self.assertRaises(ValueError):schemas.validate_preference_schema(value,schema)

    def reject_request(self, op, request):
        with self.assertRaises(ValueError):schemas.validate_document_preference_request(op,request)

    def font_result(self, *, normalized=False):
        after=deepcopy(self.native);after['TypeFaceName']='Times New Roman'
        if normalized:after['CharHeightInPts']=14
        return {'ok':True,'field':'typeface','before':deepcopy(self.font),'native_before':deepcopy(self.native),
            'font':annotation_font_snapshot(after),'native_font':after,'changed':True,
            'mutation':{'attempted':True,'may_have_changed':True},
            'native_normalizations':annotation_font_native_normalizations(self.native,after,'TypeFaceName')}

    def test_all_schemas_are_valid_json_schema_and_return_fresh_values(self):
        for op in OPS:
            first=schemas.document_preference_parameters(op)
            Draft202012Validator.check_schema(first)
            fields,required=schemas.document_preference_result_fields(op)
            Draft202012Validator.check_schema({'type':'object','properties':fields,'required':list(required),'additionalProperties':False})
            first['description']='caller-mutated'
            self.assertNotIn('description',schemas.document_preference_parameters(op))
        for factory in (schemas.annotation_font_schema,schemas.native_annotation_font_schema,
                        schemas.annotation_font_pair_schema,schemas.native_font_normalizations_schema,
                        schemas.display_options_schema,schemas.drafting_snapshot_schema):
            Draft202012Validator.check_schema(factory())

    def test_pure_module_has_no_reverse_registry_or_host_imports(self):
        source=inspect.getsource(schemas)
        self.assertNotIn('from .result_schemas',source)
        self.assertNotIn('from .operation_schemas',source)
        self.assertNotIn('from .hosts',source)
        self.assertNotIn('import swcli.hosts',source)

    def test_read_parameters_accept_only_empty_object(self):
        for op in OPS[::2]:
            schemas.validate_document_preference_request(op,{})
            self.reject_request(op,{'arbitrary':True})
            self.reject_request(op,[])

    def test_real_fixed_snapshots_for_all_three_kinds_validate_and_coverage_is_pure(self):
        for kind in (1,2,3):
            with self.subTest(kind=kind):
                self.fixture.setUp()
                if kind==3:self.fixture.drawing()
                else:self.fixture.document.GetType=lambda:kind
                snapshot=self.fixture.expected()
                schemas.validate_drafting_snapshot_values(snapshot)
                schemas.validate_document_preference_request('document.drafting-standard-set',
                    {'value':'iso','expected_snapshot':snapshot})
                self.assertEqual(snapshot['observed_defaults']['coverage'],drafting_defaults_coverage(kind))
                self.assertEqual(len(snapshot['observed_defaults']['display']),5 if kind==3 else 10)
        coverage=drafting_defaults_coverage(1);coverage['display'].pop()
        self.assertEqual(len(drafting_defaults_coverage(1)['display']),10)

    def test_both_17_field_font_snapshots_validate_with_zero_inactive_points(self):
        raw=deepcopy(self.native);raw['CharHeightInPts']=0
        pair={'font':annotation_font_snapshot(raw),'native_font':raw}
        schemas.validate_preference_schema(pair,schemas.annotation_font_pair_schema())
        schemas.validate_document_preference_result_values('document.annotation-font',{'ok':True,**pair})
        pair['native_font']['IsHeightSpecifiedInPts']=True
        self.reject_schema(pair,schemas.annotation_font_pair_schema())

    def test_font_write_fields_have_precise_types_and_complete_expected_font(self):
        targets={'typeface':'Arial Unicode MS','height_mm':4.5,'height_points':14,
                 'bold':True,'italic':False,'underline':True,'strikeout':False}
        for field,value in targets.items():
            schemas.validate_document_preference_request('document.annotation-font-set',
                {'field':field,'value':value,'expected_font':self.font})
        bad=(('typeface',''),('typeface',' Arial'),('typeface','Arial\n'),('typeface','\x01Arial'),
             ('typeface','Arial\x7f'),('height_mm',True),('height_mm',0),('height_mm',float('nan')),
             ('height_mm',5e-324),('height_points',14.0),('height_points',True),('height_points',0),
             ('bold',1),('italic','false'),('backwards',True),('height_mode','points'))
        for field,value in bad:
            with self.subTest(field=field,value=value):
                self.reject_request('document.annotation-font-set',{'field':field,'value':value,'expected_font':self.font})
        for defect in (lambda x:x.pop('expected_font'),lambda x:x['expected_font'].pop('bold'),
                       lambda x:x['expected_font'].update(unknown=0),lambda x:x.update(native_path='file.sldstd')):
            request={'field':'bold','value':True,'expected_font':deepcopy(self.font)};defect(request)
            self.reject_request('document.annotation-font-set',request)

    def test_font_read_preserves_unknown_empty_typeface_without_enabling_empty_write(self):
        raw=deepcopy(self.native);raw['TypeFaceName']=''
        result={'ok':True,'font':annotation_font_snapshot(raw),'native_font':raw}
        schemas.validate_document_preference_result_values('document.annotation-font',result)
        self.reject_request('document.annotation-font-set',{'field':'typeface','value':'','expected_font':result['font']})

    def test_font_native_normalized_mismatch_is_semantically_rejected(self):
        result={'ok':True,'font':deepcopy(self.font),'native_font':deepcopy(self.native)}
        for defect in (lambda x:x['font'].update(height_mm=4.0),
                       lambda x:x['font'].update(height_mode='points'),
                       lambda x:x['font'].update(height_points=14),
                       lambda x:x['native_font'].update(TypeFaceName='Other')):
            changed=deepcopy(result);defect(changed)
            with self.assertRaises(ValueError):schemas.validate_document_preference_result_values('document.annotation-font',changed)

    def test_native_normalizations_are_required_bounded_and_verified_against_raw_fields(self):
        for normalized in (False,True):
            result=self.font_result(normalized=normalized)
            schemas.validate_document_preference_result_values('document.annotation-font-set',result)
        result=self.font_result(normalized=True)
        self.assertEqual(result['native_normalizations'][0]['member'],'CharHeightInPts')
        defects=(lambda x:x.pop('native_normalizations'),lambda x:x.update(native_normalizations=[]),
            lambda x:x['native_normalizations'][0].update(before=True),
            lambda x:x['native_normalizations'][0].update(after=14.0),
            lambda x:x['native_normalizations'][0].update(reason='font-conversion'),
            lambda x:x['native_normalizations'][0].update(member='Bold'),
            lambda x:x['native_normalizations'][0].update(extra=True),
            lambda x:x['native_normalizations'].append(deepcopy(x['native_normalizations'][0])),
            lambda x:x['native_font'].update(CharHeight=0.004))
        for defect in defects:
            with self.subTest(defect=defect):
                changed=deepcopy(result);defect(changed)
                with self.assertRaises(ValueError):schemas.validate_document_preference_result_values('document.annotation-font-set',changed)

    def test_charheight_normalization_uses_native_positive_finite_numbers_without_conversion_guess(self):
        schema=schemas.native_font_normalizations_schema()
        valid=[{'member':'CharHeight','before':0.003,'after':0.004,'reason':'inactive-height-representation'}]
        schemas.validate_preference_schema(valid,schema)
        for value in (True,0,-1,float('inf'),float('nan')):
            bad=deepcopy(valid);bad[0]['after']=value;self.reject_schema(bad,schema)

    def test_display_all_ten_fields_support_correct_write_and_expected_domains(self):
        targets={'grid.display':True,'grid.major_spacing_mm':10.0,'grid.minor_lines_per_major':10,
            'grid.snap_points_per_minor':5,'virtual_sharp.style':'plus','plane.front_face_color':0x123456,
            'plane.back_face_color':0x654321,'plane.intersection_line_color':0,
            'plane.transparency':25,'plane.show_intersections':False}
        for field,value in targets.items():
            request={'field':field,'value':value,'expected_value':self.options[field]['value']}
            schemas.validate_document_preference_request('document.display-option-set',request)
        for field in ('plane.front_face_color','plane.transparency','grid.minor_lines_per_major'):
            schemas.validate_document_preference_request('document.display-option-set',
                {'field':field,'value':targets[field],'expected_value':-2147483648})
        self.reject_request('document.display-option-set',{'field':'virtual_sharp.style','value':'plus','expected_value':'other'})
        for field,value in (('grid.display',1),('grid.minor_lines_per_major',1.0),('grid.snap_points_per_minor',True),
            ('grid.major_spacing_mm',0),('grid.major_spacing_mm',float('inf')),('grid.major_spacing_mm',5e-324),
            ('virtual_sharp.style','other'),('plane.transparency',101),('plane.front_face_color',16777216)):
            self.reject_request('document.display-option-set',{'field':field,'value':value,'expected_value':self.options[field]['value']})
        for bad in ({'field':'grid.display','value':True},
                    {'field':'grid.display','value':True,'expected_value':False,'preference':57}):
            self.reject_request('document.display-option-set',bad)

    def test_display_read_unknown_enum_is_other_with_exact_int32_raw(self):
        options=deepcopy(self.options);options['virtual_sharp.style']=display_observation('virtual_sharp.style',999)
        schemas.validate_document_preference_result_values('document.display-options',{'ok':True,'options':options})
        for defect in (lambda x:x['virtual_sharp.style'].update(native_value=999.0),
                       lambda x:x['virtual_sharp.style'].update(native_value=True),
                       lambda x:x['virtual_sharp.style'].update(native_value=3),
                       lambda x:x['grid.major_spacing_mm'].update(value=0.1)):
            changed=deepcopy(options);defect(changed)
            with self.assertRaises(ValueError):schemas.validate_document_preference_result_values('document.display-options',{'ok':True,'options':changed})

    def test_display_document_applicability_is_exact_10_or_5_no_partial_model(self):
        self.fixture.drawing();snapshot=self.fixture.expected();drawing=snapshot['observed_defaults']['display']
        schemas.validate_document_preference_result_values('document.display-options',{'ok':True,'document':{'type':3},'options':drawing})
        for options in (self.options,{**drawing,'plane.transparency':self.options['plane.transparency']}):
            with self.assertRaises(ValueError):schemas.validate_document_preference_result_values('document.display-options',{'ok':True,'document':{'type':3},'options':options})
        partial=deepcopy(self.options);partial.pop('grid.display')
        self.reject_schema(partial,schemas.display_options_schema())

    def test_drafting_target_is_one_of_seven_named_standards_not_custom_or_paths(self):
        for value in ('ansi','iso','din','jis','bsi','gost','gb'):
            schemas.validate_document_preference_request('document.drafting-standard-set',{'value':value,'expected_snapshot':self.snapshot})
        for value in ('custom','other','ISO','x.sldstd',7,True):
            self.reject_request('document.drafting-standard-set',{'value':value,'expected_snapshot':self.snapshot})
        self.reject_request('document.drafting-standard-set',{'value':'iso'})

    def test_nested_snapshot_extra_missing_wrong_profile_kind_and_coverage_are_rejected(self):
        paths=(('observed_defaults','coverage'),('observed_defaults','annotations'),
            ('observed_defaults','annotation_font','font'),('observed_defaults','annotation_font','native_font'),
            ('observed_defaults','length_units','native_units'),('observed_defaults','display'),
            ('observed_defaults','base_standards'),('observed_defaults','base_standards','detail_view'))
        for path in paths:
            for extra in (False,True):
                with self.subTest(path=path,extra=extra):
                    snapshot=deepcopy(self.snapshot);node=snapshot
                    for key in path:node=node[key]
                    if extra:node['extra']=False
                    else:node.pop(next(iter(node)))
                    with self.assertRaises(ValueError):schemas.validate_drafting_snapshot_values(snapshot)
        for defect in (lambda x:x.update(extra=True),lambda x:x['observed_defaults'].update(profile='other'),
            lambda x:x['observed_defaults'].update(document_type=True),lambda x:x['observed_defaults'].update(document_type=1.0),
            lambda x:x['observed_defaults'].update(document_type=3),
            lambda x:x['observed_defaults']['coverage']['base_standards']['detail_view'].update(option=302)):
            snapshot=deepcopy(self.snapshot);defect(snapshot)
            with self.assertRaises(ValueError):schemas.validate_drafting_snapshot_values(snapshot)

    def test_snapshot_native_bool_int_float_and_normalization_faults_are_rejected(self):
        defects=(lambda x:x['standard'].update(native_value=7.0),
            lambda x:x['observed_defaults']['base_standards']['detail_view'].update(native_value=True),
            lambda x:x['observed_defaults']['annotation_font']['font'].update(height_points=12.0),
            lambda x:x['observed_defaults']['annotation_font']['native_font'].update(Bold=0),
            lambda x:x['observed_defaults']['length_units']['native_units'].update(round_to_fraction=False),
            lambda x:x['observed_defaults']['length_units'].update(decimal_places=5),
            lambda x:x['observed_defaults']['annotations']['bent_leader.length_mm'].update(value=0.00635),
            lambda x:x['observed_defaults']['annotations']['arrow.edge_vertex'].update(value='dot'),
            lambda x:x['observed_defaults']['display']['grid.major_spacing_mm'].update(native_value=float('nan')))
        for defect in defects:
            snapshot=deepcopy(self.snapshot);defect(snapshot)
            with self.assertRaises(ValueError):schemas.validate_drafting_snapshot_values(snapshot)

    def test_snapshot_unknown_base_and_unknown_length_enum_remain_observable(self):
        self.fixture.native['Integer',13,301]=77;self.fixture.units[0]=99
        snapshot=self.fixture.expected();schemas.validate_drafting_snapshot_values(snapshot)
        self.assertEqual(snapshot['observed_defaults']['base_standards']['detail_view']['value'],'other')
        self.assertEqual(snapshot['observed_defaults']['length_units']['length_unit'],'other')
        self.assertEqual(len(snapshot['observed_defaults']['length_units']['native_units']),5)

    def test_success_result_requires_all_owned_fields_but_partial_failure_is_allowed(self):
        font=self.font_result();schemas.validate_document_preference_result_values('document.annotation-font-set',font)
        failed={'ok':False,'field':'typeface','before':self.font,'native_before':self.native,
            'mutation':{'attempted':True,'may_have_changed':True}}
        schemas.validate_document_preference_result_values('document.annotation-font-set',failed)
        for key in ('font','native_font','native_normalizations','mutation'):
            broken=deepcopy(font);broken.pop(key)
            with self.assertRaises(ValueError):schemas.validate_document_preference_result_values('document.annotation-font-set',broken)
        standard={'ok':True,**self.snapshot}
        schemas.validate_document_preference_result_values('document.drafting-standard',standard)
        with self.assertRaises(ValueError):schemas.validate_document_preference_result_values('document.drafting-standard',{'ok':True,'standard':self.snapshot['standard']})
        with self.assertRaises(ValueError):schemas.validate_document_preference_result_values('document.drafting-standard',{'ok':True,'document':{'type':3},**self.snapshot})


if __name__=='__main__':unittest.main()
