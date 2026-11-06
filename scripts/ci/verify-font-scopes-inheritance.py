"""Owned Notes fixtures/observer for a separate public CLI font gate.

Seed creates only generated fixtures. Observe opens public outputs read-only.
No attachment, native retry, rollback, or host restart; use the hard watchdog.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath

from swcli.font_snapshot import FONT_MEMBERS, font_snapshot
from swcli.hosts import windows_document_font_scopes as fonts
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_custom_properties import _state
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows

spec = importlib.util.spec_from_file_location('_font_notes_fixture_base', Path(__file__).with_name('prepare-annotation-fixtures.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
harness = fixtures.harness
require = harness.checked
LABELS = {'inherited': 'SWCLI_FONT_SCOPES_INHERITED', 'local': 'SWCLI_FONT_SCOPES_LOCAL'}


def note_enum(pythoncom, path):
    library = pythoncom.LoadTypeLib(str(path))
    found = []
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attr = info.GetTypeAttr()
        if attr.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attr.cVars):
            value = info.GetVarDesc(offset)
            if info.GetDocumentation(value[0])[0] == 'swNote':
                found.append(value.value)
    require(len(found) == 1 and type(found[0]) is int, 'official swNote enum missing/ambiguous')
    return found[0]


def snapshot(annotation, call):
    use_doc = call('IAnnotation.GetUseDocTextFormat', lambda: annotation.GetUseDocTextFormat(0))
    require(type(use_doc) is bool, 'Notes inheritance flag is unreadable')
    count = call('IAnnotation.GetTextFormatCount', lambda: _com_value(annotation, 'GetTextFormatCount'))
    require(type(count) is int and count == 1, 'generated plain Note must have one text format')
    obj = call('IAnnotation.GetTextFormat', lambda: annotation.GetTextFormat(0))
    require(obj is not None, 'generated Note text format is missing')
    native = {member: call('ITextFormat.' + member + '.get', lambda member=member: fonts._read_member(obj, member))
              for member in FONT_MEMBERS.values()}
    return {'use_document_font': use_doc, 'font': font_snapshot(native), 'native_font': native}


def notes(document, constants, call):
    found = {}
    views = []
    if _com_value(document, 'GetType') == 3:
        view = call('IModelDoc2.GetFirstView', lambda: _com_value(document, 'GetFirstView'))
        while view is not None:
            require(len(views) < 100, 'drawing view enumeration exceeded bounded fixture limit')
            views.append(view)
            view = call('IView.GetNextView', lambda: _com_value(view, 'GetNextView'))
        heads = [call('IView.GetFirstAnnotation3', lambda view=view: _com_value(view, 'GetFirstAnnotation3')) for view in views]
    else:
        heads = [call('IModelDoc2.GetFirstAnnotation2', lambda: _com_value(document, 'GetFirstAnnotation2'))]
    total = 0
    for annotation in heads:
        while annotation is not None:
            total += 1
            require(total <= 1000, 'annotation enumeration exceeded bounded fixture limit')
            kind = call('IAnnotation.GetType', lambda: _com_value(annotation, 'GetType'))
            if kind == constants['swNote']:
                note = call('IAnnotation.GetSpecificAnnotation', lambda: _com_value(annotation, 'GetSpecificAnnotation'))
                text = call('INote.GetText', lambda: _com_value(note, 'GetText'))
                for label, expected in LABELS.items():
                    if text == expected:
                        require(label not in found, 'duplicate generated Note label')
                        found[label] = snapshot(annotation, call)
            annotation = call('IAnnotation.GetNext3', lambda: _com_value(annotation, 'GetNext3'))
    require(found.keys() == LABELS.keys(), 'both generated inheritance/local Notes are required')
    return found


def check_inherited(observation, default):
    require(observation['use_document_font'] is True, 'inheriting Note lost its UseDoc flag')
    observed = observation['font']
    for field in ('typeface', 'bold', 'italic', 'underline', 'strikeout', 'height_mode'):
        require(observed[field] == default[field], 'inheriting Note did not follow default ' + field)
    active = 'height_points' if default['height_mode'] == 'points' else 'height_mm'
    require(observed[active] == default[active], 'inheriting Note did not follow active height')


def close(app, document, call):
    title = _com_value(document, 'GetTitle')
    call('close-owned-Notes-document', lambda: app.CloseDoc(title))


def seed(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind, drawing_template):
    raw = output / 'raw'
    raw.mkdir(exist_ok=True)
    case.update(kind=profile_kind, fixture_seed_only=True)
    fixtures.prepare_case(app, raw, constants, plane, reverse, call, case.setdefault('fixture', {}),
                          report, live, profile_kind=profile_kind, drawing_template=drawing_template)
    source = Path(case['fixture']['path'])
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    opened, document = call('open-owned-Notes-fixture', lambda: open_windows_document_with_handle(str(source), app=app))
    live['document'] = document
    require(opened['ok'] and opened['api_errors'] == opened['api_warnings'] == 0, 'Notes fixture open failed')
    _, defaults_before, _ = fonts._read_fonts(document, constants)
    for label, text in LABELS.items():
        note = call('IModelDoc2.InsertNote', lambda: document.InsertNote(text))
        require(note is not None, 'generated Note insertion failed')
        annotation = call('INote.GetAnnotation', lambda: _com_value(note, 'GetAnnotation'))
        require(annotation is not None, 'generated Note has no annotation')
        if label == 'inherited':
            require(call('IAnnotation.SetTextFormat.UseDoc', lambda: annotation.SetTextFormat(0, True, None)) is True,
                    'generated inheriting Note setup failed')
        else:
            obj = call('IAnnotation.GetTextFormat.local-seed', lambda: annotation.GetTextFormat(0))
            require(call('IAnnotation.SetTextFormat.local', lambda: annotation.SetTextFormat(0, False, obj)) is True,
                    'generated local Note setup failed')
            obj = call('IAnnotation.GetTextFormat.local', lambda: annotation.GetTextFormat(0))
            call('ITextFormat.CharHeightInPts.local-seed', lambda: setattr(obj, 'CharHeightInPts', 20))
            require(call('IAnnotation.SetTextFormat.local-20pt', lambda: annotation.SetTextFormat(0, False, obj)) is True,
                    'generated 20-point local Note setup failed')
    _, defaults_after, _ = fonts._read_fonts(document, constants)
    require(defaults_after == defaults_before, 'local Note seeding changed a document default')
    path = output / source.name
    saved = case['seed_save'] = call('save-owned-Notes-source', lambda: save_as_native_windows(str(path), document=document))
    require(saved['ok'] and saved['api_saved'] is True and saved['save_errors'] == 0
            and saved['save_warnings'] is None and saved['document']['modified'] is False, 'Notes source save failed')
    close(app, document, call)
    live['document'] = None
    opened, document = call('reopen-owned-Notes-source-readonly', lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
    live['document'] = document
    require(opened['ok'] and opened['api_errors'] == opened['api_warnings'] == 0 and opened['read_only'] is True, 'Notes source readonly reopen failed')
    state = _state(document)
    observed = case['seed_notes'] = notes(document, constants, call)
    _, defaults, _ = fonts._read_fonts(document, constants)
    case['seed_fonts'] = defaults
    check_inherited(observed['inherited'], defaults['notes'])
    require(observed['local']['use_document_font'] is False and observed['local']['font']['height_mode'] == 'points'
            and observed['local']['font']['height_points'] == 20, 'local Note font did not persist')
    require(_state(document) == state and state[2] is False, 'Notes source readback changed document state')
    require(hashlib.sha256(source.read_bytes()).hexdigest() == original_hash, 'Notes seeding changed its raw source')
    case.update(source_path=str(path), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), success=True)
    close(app, document, call)
    live['document'] = None
    require(_com_value(app, 'GetDocumentCount') == 0, 'Notes fixture preparation left documents open')


def observe(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind, fixture_dir, gate_dir):
    seed_report = json.loads((fixture_dir / 'report.json').read_text())
    public_report = json.loads((gate_dir / 'font-scopes-public.json').read_text())
    require(seed_report.get('success') is True and public_report.get('success') is True
            and public_report.get('evidence_kind') == 'installed-public-cli-gate'
            and public_report.get('selected_scope') == 'notes', 'successful Notes source/public reports required')
    seeded = next(row for row in seed_report['cases'] if row.get('kind') == profile_kind)
    suffix = fixtures.KINDS[profile_kind][1]
    public = next(row for row in public_report['font_scope_cases'] if row.get('format') == suffix)
    case.update(kind=profile_kind, observations=[], source_sha256=seeded['source_sha256'])
    source = fixture_dir / ('annotations.' + suffix)
    require(hashlib.sha256(source.read_bytes()).hexdigest() == seeded['source_sha256'], 'public gate changed its Notes source')
    require(len(public['saves']) == 2, 'both public height-mode saves are required')
    for saved in public['saves']:
        path = gate_dir / PureWindowsPath(saved['path']).name
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == saved['sha256'], 'public saved file digest mismatch')
        opened, document = call('open-public-Notes-output-readonly', lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
        live['document'] = document
        require(opened['ok'] and opened['api_errors'] == opened['api_warnings'] == 0 and opened['read_only'] is True, 'public Notes output did not open readonly')
        state = _state(document)
        observed = notes(document, constants, call)
        _, defaults, _ = fonts._read_fonts(document, constants)
        require(defaults == saved['reopened']['fonts'], 'independent output font defaults differ from public CLI readback')
        check_inherited(observed['inherited'], defaults['notes'])
        require(observed['local'] == seeded['seed_notes']['local'], 'document default write changed the full local Note font/flag')
        require(_state(document) == state and state[2] is False, 'independent Notes observation changed document state')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == saved['sha256'], 'independent Notes observation changed saved bytes')
        case['observations'].append(dict(path=str(path), sha256=saved['sha256'], notes=observed, fonts=defaults))
        close(app, document, call)
        live['document'] = None
    case['success'] = True
    require(_com_value(app, 'GetDocumentCount') == 0, 'Notes observer left documents open')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--swconst', required=True, type=Path)
    parser.add_argument('--drawing-template', required=True, type=Path)
    parser.add_argument('--phase', required=True, choices=('seed', 'observe'))
    parser.add_argument('--fixture-dir', type=Path)
    parser.add_argument('--gate-dir', type=Path)
    args = parser.parse_args(argv)
    if args.phase == 'observe':
        require(args.fixture_dir is not None and args.gate_dir is not None, 'observer needs source/public evidence directories')
    args.output_dir.mkdir()
    original = harness.read_constants
    def constants(pythoncom, path):
        return {**original(pythoncom, path), **fonts.read_font_constants(pythoncom, path), 'swNote': note_enum(pythoncom, path)}
    harness.read_constants = constants
    def runner(app, output, enum, *arguments, **keywords):
        if args.phase == 'seed':
            return seed(app, output, enum, *arguments, **keywords, drawing_template=args.drawing_template)
        return observe(app, output, enum, *arguments, **keywords, fixture_dir=args.fixture_dir, gate_dir=args.gate_dir)
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False, case_runner=runner,
        case_plan=[(kind, 'front', False) for kind in fixtures.KINDS], diagnostic_case='notes-inheritance-' + args.phase)


if __name__ == '__main__':
    raise SystemExit(main())
