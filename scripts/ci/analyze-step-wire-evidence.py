"""Compare original Part21 fixture wire files offline; never calls CAD or CI."""
import argparse
import json
import math
from pathlib import Path
from gate_support.step_wire_evidence import audit_wire, byte_compare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--left',type=Path,required=True,help='original step-public directory')
    parser.add_argument('--right',type=Path,required=True,help='second original step-public directory')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result={'scope':'generated straight-edge fixture; no full EXPRESS/native support claim','files':[]}
    for name in ('ap203-wireframe.step','ap214-wireframe.step','ap203-wireframe-sketches.step','ap214-wireframe-sketches.step','mcp-ap203-wireframe.step'):
        raw=[(root/name).read_bytes() for root in (args.left,args.right)]
        reports=[audit_wire(value) for value in raw]
        expected=sorted([10]*4+[30]*4+[40]*4+([30]*2+[40]*2+[50]*2 if 'sketches' in name else []))
        for report in reports:
            lengths=sorted(c['length_mm'] for c in report['curves'])
            graph=report['base_graph']
            report['matches_fixture']=(len(lengths)==len(expected) and all(math.isclose(a,b,rel_tol=0,abs_tol=1e-9)
                for a,b in zip(lengths,expected)) and graph['edges']==12 and graph['vertices']==8
                and graph['connected_components']==1 and graph['vertex_degrees']==[3]*8
                and len(graph['boundary_face_loops'])==6 and all(x['edges']==4 and x['all_vertices_degree_two']
                    for x in graph['boundary_face_loops']))
        result['files'].append({'name':name,'bytes':byte_compare(*raw),'left':reports[0],'right':reports[1],
                                'geometry_equal':reports[0]['geometry_signature']==reports[1]['geometry_signature'],
                                'entity_histogram_equal':reports[0]['entity_counts']==reports[1]['entity_counts']})
    result['cross_protocol_geometry_equal']={geometry:all(
        audit_wire((root/('ap203-'+geometry+'.step')).read_bytes())['geometry_signature']==
        audit_wire((root/('ap214-'+geometry+'.step')).read_bytes())['geometry_signature'] for root in (args.left,args.right))
        for geometry in ('wireframe','wireframe-sketches')}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Compared',len(result['files']),'file pairs; geometry equal:',all(x['geometry_equal'] for x in result['files']))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
