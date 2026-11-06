"""Bounded, instantaneous mate-target contracts; not persistent public references."""


def obj(fields):
    return dict(type="object", properties=fields, required=list(fields), additionalProperties=False)


TEXT = dict(type="string", minLength=1)
INT = dict(type="integer", minimum=0)
BOOL = dict(type="boolean")
NUMBER = dict(type="number")
HASH = dict(type="string", pattern="^[a-f0-9]{64}$")
COMPONENT_NAMES = dict(type="array", items=TEXT, minItems=2, maxItems=2, uniqueItems=True)
FACE = obj(dict(index=INT, surface_kind=dict(type="string", enum=["plane", "cylinder"]),
                parameters=dict(type="array", items=NUMBER, minItems=6, maxItems=7),
                area_mm2=dict(type="number", exclusiveMinimum=0), sense=BOOL, reference_sha256=HASH))
COMPONENT = obj(dict(name=TEXT, path=TEXT, configuration=TEXT, native_id=INT,
    fixed=BOOL, suppression=dict(type="integer", enum=[2, 3]), source_update_stamp=INT,
    source_modified=BOOL, transform=dict(type="array", items=NUMBER, minItems=16, maxItems=16),
    faces=dict(type="array", items=FACE, minItems=1, maxItems=64)))
MATE = obj(dict(name=TEXT, kind=dict(type="string", enum=["coincident", "concentric"]),
    alignment=dict(type="string", enum=["aligned", "anti-aligned"]), error_code=INT, suppressed=BOOL,
    components=COMPONENT_NAMES, references=dict(type="array", items=HASH, minItems=2, maxItems=2),
    distance_mm=dict(type="number", minimum=0), parallel_error=dict(type="number", minimum=0)))
SNAPSHOT = obj(dict(title=TEXT, path=dict(type="string"), configuration=TEXT, update_stamp=INT,
    modified=BOOL, components=dict(type="array", items=COMPONENT, minItems=2, maxItems=2),
    mates=dict(type="array", items=MATE, maxItems=16)))
TARGET = obj(dict(component=TEXT, face_index=INT))
MUTATION = obj(dict(attempted=BOOL, creation_returned=BOOL, may_have_changed=BOOL))
# Promotion requires recorded Windows native persistence plus independent public
# client -> daemon -> worker evidence. Internal calibration is insufficient.
PUBLIC_MATE_WRITES_CALIBRATED = False
