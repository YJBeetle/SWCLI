"""Exact GB fixture discovery/wiring tests; no template is opened and no COM."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_document_properties_calibration as portable
import test_document_properties_calibration_watchdog as watchdog

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('docprops_templates', ROOT / 'scripts/ci/gate_support/document_property_templates.py')
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class ExactGBTemplates(unittest.TestCase):
    def installed(self, root):
        directory = root / 'install/data/templates'; directory.mkdir(parents=True)
        for name in ('gb_part.prtdot', 'gb_assembly.asmdot', 'gb.drwdot'):
            (directory / name).write_bytes(b'portable-template-not-native')
        return directory

    def test_explicit_installed_gb_bundle_beats_unconfigured_mbd_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); installed = self.installed(root)
            mbd = root / 'programdata/SOLIDWORKS/SOLIDWORKS 2025/templates/MBD'
            mbd.mkdir(parents=True); (mbd / 'part 0001mm and smaller.prtdot').write_bytes(b'ansi')
            selected = selector.templates(root / 'programdata', root / 'install')
            self.assertEqual({Path(value).parent for value in selected.values()}, {installed.resolve()})
            self.assertEqual(Path(selected['part']).name, 'gb_part.prtdot')

    def test_program_data_requires_exact_unique_names_in_templates_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); directory = root / 'programdata/SOLIDWORKS/SOLIDWORKS 2025/templates'; directory.mkdir(parents=True)
            for name in selector.NAMES.values(): (directory / name).write_bytes(b'portable')
            selected = selector.templates(root / 'programdata', root / 'install')
            self.assertEqual({Path(value).parent for value in selected.values()}, {directory.resolve()})
            duplicate = root / 'programdata/SOLIDWORKS/SOLIDWORKS 2024/templates'; duplicate.mkdir(parents=True)
            (duplicate / 'gb_part.prtdot').write_bytes(b'old')
            with self.assertRaisesRegex(RuntimeError, 'found 2'):
                selector.templates(root / 'programdata', root / 'install')

    def test_missing_gb_never_selects_mbd_and_records_failure_without_host(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); directory = root / 'programdata/SOLIDWORKS/SOLIDWORKS 2025/templates/MBD'; directory.mkdir(parents=True)
            (directory / 'part.prtdot').write_bytes(b'ansi')
            report = root / 'selection.json'
            with self.assertRaisesRegex(RuntimeError, 'no arbitrary fallback'):
                selector.main(['--program-data', str(root / 'programdata'), '--installation', str(root / 'install'), '--output', str(report)])
            import json
            recorded = json.loads(report.read_text())
            self.assertFalse(recorded['success']); self.assertIn('failure', recorded)

    def test_symlink_named_gb_is_not_an_installed_regular_template(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); installed = self.installed(root)
            target = root / 'not-a-trusted-template'; target.write_bytes(b'other')
            (installed / 'gb_part.prtdot').unlink()
            try:
                (installed / 'gb_part.prtdot').symlink_to(target)
            except OSError as error:
                self.skipTest('symbolic links unavailable: ' + str(error))
            with self.assertRaisesRegex(RuntimeError, 'found 0'):
                selector.templates(root / 'programdata', root / 'install')

    def test_explicit_model_paths_are_bound_to_exact_worker_authorization(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = SimpleNamespace(attach_pid=123, stage='standards', output=str(root / 'output'),
                swconst=None, drawing_template='gb_a4.drwdot', font_typeface=None, isolated_host=True,
                part_template='gb_part.prtdot', assembly_template='gb_assembly.asmdot')
            with patch.object(watchdog.driver, 'driver_site_packages', return_value=[]):
                config = watchdog.driver.worker_config(args, root / 'script.py', root, root / 'driver')
            argv = config['script_args']
            self.assertEqual(argv[argv.index('--part-template')+1], args.part_template)
            self.assertEqual(argv[argv.index('--assembly-template')+1], args.assembly_template)
            expected = watchdog.driver.expected_identity(config, 456, watchdog.driver.default_python())
            changed = {**expected, 'script_args': [value for value in argv if value != args.part_template]}
            self.assertFalse(watchdog.driver.exact_json(expected, changed))

    def test_creator_receives_explicit_path_without_global_preference_setter(self):
        for kind in ('part', 'assembly'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                template = Path(folder) / ('gb_part.prtdot' if kind == 'part' else 'gb_assembly.asmdot')
                template.write_bytes(b'portable-template')
                c = portable.fixture(); c.args.stage = 'read'; setattr(c.args, kind + '_template', str(template))
                seen = []
                def resolve(app, explicit, *, kind):
                    seen.append(explicit); return {'ok': True, 'path': explicit}
                def create(*, app, template):
                    seen.append(template); doc = portable.Doc(); app.docs.append(doc); return {'ok': True}, doc
                c.resolve_template = resolve; setattr(c, 'create_' + kind, create)
                c.save_new = lambda document, label, kind: {'path': 'portable-saved'}
                c.create(kind, 'explicit-template')
                self.assertEqual(seen, [str(template), str(template)])
