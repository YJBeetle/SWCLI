"""Reviewed exact system results never widen domains or scalar invariants."""
from copy import deepcopy
import unittest
from unittest import mock
import test_document_unit_profile as existing
from swcli import document_unit_profile as catalog
from swcli.hosts import windows_document_unit_profile as adapter


class SystemPolicyTests(existing.UnitProfileTests):
    # Reuse the actual native-adapter fake; these tests are not native evidence.
    def system_change(self, **kw):
        return self.edit('system', 'mmgs', **kw)

    def domain(self):
        return (1, catalog.fingerprint(self.expected), 'system', 5)

    def observed(self):
        after = deepcopy(self.expected)
        after['values']['system'] = catalog.observe('system', 5)
        after['linkage']['swUnitsTimeUnits'] = 7
        return after

    def system_set(self, *args):
        self.set_native(*args)
        self.linkage['swUnitsTimeUnits'] = 7
        return True

    def test_public_requires_both_domain_and_reviewed_after_before_set(self):
        domain = self.domain()
        for domains, results in (((), ()), ((domain,), ()), ((), ((domain, catalog.fingerprint(self.observed())),)),
                                  ((domain,), ((domain, 'bad'),)),
                                  ((domain,), ((domain, 'a'*64), (domain, 'a'*64)))):
            with self.subTest(domains=domains, results=results), mock.patch.object(adapter, 'CALIBRATED_UNIT_WRITES', domains), mock.patch.object(catalog, 'CALIBRATED_UNIT_SYSTEM_RESULTS', results):
                result = self.system_change()
                self.assertFalse(result['ok'], result)
                self.assertEqual(result['mutation'], dict(attempted=False, may_have_changed=False))
                self.assert_no_write()

    def test_reviewed_complete_linkage_result_permits_exact_system_only(self):
        domain = self.domain()
        self.document.Extension.SetUserPreferenceInteger.side_effect = self.system_set
        with mock.patch.object(adapter, 'CALIBRATED_UNIT_WRITES', (domain,)), mock.patch.object(catalog, 'CALIBRATED_UNIT_SYSTEM_RESULTS', ((domain, catalog.fingerprint(self.observed())),)):
            result = self.system_change()
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['unit_profile'], self.observed())
        self.document.Extension.SetUserPreferenceInteger.assert_called_once_with(263, 0, 5)
        self.document.SetSaveFlag.assert_called_once_with()

    def test_one_linkage_mismatch_is_partial_without_dirty_mark_retry_or_rollback(self):
        domain = self.domain()
        self.document.Extension.SetUserPreferenceInteger.side_effect = self.system_set
        wrong = self.observed();wrong['linkage']['swUnitsTimeUnits'] = 8
        with mock.patch.object(adapter, 'CALIBRATED_UNIT_WRITES', (domain,)), mock.patch.object(catalog, 'CALIBRATED_UNIT_SYSTEM_RESULTS', ((domain, catalog.fingerprint(wrong)),)):
            result = self.system_change()
        self.assertFalse(result['ok'], result)
        self.assertEqual(result['mutation'], dict(attempted=True, may_have_changed=True))
        self.assertIs(result['native_return_value'], True)
        self.assertEqual(result['observed'], self.observed())
        self.document.Extension.SetUserPreferenceInteger.assert_called_once()
        self.document.SetSaveFlag.assert_not_called()

    def test_all_snapshot_members_are_part_of_reviewed_system_result(self):
        after = self.observed()
        for group in ('values', 'native_units', 'linkage'):
            for field in after[group]:
                wrong = deepcopy(after)
                old = wrong[group][field]
                if group == 'values':
                    wrong[group][field] = catalog.observe(field, old['native_value']+1)
                else:wrong[group][field] = not old if type(old) is bool else old+1
                with self.subTest(group=group, field=field), self.assertRaises(RuntimeError):
                    catalog.verify_system_after(self.expected, wrong, 5, catalog.fingerprint(after))

    def test_unplanned_system_pair_cannot_be_enabled_even_by_test_domain(self):
        domain = (1, catalog.fingerprint(self.expected), 'system', 3)
        with mock.patch.object(adapter, 'CALIBRATED_UNIT_WRITES', (domain,)):
            result = self.edit('system', 'ips', calibration=True)
        self.assertFalse(result['ok'], result)
        self.assert_no_write()

    def test_scalar_public_domain_does_not_admit_non_target_drift(self):
        domain = (1, catalog.fingerprint(self.expected), 'linear.unit', 3)
        def change(*args):
            self.set_native(*args);self.linkage['swUnitsTimeUnits'] += 1;return True
        self.document.Extension.SetUserPreferenceInteger.side_effect = change
        with mock.patch.object(adapter, 'CALIBRATED_UNIT_WRITES', (domain,)):
            result = self.edit()
        self.assertFalse(result['ok'], result)
        self.assertEqual(result['mutation'], dict(attempted=True, may_have_changed=True))
        self.document.SetSaveFlag.assert_not_called()

    def test_production_domains_stay_empty(self):
        self.assertEqual(catalog.CALIBRATED_UNIT_WRITES, ())
        self.assertEqual(catalog.CALIBRATED_UNIT_SYSTEM_RESULTS, ())

    def test_scalar_getunits_target_must_roundtrip_together(self):
        def change(*args):
            returned=self.set_native(*args)
            self.units=(999,*self.units[1:])
            return returned
        self.document.Extension.SetUserPreferenceInteger.side_effect=change
        result=self.edit(calibration=True)
        self.assertFalse(result['ok'],result)
        self.assertEqual(result['mutation'],dict(attempted=True,may_have_changed=True))
        self.document.SetSaveFlag.assert_not_called()
