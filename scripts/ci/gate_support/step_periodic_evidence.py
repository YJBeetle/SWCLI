"""Offline oracles for a single r10/h30 cylinder; not general STEP or native acceptance."""
import math
from .step_wire_evidence import Node, Ref, parse_periodic, references


PLAN = (('ap203', False), ('ap203', True), ('ap214', False), ('ap214', True))
READER_SCOPE = 'step-public-periodic-independent-readback'


def require(ok, message):
    if not ok:raise ValueError(message)


def audit_cylinder_topology(raw, split_periodic_faces):
    require(type(split_periodic_faces) is bool, 'strict split boolean required')
    require(len(raw) <= 8 * 1024 * 1024, 'fixture STEP exceeds bound')
    _, entities = parse_periodic(raw)
    require(len(entities) <= 20000, 'fixture entity count exceeds bound')
    def node(ref, kind):
        require(isinstance(ref, Ref), 'expected entity reference')
        value = entities[ref.value]
        require(isinstance(value, Node) and value.name == kind, 'expected ' + kind)
        return value
    roots = [i for i,v in entities.items() if isinstance(v,Node) and v.name=='SHAPE_DEFINITION_REPRESENTATION']
    require(len(roots)==1, 'expected one shape definition root')
    seen, pending = set(), list(roots)
    while pending:
        identity = pending.pop()
        if identity in seen:continue
        seen.add(identity);pending.extend(references(entities[identity]))
    bodies = [i for i,v in entities.items() if isinstance(v,Node) and v.name=='MANIFOLD_SOLID_BREP']
    require(len(bodies)==1 and bodies[0] in seen, 'expected one reachable closed solid')
    body=entities[bodies[0]];require(len(body.args)==2, 'unknown solid layout')
    shell=node(body.args[1], 'CLOSED_SHELL')
    require(len(shell.args)==2 and isinstance(shell.args[1],tuple), 'unknown shell layout')
    faces=shell.args[1]
    require(all(isinstance(r,Ref) for r in faces) and len(set(faces))==len(faces), 'duplicate or invalid face references')
    all_faces={i for i,v in entities.items() if isinstance(v,Node) and v.name=='ADVANCED_FACE'}
    require(all_faces=={r.value for r in faces}, 'extra or unreachable faces')
    counts={'CYLINDRICAL_SURFACE':0,'PLANE':0}
    for ref in faces:
        face=node(ref,'ADVANCED_FACE');require(len(face.args)==4 and isinstance(face.args[2],Ref), 'unknown face layout')
        surface=entities[face.args[2].value]
        require(isinstance(surface,Node) and surface.name in counts, 'unknown fixture surface type')
        counts[surface.name]+=1  # Count face uses, not distinct/reused surface objects.
    require(counts=={'CYLINDRICAL_SURFACE':2 if split_periodic_faces else 1,'PLANE':2}, 'periodic-face split topology differs')
    return dict(scope='single cylinder fixture only; not general STEP validity',solid_count=1,
                face_count=len(faces),face_surface_counts=counts,split_periodic_faces=split_periodic_faces)


def verify_cylinder_mass(observation):
    require(observation.get('ok') is True and observation.get('method')=='native-body-mass-properties', 'native mass evidence required')
    metrics=observation['metrics'];bodies=observation['bodies']
    require(type(metrics['solid_body_count']) is int and metrics['solid_body_count']==len(bodies)==1, 'cylinder body count differs')
    for row in (metrics,bodies[0]):
        for key,target in (('volume_mm3',3000*math.pi),('surface_area_mm2',800*math.pi)):
            value=row[key];require(type(value) in (int,float) and math.isfinite(value) and math.isclose(value,target,rel_tol=1e-7,abs_tol=1e-5),'cylinder '+key+' differs')
        for axis,target in zip('xyz',(0,0,15)):
            value=row['centroid_mm'][axis]
            require(type(value) in (int,float) and math.isfinite(value) and math.isclose(value,target,rel_tol=0,abs_tol=1e-9),'cylinder centroid differs')
    return observation
