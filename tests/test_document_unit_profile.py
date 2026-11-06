"""Whole-profile CAS and guards; mock results never authorize native writes."""
from copy import deepcopy
import json
import unittest
from unittest import mock
import test_document_units as legacy
import test_document_annotations as annotations
from swcli.document_unit_profile import FIELDS, LINKAGE, snapshot, validate_snapshot, target, fingerprint
from swcli.hosts import windows_document_unit_profile as adapter
from swcli.operation_schemas import validate_operation_request, OPERATION_CATALOG
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.daemon.documents import DocumentLeaseConflict
from swcli.result_schemas import validate_operation_result
from swcli.cli import build_parser, _typed_operation

class UnitProfileTests(unittest.TestCase):
    apply_units = legacy.DocumentUnitsTests.apply_units
    mark_modified = legacy.DocumentUnitsTests.mark_modified

    def setUp(self):
        legacy.DocumentUnitsTests.setUp(self)
        self.peer_configuration=legacy.SimpleNamespace(Name='Foreground')
        self.foreground.GetActiveConfiguration=lambda:self.peer_configuration
        self.raw = {f: (4 if f == 'system' else 2 if f == 'mass_properties.mass_unit' else 4 if f == 'mass_properties.volume_unit' else 3 if 'precision' in f else 0) for f in FIELDS}
        self.linkage = {n: False if family == 'Toggle' else 0 for n, (family, _) in LINKAGE.items()}
        self.document.Extension = mock.Mock()
        self.document.Extension.GetUserPreferenceInteger.side_effect = lambda p, o: next((self.raw[f] for f,s in FIELDS.items() if s['id']==p), self.linkage.get(next((n for n,(family,i) in LINKAGE.items() if family=='Integer' and i==p), ''), 0))
        self.document.Extension.GetUserPreferenceToggle.side_effect = lambda p,o: next(self.linkage[n] for n,(family,i) in LINKAGE.items() if family=='Toggle' and i==p)
        self.document.Extension.SetUserPreferenceInteger.side_effect = self.set_native
        self.expected = self.snap()
    def snap(self):
        return snapshot(1, self.raw, self.units, self.linkage)
    def set_native(self, preference, option, value):
        field = next(f for f,s in FIELDS.items() if s['id']==preference)
        self.raw[field] = value
        if field == 'linear.unit': self.units = (value, *self.units[1:])
        if field == 'linear.precision': self.units = (*self.units[:3], value, self.units[4])
        return True
    def edit(self, field='linear.unit', value='inch', expected=None, calibration=False):
        if calibration:
            return adapter._calibrate_unit_profile(self.app, self.document, field, value, self.expected if expected is None else expected)
        return adapter.set_document_unit_profile_windows(app=self.app, document=self.document, field=field, value=value, expected_snapshot=self.expected if expected is None else expected)
    def operation(self, name, values=None, **kw):
        return execute_operation(self.app, name, values or {}, documents=self.documents, session_id='writer', document_id=self.entry.document_id, **kw)
    def assert_no_write(self):
        self.document.Extension.SetUserPreferenceInteger.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.document.SetUnits.assert_not_called()
    def test_read_background_unknown_and_raw_five(self):
        self.raw['angular.unit']=999
        self.units=(7,0,8,5,-1)
        r=self.operation('document.unit-profile')
        self.assertTrue(r['ok'],r)
        validate_operation_result('document.unit-profile',r)
        self.assertEqual(r['unit_profile']['values']['angular.unit'],dict(value='other',native_value=999))
        self.assertEqual(list(r['unit_profile']['native_units'].values()),list(self.units))
        self.assertIs(self.app.ActiveDoc,self.foreground)
        self.assert_no_write()
    def test_all_public_changes_fail_closed(self):
        for f in FIELDS:
            value=next((v for v in FIELDS[f].get('targets',()) if FIELDS[f]['enum'][v]!=self.raw[f]),0)
            r=self.edit(f,value)
            self.assertFalse(r['ok'],r)
            self.assertFalse(r['mutation']['attempted'])
        self.assert_no_write()
    def test_noop_validated_through_registry(self):
        r=self.operation('document.unit-profile-set',dict(field='linear.unit',value='mm',expected_snapshot=self.expected),lease_id=self.lease['lease_id'],expected_update_stamp=7)
        self.assertTrue(r['ok'],r)
        self.assertFalse(r['changed'])
        validate_operation_result('document.unit-profile-set',r)
        self.assert_no_write()
    def test_required_lease_and_stamp_route(self):
        values=dict(field='linear.unit',value='mm',expected_snapshot=self.expected)
        for kw in ({},{'expected_update_stamp':7},{'lease_id':self.lease['lease_id']},{'lease_id':self.lease['lease_id'],'expected_update_stamp':6}):
            with self.subTest(kw=kw),self.assertRaises((ValueError,DocumentLeaseConflict,DocumentUpdateConflict)):
                self.operation('document.unit-profile-set',values,**kw)
        self.assertTrue(OPERATION_CATALOG['document.unit-profile-set'].lease_guarded)
        self.assert_no_write()
    def test_every_nontarget_member_participates_in_cas(self):
        for group in ('values','native_units','linkage'):
            for name in self.expected[group]:
                changed=deepcopy(self.expected)
                if group=='values':
                    changed[group][name]['native_value']=999
                    changed[group][name]['value']='other'
                else:
                    old=changed[group][name]
                    changed[group][name]=not old if type(old)is bool else old+1
                r=self.edit(expected=changed,calibration=True)
                self.assertFalse(r['ok'],r)
                self.assertFalse(r['mutation']['attempted'])
        self.assert_no_write()
    def test_canonical_types_and_unknown_preserved(self):
        for change in (lambda s:s.update(document_type=True),lambda s:s['values']['linear.unit'].update(value='inch'),lambda s:s['native_units'].update(length_unit=False),lambda s:s['values'].update(extra={})):
            s=deepcopy(self.expected);change(s)
            with self.assertRaises(ValueError): validate_snapshot(s)
        self.assertEqual(fingerprint(self.expected),fingerprint(deepcopy(self.expected)))
    def test_property_shaped_raw_units(self):
        self.document.GetUnits=self.units
        self.assertTrue(adapter.read_document_unit_profile_windows(app=self.app,document=self.document)['ok'])
    def test_unreadable_getter_stops_before_writes(self):
        self.document.GetUnits=lambda:(False,1,8,3,0)
        self.assertFalse(self.edit(calibration=True)['ok'])
        self.assert_no_write()
    def test_readonly_and_viewonly(self):
        for name in ('IsOpenedReadOnly','IsOpenedViewOnly'):
            with mock.patch.object(self.document,name,return_value=True): self.assertFalse(self.edit(calibration=True)['ok'])
        self.assert_no_write()
    def test_pre_read_drift_rejects(self):
        for drift in (lambda:setattr(self.app,'ActiveDoc',self.document),lambda:setattr(self.configuration,'Name','Other'),lambda:setattr(self.document,'IsOpenedReadOnly',lambda:True)):
            with self.subTest(drift=drift):
                self.setUp()
                self.document.GetUnits=lambda:(drift() or self.units)
                self.assertFalse(self.edit(calibration=True)['ok'])
                self.assert_no_write()
    def test_single_calibration_set_and_dirty_once(self):
        r=self.edit(calibration=True)
        self.assertTrue(r['ok'],r)
        self.document.Extension.SetUserPreferenceInteger.assert_called_once_with(47,0,3)
        self.document.SetSaveFlag.assert_called_once_with()
        self.document.SetUnits.assert_not_called()
    def test_false_and_exception_are_partial_no_retry(self):
        for failure in (False,RuntimeError('native failure')):
            self.setUp()
            if failure is False:self.document.Extension.SetUserPreferenceInteger.side_effect=lambda *a:False
            else:self.document.Extension.SetUserPreferenceInteger.side_effect=failure
            r=self.edit(calibration=True)
            self.assertFalse(r['ok'],r)
            self.assertEqual(r['mutation'],dict(attempted=True,may_have_changed=True))
            if failure is False:self.assertIs(r['native_return_value'],False)
            self.document.Extension.SetUserPreferenceInteger.assert_called_once()
            self.document.SetSaveFlag.assert_not_called()
    def test_post_getter_stamp_and_dirty_drift_not_adopted(self):
        for dirty in (False,True):
            self.setUp();self.modified=True;self.stamp=7
            self.document.GetUpdateStamp=lambda:self.stamp
            calls=0
            def read():
                nonlocal calls
                calls+=1
                if calls==2:
                    if dirty:self.modified=False
                    else:self.stamp=99
                return self.units
            self.document.GetUnits=read
            r=self.edit(calibration=True)
            self.assertFalse(r['ok'],r)
            self.assertIn('observed',r)
            self.document.SetSaveFlag.assert_not_called()
    def test_linkage_drift_after_set_is_partial(self):
        def change(*args):
            self.set_native(*args);self.linkage['swUnitsTimeUnits']=8;return True
        self.document.Extension.SetUserPreferenceInteger.side_effect=change
        r=self.edit(calibration=True)
        self.assertFalse(r['ok'],r)
        self.assertTrue(r['mutation']['may_have_changed'])
        self.document.SetSaveFlag.assert_not_called()
    def test_existing_dirty_no_duplicate_mark(self):
        self.modified=True
        self.assertTrue(self.edit(calibration=True)['ok'])
        self.document.SetSaveFlag.assert_not_called()
    def test_drawing_context_is_preserved_and_drift_refuses(self):
        annotations.DocumentAnnotationTests.drawing_context(self)
        self.expected=snapshot(3,self.raw,self.units,self.linkage)
        r=self.edit(calibration=True)
        self.assertTrue(r['ok'],r)
        self.assertIs(self.document.SketchManager.ActiveSketch,self.sheet_sketch)
        self.setUp()
        annotations.DocumentAnnotationTests.drawing_context(self)
        self.expected=snapshot(3,self.raw,self.units,self.linkage)
        def drift():
            self.sheet_name='Other'
            return self.units
        self.document.GetUnits=drift
        self.assertFalse(self.edit(calibration=True)['ok'])
        self.assert_no_write()

    def test_setter_cannot_clear_existing_dirty(self):
        self.modified=True
        def change(*args):
            self.set_native(*args);self.modified=False;return True
        self.document.Extension.SetUserPreferenceInteger.side_effect=change
        r=self.edit(calibration=True)
        self.assertFalse(r['ok'],r)
        self.document.Extension.SetUserPreferenceInteger.assert_called_once()
        self.document.SetSaveFlag.assert_not_called()

    def test_cli_and_contract_reject_private_bypass(self):
        args=build_parser().parse_args(['document','unit-profile-set','linear.precision','8','--if-snapshot',json.dumps(self.expected),'--if-update-stamp','7','--lease','token','--json'])
        op=_typed_operation(args)
        self.assertEqual(op[0],'document.unit-profile-set')
        self.assertEqual(op[1]['value'],8)
        for v in (True,-1,9,'8'):
            with self.assertRaises(ValueError):target('linear.precision',v)
        with self.assertRaises(ValueError):validate_operation_request(op[0],dict(op[1],calibration=True))



class UnitProfilePeerGuards(unittest.TestCase):
    setUp=UnitProfileTests.setUp
    apply_units=UnitProfileTests.apply_units
    mark_modified=UnitProfileTests.mark_modified
    set_native=UnitProfileTests.set_native
    snap=UnitProfileTests.snap
    edit=UnitProfileTests.edit
    assert_no_write=UnitProfileTests.assert_no_write
    def test_same_active_object_peer_drift_is_partial_without_rollback(self):
        for member,new in (('GetUpdateStamp',999),('GetSaveFlag',True),('GetTitle','Other foreground'),('GetPathName','C:\\other.SLDPRT')):
            with self.subTest(member=member):
                self.setUp()
                def change(*args):
                    returned=self.set_native(*args)
                    setattr(self.foreground,member,lambda:new)
                    return returned
                self.document.Extension.SetUserPreferenceInteger.side_effect=change
                result=self.edit(calibration=True)
                self.assertFalse(result['ok'],result)
                self.assertEqual(result['mutation'],dict(attempted=True,may_have_changed=True))
                self.assertIs(result['native_return_value'],True)
                self.assertIs(self.app.ActiveDoc,self.foreground)
                self.assertEqual(getattr(self.foreground,member)(),new)
                self.document.Extension.SetUserPreferenceInteger.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()
    def test_pre_read_peer_drift_never_reaches_setter(self):
        def read():
            self.foreground.GetUpdateStamp=lambda:999
            return self.units
        self.document.GetUnits=read
        result=self.edit(calibration=True)
        self.assertFalse(result['ok'],result)
        self.assert_no_write()
    def test_active_target_can_change_own_stamp_and_dirty_without_false_peer_refusal(self):
        self.app.ActiveDoc=self.document
        def change(*args):
            returned=self.set_native(*args)
            self.document.GetUpdateStamp=lambda:99
            return returned
        self.document.Extension.SetUserPreferenceInteger.side_effect=change
        self.assertTrue(self.edit(calibration=True)['ok'])

    def test_peer_configuration_catalog_and_target_identity_after_set_refuse(self):
        for scenario in ('peer-config','closed-peer','target-identity'):
            with self.subTest(scenario=scenario):
                self.setUp()
                def change(*args):
                    returned=self.set_native(*args)
                    if scenario=='peer-config':self.peer_configuration.Name='Other'
                    elif scenario=='closed-peer':self.app.GetDocuments=lambda:(self.document,)
                    else:self.document.GetPathName=lambda:'C:\\changed.SLDPRT'
                    return returned
                self.document.Extension.SetUserPreferenceInteger.side_effect=change
                result=self.edit(calibration=True)
                self.assertFalse(result['ok'],result)
                self.assertEqual(result['mutation'],dict(attempted=True,may_have_changed=True))
                self.document.Extension.SetUserPreferenceInteger.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()
    def test_peer_drift_during_dirty_mark_remains_partial(self):
        def mark():
            self.mark_modified()
            self.foreground.GetTitle=lambda:'Changed on dirty mark'
        self.document.SetSaveFlag.side_effect=mark
        result=self.edit(calibration=True)
        self.assertFalse(result['ok'],result)
        self.assertEqual(result['mutation'],dict(attempted=True,may_have_changed=True))
        self.assertEqual(self.foreground.GetTitle(),'Changed on dirty mark')
        self.document.Extension.SetUserPreferenceInteger.assert_called_once()
        self.document.SetSaveFlag.assert_called_once()
    def test_reader_rejects_same_pointer_peer_identity_drift_without_restoration(self):
        def read():
            self.foreground.GetTitle=lambda:'Changed during read'
            return self.units
        self.document.GetUnits=read
        result=adapter.read_document_unit_profile_windows(app=self.app,document=self.document)
        self.assertFalse(result['ok'],result)
        self.assertIs(self.app.ActiveDoc,self.foreground)
        self.assertEqual(self.foreground.GetTitle(),'Changed during read')
        self.assert_no_write()

if __name__=='__main__':unittest.main()
