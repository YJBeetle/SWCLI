"""Public readonly assembly targets; explicitly no mate-tree/write authority."""
from copy import deepcopy
import json

from .entity_contracts import _FACE, _object

TARGET_ID = {"type": "string", "pattern": "^at-[0-9a-f]{32}$"}
SNAPSHOT_ID = {"type": "string", "pattern": "^as-[0-9a-f]{32}$"}
_TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
_INT = {"type": "integer", "minimum": 0}
_STATE = _object({"configuration": _TEXT, "update_stamp": _INT, "path": _TEXT,
                  "modified": {"const": False}, "readonly": {"const": True},
                  "view_only": {"const": False}})
_GEOMETRY = deepcopy(_FACE)
_GEOMETRY['oneOf'] = _GEOMETRY['oneOf'][:2]
for _variant in _GEOMETRY['oneOf']:
    _variant['properties'].pop('entity_id')
    _variant['required'].remove('entity_id')
_FACE_ROW = _object({"index": _INT, "geometry": _GEOMETRY,
                     "reference_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                     "exact_native_owner": {"const": True}})
_COMPONENT = _object({"name": _TEXT, "path": _TEXT, "source_state": _STATE,
    "transform": {"type": "array", "items": {"type": "number"}, "minItems": 16, "maxItems": 16},
    "fixed": {"type": "boolean"}, "suppression": {"enum": [2, 3], "type": "integer"},
    "source_face_count": {"type": "integer", "minimum": 1, "maximum": 64},
    "component_face_count": {"type": "integer", "minimum": 1, "maximum": 64},
    "faces": {"type": "array", "items": _FACE_ROW, "minItems": 1, "maxItems": 64}})
CENSUS = _object({"assembly": _STATE,
    "components": {"type": "array", "items": _COMPONENT, "minItems": 2, "maxItems": 2},
    "face_count": {"type": "integer", "minimum": 2, "maximum": 128},
    "all_faces_observed": {"const": True}})
TARGET = _object({"target_id": TARGET_ID, "kind": {"const": "assembly-face"},
                  "component_name": _TEXT, "face_index": _INT})
READ_GATE = _object({"scope": {"const": "complete-readonly-target-census"},
                    "mate_tree_compared": {"const": False}, "write_authorized": {"const": False}})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def census_value(raw):
    """Strip private diagnostic flags; validate every value before staging IDs."""
    raw = deepcopy(raw)
    expected = dict(scope='private readonly active-assembly complete target census',
                    public_handles_issued=False, write_CAS_executed=False, public_acceptance=False)
    for key, value in expected.items():
        if canonical(raw.pop(key, None)) != canonical(value):
            raise ValueError('invalid private census flag: ' + key)
    validate_census(raw)
    return raw


def validate_census(value):
    # Source-only CLI/bootstrap help must remain importable without site packages.
    from jsonschema import Draft202012Validator

    canonical(value)
    Draft202012Validator(CENSUS).validate(value)
    components = value['components']
    if len({c['name'] for c in components}) != 2 or [c['fixed'] for c in components] != [True, False]:
        raise ValueError('census must contain distinct fixed/floating components')
    hashes = []
    for component in components:
        faces = component['faces']
        if (component['path'] != component['source_state']['path']
                or len(faces) != component['source_face_count']
                or len(faces) != component['component_face_count']
                or [f['index'] for f in faces] != list(range(len(faces)))):
            raise ValueError('incomplete component face census')
        hashes.extend(f['reference_sha256'] for f in faces)
    if value['face_count'] != len(hashes) or len(set(hashes)) != len(hashes):
        raise ValueError('incomplete or ambiguous target census')


def result_fields():
    common = {'scope': {'const': 'active-assembly-readonly-targets-v1'},
              'snapshot_id': SNAPSHOT_ID, 'census': CENSUS, 'read_gate': READ_GATE}
    return {
        'assembly.targets.list': ({**common, 'targets': {
            'type': 'array', 'items': TARGET, 'minItems': 2, 'maxItems': 128}},
            ('document', 'session_id', *common, 'targets')),
        'assembly.targets.validate': ({**common, 'target_ids': {
            'type': 'array', 'items': TARGET_ID, 'minItems': 1, 'maxItems': 128, 'uniqueItems': True},
            'unchanged': {'const': True}},
            ('document', 'session_id', *common, 'target_ids', 'unchanged')),
    }


def validate_result(name, result):
    if not result['ok']:
        if any(k in result for k in ('snapshot_id', 'targets', 'target_ids', 'census', 'unchanged')):
            raise ValueError('failed target observation published partial handles')
        return
    validate_census(result['census'])
    state, doc = result['census']['assembly'], result['document']
    if (doc['type'] != 2 or doc['active'] is not True or doc['path'] != state['path']
            or doc['modified'] is not False or doc['update_stamp'] != state['update_stamp']):
        raise ValueError('target document differs from complete census')
    if name.endswith('.list'):
        targets = result['targets']
        planned = [(c['name'], f['index']) for c in result['census']['components'] for f in c['faces']]
        if ([(t['component_name'], t['face_index']) for t in targets] != planned
                or len({t['target_id'] for t in targets}) != len(planned)):
            raise ValueError('public handles do not cover exact complete census')
