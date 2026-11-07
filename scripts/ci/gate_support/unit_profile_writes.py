"""Finite private native diagnostics. Reports never enable public write domains."""
from copy import deepcopy
import hashlib
from pathlib import Path
import os
import shutil

from swcli.document_unit_profile import FIELDS, SYSTEMS, target, typed_key, fingerprint
from swcli.hosts import windows_document_unit_profile as adapter
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_custom_properties import _state
from swcli.hosts.windows_feature_inspection import _same
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_parts import create_part_windows_with_handle


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_native_targets(enums):
    required = {
        'swUnitSystem_e': {'swUnitSystem_CGS':1,'swUnitSystem_MKS':2,'swUnitSystem_IPS':3,'swUnitSystem_Custom':4,'swUnitSystem_MMGS':5},
        'swLengthUnit_e': {'swMM':0,'swMETER':2,'swINCHES':3},
        'swAngleUnit_e': {'swDEGREES':0,'swRADIANS':3},
        'swUnitsMassPropMass_e': {'swUnitsMassPropMass_Grams':2,'swUnitsMassPropMass_Kilograms':3},
        'swUnitsMassPropVolume_e': {'swUnitsMassPropVolume_Millimeters3':4,'swUnitsMassPropVolume_Meters3':6},
    }
    for family, members in required.items():
        for name, value in members.items():
            observed = enums.get(family, {}).get(name)
            require(type(observed) is int and observed == value, 'actual swconst write target differs: '+name)


def scalar_targets(field, source):
    """All existing catalog candidates, with the current value last (if present)."""
    require(field in FIELDS and field != 'system', 'scalar field required')
    candidates = FIELDS[field].get('targets', tuple(range(9)))
    return tuple(v for v in candidates if target(field, v) != source) + tuple(
        v for v in candidates if target(field, v) == source)


def system_targets(source):
    """Exactly eight directed MMGS spokes; preserve the actual starting system."""
    require(type(source) is int and source in SYSTEMS.values(), 'known source system required')
    spokes = tuple(v for v in SYSTEMS.values() if v != SYSTEMS['mmgs'])
    route = []
    if source != SYSTEMS['mmgs']:
        route.append('mmgs')
    for code in spokes:
        if code != source:
            route.extend((next(k for k, v in SYSTEMS.items() if v == code), 'mmgs'))
    if source != SYSTEMS['mmgs']:
        route.append(next(k for k, v in SYSTEMS.items() if v == source))
    return tuple(route)


def custom_preparation(source):
    require(type(source) is int and source in SYSTEMS.values(), 'known source system required')
    if source == SYSTEMS['custom']:return ()
    return ('custom',) if source == SYSTEMS['mmgs'] else ('mmgs', 'custom')


def changed_members(before, after):
    return {group: {key: dict(before=before[group][key], after=after[group][key])
                    for key in before[group] if typed_key(before[group][key]) != typed_key(after[group][key])}
            for group in ('values', 'native_units', 'linkage')}


def require_changed(result, before, field, value):
    require(result.get('ok') is True and result.get('changed') is True
            and result.get('mutation') == dict(attempted=True, may_have_changed=True)
            and result.get('native_return_value') is True
            and typed_key(result.get('before')) == typed_key(before)
            and result['unit_profile']['values'][field]['native_value'] == target(field, value),
            'private changed write failed; preserve first error/partial and stop')
    require(before['values'][field]['native_value'] != target(field, value),
            'noop cannot count as changed-write calibration')


class Calibration:
    def __init__(self, *, app, document, front, case, output, suffix, call, persist, geometry, compare):
        self.app, self.document, self.front = app, document, front
        self.case, self.output, self.suffix = case, output, suffix
        self.call, self.persist, self.geometry, self.compare = call, persist, geometry, compare
        self.case['write_steps'] = []
        self.baseline_geometry = case.get('geometry_before')

    def q(self, obj, name):
        return self.call(name, lambda: _com_value(obj, name))

    def same(self, first, second):
        return self.call('SldWorks.IsSame', lambda: _same(self.app, first, second))

    def context(self):
        opened = self.q(self.app, 'GetDocuments')
        require(type(opened) in (list, tuple), 'unreadable owned document catalog')
        active = self.q(self.app, 'ActiveDoc')
        require(self.front is not None and self.same(active, self.front),
                'calibration target must remain in background')
        require(len(opened) == 2 and all(any(self.same(obj, item) for item in opened)
                for obj in (self.document, self.front)), 'owned fixture catalog drifted')
        return dict(target_state=list(_state(self.document)),
                    target_identity=list(adapter._identity(self.document)),
                    peer_state=list(_state(self.front)), peer_identity=list(adapter._identity(self.front)))

    def read(self, document=None):
        result = self.call('read-write-calibration-profile', lambda:
            adapter.read_document_unit_profile_windows(app=self.app, document=self.document if document is None else document))
        if result.get('ok') is not True:
            self.case['first_read_failure']=result;self.persist()
        require(result.get('ok') is True, 'native profile read failed; no replacement getter')
        return result['unit_profile']

    def close(self, document):
        identity = adapter._identity(document)
        documents = self.q(self.app, 'GetDocuments')
        require(any(self.same(document, obj) for obj in documents)
                and sum(self.q(obj, 'GetTitle') == identity[0] for obj in documents) == 1,
                'close target identity/title is not uniquely owned')
        survivors = [(obj, list(_state(obj)), list(adapter._identity(obj))) for obj in documents if not self.same(document, obj)]
        self.persist()
        self.call('close-unique-owned-write-fixture', lambda: self.app.CloseDoc(identity[0]))
        remaining = self.q(self.app, 'GetDocuments') or ()
        # Do not call native IsSame/getters on the now-closed COM handle.
        require(len(remaining) == len(survivors)
                and not any(self.q(obj, 'GetTitle') == identity[0] for obj in remaining)
                and all(any(self.same(obj, item) for item in remaining)
                        and list(_state(obj)) == state and list(adapter._identity(obj)) == name
                        for obj, state, name in survivors),
                'owned close changed catalog or a surviving document')

    def save(self, path, step):
        step['save'] = self.call('save-distinct-unit-target', lambda:
            save_as_native_windows(str(path), document=self.document))
        self.persist()
        result = step['save']
        require(result.get('ok') is True and result['save_errors'] == 0
                and result['save_warnings'] is None and not self.q(self.document, 'GetSaveFlag'),
                'native changed target save failed')
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def open(self, path, readonly, step, label):
        result, document = self.call(label, lambda:
            open_windows_document_with_handle(str(path), app=self.app, read_only=readonly))
        step[label] = result
        self.persist()
        require(result.get('ok') is True and document is not None
                and result['api_errors'] == result['api_warnings'] == 0
                and self.q(document, 'IsOpenedReadOnly') is readonly
                and self.q(document, 'GetSaveFlag') is False,
                'planned native reopen failed; no retry')
        require(Path(self.q(document, 'GetPathName')) == path, 'native reopen path mismatch')
        return document

    def measure(self, step, label):
        if self.baseline_geometry is not None:
            context = self.context() if self.front is not None else list(_state(self.document))
            observed = self.geometry(self.document, step, label)
            self.compare(self.baseline_geometry, observed, step, 'comparison_'+label,
                         self.persist, 'unit changed write altered geometry')
            after = self.context() if self.front is not None else list(_state(self.document))
            require(after == context, 'measurement changed exact state/context')

    def step(self, field, value, role):
        before = self.read()
        require(before['values'][field]['native_value'] != target(field, value),
                'planned changed target is already current')
        context = self.context()
        require(context['target_state'][2] is False, 'each changed source must start clean')
        directory = self.output / ('kind-'+str(before['document_type'])) / ('step-%03d' % (len(self.case['write_steps'])+1))
        directory.mkdir(parents=True, exist_ok=False)
        source_path = directory / ('source.'+self.suffix)
        current_path = Path(context['target_identity'][1])
        current_hash = hashlib.sha256(current_path.read_bytes()).hexdigest()
        with current_path.open('rb') as source, source_path.open('xb') as copy:
            shutil.copyfileobj(source, copy)
            copy.flush();os.fsync(copy.fileno())
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        require(source_hash == current_hash, 'source copy differs from saved native bytes')
        step = dict(success=False, role=role, field=field, value=value, native_target=target(field, value),
                    before=deepcopy(before), before_fingerprint=fingerprint(before), context_before=context,
                    source_file=str(source_path.relative_to(self.output)), source_sha256=source_hash,
                    source_original_path=str(current_path), source_original_sha256=current_hash)
        self.case['write_steps'].append(step)
        # Durable complete source, identities, planned target and native hashes BEFORE mutation.
        self.persist()
        step['result'] = self.call('private-single-unit-set', lambda:
            adapter._calibrate_unit_profile(self.app, self.document, field, value, before))
        if step['result'].get('ok') is not True:step['first_business_error']=deepcopy(step['result'].get('error'))
        self.persist()
        require_changed(step['result'], before, field, value)
        after = step['after'] = step['result']['unit_profile']
        step['after_fingerprint'] = fingerprint(after)
        step['changed_members'] = changed_members(before, after)
        observed = step['context_after'] = self.context()
        self.persist()
        require(observed['target_identity'] == context['target_identity']
                and observed['target_state'][0] == context['target_state'][0]
                and observed['target_state'][3] == context['target_state'][3]
                and observed['target_state'][2] is True
                and observed['peer_state'] == context['peer_state']
                and observed['peer_identity'] == context['peer_identity'],
                'changed unit setter altered identity/context/foreground')
        require(typed_key(self.read()) == typed_key(after) and self.context() == observed,
                'changed unit readback drifted from guarded post-state')
        self.measure(step, 'geometry_after_write')
        target_path = directory / ('target.'+self.suffix)
        step['target_file'] = str(target_path.relative_to(self.output))
        self.persist()
        step['target_sha256'] = self.save(target_path, step)
        self.persist()
        require(typed_key(self.read()) == typed_key(after), 'save changed complete unit profile')
        require(hashlib.sha256(current_path.read_bytes()).hexdigest() == current_hash
                and hashlib.sha256(source_path.read_bytes()).hexdigest() == source_hash,
                'changed save overwrote original/source native file')
        self.close(self.document)
        self.close(self.front)
        self.front = None
        require(self.q(self.app, 'GetDocumentCount') == 0, 'owned write fixture catalog not empty')
        self.document = self.open(target_path, True, step, 'reopen_readonly')
        step['readonly_profile'] = self.read()
        self.persist()
        require(typed_key(step['readonly_profile']) == typed_key(after),
                'changed profile did not persist exactly on readonly reopen')
        state = list(_state(self.document))
        step['readonly_refusal'] = self.call('readonly-changed-unit-refusal', lambda:
            adapter.set_document_unit_profile_windows(app=self.app, document=self.document,
                field=field, value=value, expected_snapshot=after))
        self.persist()
        require(step['readonly_refusal'].get('ok') is False
                and step['readonly_refusal'].get('mutation') == dict(attempted=False, may_have_changed=False)
                and step['readonly_refusal'].get('error', {}).get('type') == 'ValueError',
                'readonly write did not fail before mutation')
        require(list(_state(self.document)) == state and typed_key(self.read()) == typed_key(after),
                'readonly refusal changed exact state/profile')
        self.measure(step, 'geometry_readonly')
        self.close(self.document)
        require(hashlib.sha256(target_path.read_bytes()).hexdigest() == step['target_sha256']
                and hashlib.sha256(source_path.read_bytes()).hexdigest() == source_hash,
                'readonly verification changed native file bytes')
        self.document = self.open(target_path, False, step, 'reopen_writable_for_next_case')
        require(typed_key(self.read()) == typed_key(after)
                and hashlib.sha256(target_path.read_bytes()).hexdigest() == step['target_sha256'],
                'planned writable reopen changed profile or native bytes')
        front_result, self.front = self.call('create-owned-next-foreground', lambda:
            create_part_windows_with_handle(app=self.app))
        step['next_foreground'] = front_result
        self.persist()
        require(front_result.get('ok') is True and self.front is not None, 'next foreground creation failed')
        self.context()
        step['success'] = True
        self.persist()

    def run(self):
        self.case['planned_scalar_targets'] = {field:list(FIELDS[field].get('targets',tuple(range(9)))) for field in FIELDS if field!='system'}
        self.case['initial_profile'] = self.read()
        self.persist()
        # Preserve observed source; this preparation is a recorded native mutation,
        # never a silent source normalization or a public automatic Custom switch.
        for value in custom_preparation(self.case['initial_profile']['values']['system']['native_value']):
            self.step('system', value, 'explicit-custom-preparation')
        for field in FIELDS:
            if field == 'system':
                continue
            before = self.read()
            for value in scalar_targets(field, before['values'][field]['native_value']):
                self.step(field, value, 'scalar')
        source = self.read()['values']['system']['native_value']
        for value in system_targets(source):
            self.step('system', value, 'system-spoke')
        self.close(self.document)
        self.close(self.front)
        require(self.q(self.app, 'GetDocumentCount') == 0, 'finished write calibration catalog not empty')
        for step in self.case['write_steps']:
            for label in ('source','target'):
                require(hashlib.sha256((self.output/step[label+'_file']).read_bytes()).hexdigest() == step[label+'_sha256'],
                        'final native artifact hash differs: '+step[label+'_file'])
        self.case['write_diagnostic_success'] = True
        self.persist()
