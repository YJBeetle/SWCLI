"""Read-only Part21 audit for the generated straight-edge STEP fixture.

This checks bytes, references and explicit linear geometry, not full EXPRESS
schema conformance or native importer support. No CAD/COM dependency.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import math
import re


@dataclass(frozen=True)
class Ref:
    value: int


@dataclass(frozen=True)
class Node:
    name: str
    args: tuple


TOKEN = re.compile(r"\s+|/\*.*?\*/|'(?:''|[^'])*'|#\d+|[A-Z_][A-Z_0-9]*|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?|\.[A-Z_]+\.|[(),$*]", re.S | re.I)


def expression(text):
    tokens, offset = [], 0
    while offset < len(text):
        match = TOKEN.match(text, offset)
        if not match:
            raise ValueError('unrecognized Part21 token at ' + str(offset))
        token = match[0]
        offset = match.end()
        if not token.isspace() and not token.startswith('/*'):
            tokens.append(token)
    index = 0
    def value():
        nonlocal index
        if index >= len(tokens):
            raise ValueError('truncated Part21 expression')
        token = tokens[index]
        index += 1
        if token == '(':
            items = []
            while index < len(tokens) and tokens[index] != ')':
                if tokens[index] == ',':
                    index += 1
                else:
                    items.append(value())
            if index >= len(tokens):
                raise ValueError('unclosed Part21 aggregate')
            index += 1
            return tuple(items)
        if token.startswith('#'):
            return Ref(int(token[1:]))
        if token.startswith("'"):
            return token[1:-1].replace("''", "'")
        if re.fullmatch(r'[A-Z_][A-Z_0-9]*', token, re.I):
            if index >= len(tokens) or tokens[index] != '(':
                raise ValueError('constructor missing argument list')
            return Node(token.upper(), value())
        if token in ('$','*') or re.fullmatch(r'\.[A-Z_]+\.', token, re.I):
            return token.upper()
        return Decimal(token.replace('D','E').replace('d','E'))
    result = value()
    if index != len(tokens):
        raise ValueError('trailing Part21 tokens')
    return result


def references(value):
    if isinstance(value, Ref):
        yield value.value
    elif isinstance(value, Node):
        yield from references(value.args)
    elif isinstance(value, tuple):
        for item in value:
            yield from references(item)


def components(value):
    return (value,) if isinstance(value, Node) else value


def parse(raw):
    text = raw.decode('ascii')
    if not text.startswith('ISO-10303-21;') or not text.rstrip().endswith('END-ISO-10303-21;'):
        raise ValueError('Part21 framing mismatch')
    data = re.search(r'\bDATA\s*;(.*?)\bENDSEC\s*;', text, re.S | re.I)
    if not data:
        raise ValueError('missing DATA section')
    entities = {}
    # The statement scanner respects quoted semicolons and doubled quotes.
    scanner = re.compile(r"\s*(#\d+)\s*=\s*((?:'(?:''|[^'])*'|[^;'])*);", re.S)
    cursor = 0
    while cursor < len(data[1]):
        if not data[1][cursor:].strip():
            break
        match = scanner.match(data[1], cursor)
        if not match:
            raise ValueError('malformed DATA statement')
        identity = int(match[1][1:])
        if identity in entities:
            raise ValueError('duplicate entity ID')
        entities[identity] = expression(match[2].strip())
        cursor = match.end()
    dangling = sorted({r for v in entities.values() for r in references(v)} - entities.keys())
    if dangling:
        raise ValueError('dangling entity references: ' + str(dangling))
    return text, entities


def audit_wire(raw):
    text, entities = parse(raw)
    def node(identity, kind=None):
        result = entities[identity]
        if not isinstance(result, Node) or kind is not None and result.name != kind:
            raise ValueError('unexpected entity type for #' + str(identity))
        return result
    roots = [i for i,v in entities.items() if isinstance(v,Node) and v.name == 'SHAPE_DEFINITION_REPRESENTATION']
    reachable, pending = set(), list(roots)
    while pending:
        identity = pending.pop()
        if identity not in reachable:
            reachable.add(identity)
            pending.extend(references(entities[identity]))
    shapes = [i for i in reachable if isinstance(entities[i],Node) and entities[i].name == 'GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION']
    if len(shapes) != 1:
        raise ValueError('expected one root-reachable wire shape')
    shape = node(shapes[0])
    curve_sets = [r for r in references(shape.args[1]) if node(r).name == 'GEOMETRIC_CURVE_SET']
    if len(curve_sets) != 1:
        raise ValueError('expected one represented curve set')
    members = list(references(node(curve_sets[0]).args[1]))
    context = entities[shape.args[2].value]
    unit_ids = [r for c in components(context) if c.name == 'GLOBAL_UNIT_ASSIGNED_CONTEXT' for r in references(c)]
    length_units = [i for i in unit_ids if any(c.name == 'LENGTH_UNIT' for c in components(entities[i]))]
    if len(length_units) != 1:
        raise ValueError('ambiguous length unit')
    unit = next(c for c in components(entities[length_units[0]]) if c.name == 'SI_UNIT')
    scale_mm = {('.MILLI.','.METRE.'):Decimal(1),('$','.METRE.'):Decimal(1000)}.get(unit.args)
    if scale_mm is None:
        raise ValueError('unsupported unit: ' + repr(unit.args))
    def point(identity):
        return tuple(Decimal(v)*scale_mm for v in node(identity,'CARTESIAN_POINT').args[1])
    curves = []
    for identity in members:
        item = node(identity)
        record = {'entity_id':identity,'entity_type':item.name}
        if item.name == 'B_SPLINE_CURVE_WITH_KNOTS':
            degree, controls, _, closed, intersect, multiplicities, knots, _ = item.args[1:]
            if degree != 1 or len(controls) != 2 or multiplicities != (Decimal(2),Decimal(2)) or len(knots) != 2 or not knots[0] < knots[1]:
                raise ValueError('not a regular two-point degree-one fixture spline')
            first,last = (point(r.value) for r in controls)
            record.update(degree=1,closed_curve=closed,self_intersect=intersect,
                          knot_range=[str(x) for x in knots],multiplicities=[2,2])
        elif item.name == 'TRIMMED_CURVE':
            line = node(item.args[1].value,'LINE')
            trims = item.args[2:4]
            first,last = (point(next(r for r in t if isinstance(r,Ref)).value) for t in trims)
            parameters = [next(v.args[0] for v in t if isinstance(v,Node) and v.name=='PARAMETER_VALUE') for t in trims]
            origin = point(line.args[1].value)
            vector = node(line.args[2].value,'VECTOR')
            direction = node(vector.args[1].value,'DIRECTION').args[1]
            norm = math.sqrt(sum(float(v)**2 for v in direction))
            magnitude = float(vector.args[2]*scale_mm)
            if not norm:
                raise ValueError('zero line direction')
            for position,parameter in zip((first,last),parameters):
                expected = [float(o)+float(parameter)*magnitude*float(d)/norm for o,d in zip(origin,direction)]
                if not all(math.isclose(float(a),b,rel_tol=0,abs_tol=1e-9) for a,b in zip(position,expected)):
                    raise ValueError('trim point/line parameter inconsistency')
            record.update(basis='LINE',trim_parameters=[str(x) for x in parameters])
        else:
            raise ValueError('unsupported represented curve: '+item.name)
        length = math.dist(first,last)
        if not math.isfinite(length) or length <= 0:
            raise ValueError('degenerate line')
        endpoints = sorted(tuple(str(Decimal(0) if v==0 else v.normalize()) for v in p) for p in (first,last))
        record.update(endpoints_mm=endpoints,length_mm=length)
        curves.append(record)
    globally = {i for i,v in entities.items() if isinstance(v,Node) and v.name in ('B_SPLINE_CURVE_WITH_KNOTS','TRIMMED_CURVE')}
    orphan_curves = sorted(globally-set(members))
    if orphan_curves:
        raise ValueError('unrepresented/orphan curve entities: '+str(orphan_curves))
    base = [c for c in curves if c['entity_type']=='B_SPLINE_CURVE_WITH_KNOTS']
    graph = defaultdict(list)
    for index,c in enumerate(base):
        a,b = (tuple(p) for p in c['endpoints_mm'])
        graph[a].append((b,index)); graph[b].append((a,index))
    unseen, connected = set(graph),0
    while unseen:
        connected += 1; stack=[unseen.pop()]
        while stack:
            for other,_ in graph[stack.pop()]:
                if other in unseen:
                    unseen.remove(other); stack.append(other)
    loops=[]
    for axis in range(3):
        for coordinate in sorted({p[axis] for p in graph},key=Decimal):
            edges=[c for c in base if all(p[axis]==coordinate for p in c['endpoints_mm'])]
            if edges:
                degree=Counter(tuple(p) for c in edges for p in c['endpoints_mm'])
                loops.append({'axis':axis,'coordinate_mm':coordinate,'edges':len(edges),
                              'all_vertices_degree_two':all(d==2 for d in degree.values()),
                              'perimeter_mm':math.fsum(c['length_mm'] for c in edges)})
    canonical = sorted((c['entity_type'],c['endpoints_mm']) for c in curves)
    counts=Counter(c.name for value in entities.values() for c in components(value))
    schema = re.search(r'FILE_SCHEMA\s*\((.*?)\)\s*;',text,re.S | re.I)[1].strip()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw),'ascii':True,
            'crlf_count':raw.count(b'\r\n'),'lf_count':raw.count(b'\n'),'file_schema':schema,
            'entity_counts':dict(sorted(counts.items())),'entity_ids_unique':True,'dangling_references':[],
            'shape_definition_roots':roots,'wire_shape_id':shapes[0],'curve_set_id':curve_sets[0],
            'represented_curve_count':len(members),'orphan_curves':[],'length_unit':list(unit.args),
            'curves':curves,'total_length_mm':math.fsum(c['length_mm'] for c in curves),
            'base_graph':{'edges':len(base),'vertices':len(graph),'connected_components':connected,
                          'vertex_degrees':sorted(len(v) for v in graph.values()),
                          'cycle_rank':len(base)-len(graph)+connected,'boundary_face_loops':loops},
            'geometry_signature':hashlib.sha256(json.dumps(canonical,separators=(',',':')).encode()).hexdigest(),
            'full_express_conformance':'unknown','native_import_support':'unknown'}


def byte_compare(left,right):
    limit=min(len(left),len(right))
    first=next((i for i in range(limit) if left[i]!=right[i]),limit if len(left)!=len(right) else None)
    return {'equal':left==right,'left_bytes':len(left),'right_bytes':len(right),
            'first_difference_offset':first,'same_position_different_bytes':sum(a!=b for a,b in zip(left,right)),
            'length_delta':len(right)-len(left)}
