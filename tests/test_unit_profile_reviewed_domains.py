"""Admission literals must exactly match the independently audited native source."""
import json
from pathlib import Path
import unittest
from swcli import document_unit_write_domains as admitted
from swcli import document_unit_profile as catalog

ROOT=Path(__file__).resolve().parents[1]

class ReviewedDomains(unittest.TestCase):
    def test_exact_original_archive_association_and_every_literal(self):
        audit=json.loads((ROOT/'docs/evidence/units-profile/write-checkpoints-42414478796/independent-audit.json').read_text())
        expected=tuple((r['document_type'],r['source_snapshot_sha256'],r['field'],r['native_target'],r['after_snapshot_sha256']) for r in audit['reviewable_domains'])
        self.assertTrue(audit['audit_success'])
        self.assertEqual(admitted.REVIEWED_UNIT_TRANSITIONS,expected)
        self.assertEqual(admitted.AUDITED_RUN,audit['run_id'])
        self.assertEqual(admitted.AUDITED_HEAD,audit['verified_head'])
        self.assertEqual(admitted.AUDITED_ZIP_SHA256,audit['zip_sha256'])
        self.assertEqual(admitted.AUDITED_REPORT_SHA256,audit['report_sha256'])
        self.assertEqual(admitted.CALIBRATED_UNIT_REVISION,audit['revision'])
        self.assertEqual(set(admitted.CALIBRATED_UNIT_CONFIGURATIONS),{(c['document_type'],c['configuration']) for c in audit['cases']})
        self.assertEqual(len(catalog.CALIBRATED_UNIT_WRITES),137)
        self.assertEqual(len(catalog.CALIBRATED_UNIT_SYSTEM_RESULTS),26)

    def test_any_unmeasured_revision_configuration_or_kind_stays_closed(self):
        for kind,config,revision in ((1,'Alternate','33.5.0'),(2,'Other','33.5.0'),(1,'Default','34.0.0'),(3,'Default','33.5.0'),(4,None,'33.5.0')):
            with self.subTest(kind=kind,config=config,revision=revision),self.assertRaises(ValueError):catalog.require_calibrated_context(kind,config,revision)
