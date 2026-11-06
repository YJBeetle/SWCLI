"""Portable Notes observer checks, not native inheritance acceptance."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_document_font_scopes as portable

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_font_notes_observer', ROOT / 'scripts/ci/verify-font-scopes-inheritance.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class FontScopesInheritanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = portable.FontScopeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.font = deepcopy(self.fixture.fonts()['notes'])
        self.native = deepcopy(self.fixture.native['notes'])

    def annotation(self, text, native, use_doc, next_annotation=None):
        obj = portable.Format(native)
        return SimpleNamespace(GetType=lambda: 456, GetSpecificAnnotation=lambda: SimpleNamespace(GetText=lambda: text),
            GetNext3=lambda: next_annotation, GetTextFormatCount=lambda: 1, GetTextFormat=lambda index: obj,
            GetUseDocTextFormat=lambda index: use_doc)

    def document(self, *, kind=1, local_use_doc=False):
        local = self.annotation(observer.LABELS['local'], self.native, local_use_doc)
        inherited = self.annotation(observer.LABELS['inherited'], self.native, True, local)
        return SimpleNamespace(GetType=lambda: kind, GetFirstAnnotation2=lambda: inherited,
            GetFirstView=lambda: SimpleNamespace(GetFirstAnnotation3=lambda: inherited, GetNextView=lambda: None),
            GetTitle=lambda: 'generated', GetUpdateStamp=lambda: 7, GetSaveFlag=lambda: False,
            GetActiveConfiguration=lambda: SimpleNamespace(Name='Default'))

    def test_enumerates_models_and_drawing_views_using_distinct_official_paths(self):
        for kind in (1, 2, 3):
            calls = []
            def call(name, function):
                calls.append(name)
                return function()
            observed = observer.notes(self.document(kind=kind), {'swNote': 456}, call)
            self.assertEqual(set(observed), {'local', 'inherited'})
            self.assertEqual(len(observed['local']['font']), 17)
            self.assertFalse(observed['local']['use_document_font'])
            self.assertTrue(observed['inherited']['use_document_font'])
            self.assertIn('IView.GetFirstAnnotation3' if kind == 3 else 'IModelDoc2.GetFirstAnnotation2', calls)
            if kind == 3:
                self.assertNotIn('IModelDoc2.GetFirstAnnotation2', calls)

    def test_parameterless_com_members_may_be_exposed_as_properties(self):
        local = self.annotation(observer.LABELS['local'], self.native, False)
        inherited = self.annotation(observer.LABELS['inherited'], self.native, True, local)
        for annotation, label, next_value in ((inherited, 'inherited', local), (local, 'local', None)):
            annotation.GetType = 456
            annotation.GetSpecificAnnotation = SimpleNamespace(GetText=observer.LABELS[label])
            annotation.GetTextFormatCount = 1
            annotation.GetNext3 = next_value
        document = self.document()
        document.GetFirstAnnotation2 = inherited
        result = observer.notes(document, {'swNote': 456}, lambda name, function: function())
        self.assertEqual(set(result), {'local', 'inherited'})

    def test_inherited_note_requires_flag_styles_and_active_unit_height(self):
        value = dict(use_document_font=True, font=deepcopy(self.font))
        observer.check_inherited(value, self.font)
        for mutate in (lambda row: row.update(use_document_font=False),
                       lambda row: row['font'].update(typeface='Different'),
                       lambda row: row['font'].update(bold=True),
                       lambda row: row['font'].update(height_mm=4.0),
                       lambda row: row['font'].update(height_mode='points')):
            candidate = deepcopy(value)
            mutate(candidate)
            with self.assertRaises(RuntimeError):
                observer.check_inherited(candidate, self.font)

    def test_annotation_cycle_cannot_create_unbounded_observation(self):
        annotation = self.annotation('not-a-generated-note', self.native, False)
        annotation.GetNext3 = lambda: annotation
        document = self.document()
        document.GetFirstAnnotation2 = lambda: annotation
        with self.assertRaisesRegex(RuntimeError, 'bounded fixture limit'):
            observer.notes(document, {'swNote': 456}, lambda name, function: function())

    def prepare_reports(self, root):
        fixtures, gate = root / 'fixtures', root / 'gate'
        fixtures.mkdir()
        gate.mkdir()
        source = fixtures / 'annotations.SLDPRT'
        source.write_bytes(b'generated source')
        local = dict(use_document_font=False, font=deepcopy(self.font), native_font=deepcopy(self.native))
        seeded = dict(kind='part', source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), seed_notes={'local': local})
        (fixtures / 'report.json').write_text(json.dumps(dict(success=True, cases=[seeded])))
        saves = []
        for mode in ('height_mm', 'height_points'):
            path = gate / ('notes-' + mode + '.SLDPRT')
            path.write_bytes(('generated ' + mode).encode())
            saves.append(dict(path='D:\\runner\\' + path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                              reopened={'fonts': self.fixture.fonts()}))
        public = dict(success=True, evidence_kind='installed-public-cli-gate', selected_scope='notes',
                      font_scope_cases=[dict(format='SLDPRT', saves=saves)])
        (gate / 'font-scopes-public.json').write_text(json.dumps(public))
        return fixtures, gate

    def observe(self, root, *, local_use_doc=False):
        fixtures, gate = self.prepare_reports(root)
        doc = self.document(local_use_doc=local_use_doc)
        app = SimpleNamespace(CloseDoc=lambda title: None, GetDocumentCount=lambda: 0)
        opened = dict(ok=True, api_errors=0, api_warnings=0, read_only=True)
        with patch.object(observer, 'open_windows_document_with_handle', return_value=(opened, doc)) as opener, \
                patch.object(observer.fonts, '_read_fonts', return_value=({}, self.fixture.fonts(), {})):
            case = {}
            observer.observe(app, root, {'swNote': 456}, 'front', False, lambda name, fn: fn(), case, {},
                {'document': None}, profile_kind='part', fixture_dir=fixtures, gate_dir=gate)
        return case, opener

    def test_independent_readonly_observer_matches_public_digests_and_local_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            case, opener = self.observe(Path(temporary))
        self.assertTrue(case['success'])
        self.assertEqual(len(case['observations']), 2)
        self.assertEqual(opener.call_count, 2)
        self.assertTrue(all(call.kwargs['read_only'] is True for call in opener.call_args_list))

    def test_local_inheritance_flag_change_is_a_failed_observation(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(RuntimeError, 'full local Note font/flag'):
            self.observe(Path(temporary), local_use_doc=True)



if __name__ == '__main__':
    unittest.main()
