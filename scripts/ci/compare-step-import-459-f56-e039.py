"""Pinned offline comparison of actual pre-load vectors and three original STEP payloads."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path,PureWindowsPath
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gate_support.step_wire_evidence import audit_wire,byte_compare,parse

REPORT_SHA={'459':'26f7be0f5515781db1cc043c1ddd918aac69f03c6d2eff929b0d6c3d21b7eb7d',
 'f56':'e77d690128d0262f480aa9e84cd681bc63dffd10b0911dddcb3dd70f9efd9713',
 'e039':'0db86a01969bdb7828da88a6b845f916bd992079acef922171e075a5ed708aa3'}
NAMES=('swMultiCAD_Enable3DInterconnect','swImportSolidSurface','swImportFreeCurves','swImportNeutral_SolidandSurface',
 'swImportNeutral_FreeCurvesAndPoints','swImportStepConfigData','swImportCurvePreference','swImportNeutral_CurvesAndPointsOption')


def check(ok,message):
    if not ok:raise RuntimeError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def compare(root459,step459,f56,e039):
    reports={'459':root459/'report.json',**{label:root/'native/swcli-native-smoke/step-public-readback/report.json' for label,root in [('f56',f56),('e039',e039)]}}
    cases={};vectors={};cas={};paths={'459':step459};returns={}
    for label,path in reports.items():
        raw=path.read_bytes();check(sha(raw)==REPORT_SHA[label],'Original report differs: '+label);r=json.loads(raw)
        c=r['cases'][0 if label=='459' else 1];cases[label]=c
        p=c['preferences' if label=='459' else 'sketch_observer_preferences']
        vectors[label]=p['candidate_readback' if label=='459' else 'requested']
        cas[label]=[s['values'] for s in p['stages'] if s['label'] in ('cas-before-one-load','cas-after-null-binding','sketch-cas-before-one-load')]
        check(cas[label] and all(v==vectors[label] for v in cas[label]),'Pre-load full CAS differs')
        check(tuple(vectors[label])==NAMES,'Eight-vector order differs');returns[label]=c['load_return' if label=='459' else 'import_return']
        if label=='459':check(sha(step459.read_bytes())==r['input']['sha256'],'459 original input differs')
        else:
            base=(f56 if label=='f56' else e039)/'native/swcli-native-smoke/step-public'
            paths[label]=base/PureWindowsPath(c['public_output']['path']).name
            check(sha(paths[label].read_bytes())==c['public_output']['sha256'],'Public file digest differs')
    check(vectors['f56']==vectors['e039'],'NULL repair unexpectedly changed preferences')
    differences=[key for key in NAMES if vectors['459'][key]!=vectors['e039'][key]]
    check(differences==['swImportNeutral_FreeCurvesAndPoints','swImportCurvePreference','swImportNeutral_CurvesAndPointsOption'],'Actual cross-environment differences changed')
    geometry={k:audit_wire(p.read_bytes()) for k,p in paths.items()}
    comparisons={}
    def keyed_curves(label):
        record=geometry[label];_,entities=parse(paths[label].read_bytes());result={}
        for curve in record['curves']:
            row={k:v for k,v in curve.items() if k not in ('entity_id','endpoints_mm','length_mm')}
            item=entities[curve['entity_id']]
            check(item.name=='B_SPLINE_CURVE_WITH_KNOTS','Expected original degree-one spline input')
            row['ordered_controls_in_file_mm']=[[str(v.normalize()) if v else '0' for v in entities[ref.value].args[1]] for ref in item.args[2]]
            result[json.dumps(curve['endpoints_mm'],separators=(',',':'))]=row
        return result
    for a,b in itertools.combinations(paths,2):
        left,right=geometry[a],geometry[b];ka,kb=keyed_curves(a),keyed_curves(b)
        check(left['geometry_signature']==right['geometry_signature'] and left['length_unit']==right['length_unit'] and left['entity_counts']==right['entity_counts'],'Geometric/unit/entity discrepancy requires investigation before preference hypothesis')
        comparisons[a+'__'+b]=dict(bytes=byte_compare(paths[a].read_bytes(),paths[b].read_bytes()),
            entity_counts_equal=True,units_equal=True,root_reachable_linear_endpoint_geometry_equal=True,
            parameter_records_equal=ka==kb,parameter_different_endpoint_pairs=[key for key in ka if ka[key]!=kb[key]])
    return dict(kind='offline actual-input/profile comparison; not native acceptance or precedence proof',report_sha256=REPORT_SHA,
        vectors=vectors,preload_CAS_checkpoints=cas,vector_fields=[dict(name=k,**{label:v[k] for label,v in vectors.items()}) for k in NAMES],
        differences_459_vs_e039=differences,differences_f56_vs_e039=[],load_returns=returns,files=geometry,pairwise=comparisons,
        proposed_single_change_from_e039=dict(name='swImportNeutral_FreeCurvesAndPoints',before=False,after=True,
            fixed_fields={k:v for k,v in vectors['e039'].items() if k!='swImportNeutral_FreeCurvesAndPoints'},
            binding='same preselected227/NULL, r, no fallback',status='candidate only; unexecuted'),
        limitations=['459 differs in three preferences, file byte layout and environment; Neutral alone is not causally proven',
                    'Linear endpoints plus explicitly compared spline parameters/ordered controls do not establish byte equality or full EXPRESS/metadata equivalence',
                    'Official Neutral entity selector is documented; General/Neutral precedence in this translator is not established'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root459','step459','f56','e039','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();protected=[a.root459.resolve(),a.f56.resolve(),a.e039.resolve()]
    check(all(out!=x and x not in out.parents for x in protected) and out!=a.step459.resolve(),'Do not overwrite originals')
    result=compare(a.root459,a.step459,a.f56,a.e039);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Original comparison PASS: f56=e039 eight-vector; 459 differs in three fields; equal observed linear geometry, unequal bytes; per-edge parameters and ordered controls compared')


if __name__=='__main__':main()
