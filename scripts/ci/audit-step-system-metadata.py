"""Offline provenance for exact metadata containers; never runs CAD or classifies arbitrary types."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

TYPES={
    'FavoriteFolder':('Favorites','c_fmdt_favorites.htm','references to favorite features/sketches/reference geometry; edits affect all occurrences'),
    'HistoryFolder':('History','t_accessing_recent_features.htm','access to recently created/edited features'),
    'SelectionSetFolder':('Selection Sets','c_selection_sets.htm','saved selections of existing model items'),
    'SensorFolder':('Sensors','c_Sensors_OH.htm','monitors selected model properties and their alert values'),
    'InkMarkupFolder':('Markups','r_markups.htm','organizes collaboration markups, previews and image/PDF export'),
    'NotesAreaFtrFolder':('Notes','c_annotation_view_flat_to_screen.htm','contains annotation views beneath Annotations; not model sketch lengths'),
}
UI_SHA='27ae6a82721af973bf67acd16964bd34f881fbfe2f83740d5432c2bfa4b8c8bd'
API_SHA='3a46af7f0c11e958661beecc22158fedc360939193f5d967182724c9ddbec24e'
ZIP_SHA='b2e70c0786e67a9e97ff7a0af60234516eb2fd2a4884bf9b8506d7e6c9af1475'
MEMBER='SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~GetTypeName2.html'


def check(ok,message):
    if not ok:raise RuntimeError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def extract(chm,member):return subprocess.check_output(['7z','x','-so',str(chm),member])


def audit(original,ui_chm,api_chm):
    check(sha(original.read_bytes())==ZIP_SHA,'Retained native inventory ZIP differs')
    check(sha(ui_chm.read_bytes())==UI_SHA and sha(api_chm.read_bytes())==API_SHA,'Installed official help differs')
    with zipfile.ZipFile(original) as z:
        report_raw=z.read('swcli-native-smoke/step-public-readback/report.json')
    report=json.loads(report_raw)
    check(report['host']['revision']=='33.5.0' and report['host']['process_id']==4924,'Retained host identity differs')
    examples={name:[] for name in TYPES}
    def walk(value,path='$'):
        if isinstance(value,dict):
            if value.get('kind') in TYPES:
                kind=value['kind']
                examples[kind].append(dict(json_path=path,**{k:value.get(k) for k in ('feature_id','parent_id','depth','name','kind')}))
            for key,child in value.items():walk(child,path+'.'+key)
        elif isinstance(value,list):
            for i,child in enumerate(value):walk(child,path+'['+str(i)+']')
    walk(report)
    api=extract(api_chm,MEMBER)
    check(sha(api)=='6184824334d62e2ebccebf62c0f7e1adcd25408ccaeb3581f9c4ae0a32d0505d','GetTypeName2 table bytes differ')
    records=[]
    for kind,(display,member,semantics) in TYPES.items():
        check(any(x['name']==display for x in examples[kind]),'Exact native type/display example missing: '+kind)
        first_by_name={}
        for example in examples[kind]:first_by_name.setdefault(example['name'],example)
        # The table does not promise an interface for these six internal strings.
        check(kind.encode() not in api,'Update provenance: API table now includes '+kind)
        raw=extract(ui_chm,member)
        records.append(dict(kind=kind,observed_display_name=display,native_example_count=len(examples[kind]),native_examples=list(first_by_name.values()),
            installed_ui_member=member,installed_ui_sha256=sha(raw),installed_ui_bytes=len(raw),
            official_ui_url='https://help.solidworks.com/2025/English/SolidWorks/sldworks/'+member,
            semantic_summary=semantics,listed_in_installed_GetTypeName2_table=False,
            classification_basis='inference joining exact native type/display name with official installed UI container semantics; no claimed COM interface mapping'))
    return dict(native_inventory=dict(run_id=42365535291,artifact_id=13571478417,head='d6505f7384911b43b28a5f273ab14262032c4698',
        zip_sha256=ZIP_SHA,report_sha256=sha(report_raw),host=report['host']),
        installed_ui_chm_sha256=UI_SHA,installed_api_chm_sha256=API_SHA,installed_GetTypeName2_member=MEMBER,
        installed_GetTypeName2_sha256=sha(api),exact_metadata_types=records,
        observer_rule='skip measuring only the exact container node; resume full child traversal and native-ID deduplication; reject every unknown descendant',
        limitations=['Older retained host has same 33.5.0 revision, not the current PID or proof of identical Windows image',
                     'Current 43260435588 inventory stopped after CommentsFolder/FavoriteFolder; it does not prove subsequent nodes exist or are absent',
                     'Container classification is not proof that its descendants are harmless; no wildcard, display-name matching or subtree pruning',
                     'These six strings are absent from installed GetTypeName2 table; no fabricated GetSpecificFeature2 interface mapping',
                     'Offline provenance PASS is not native import/save/reopen or public eight-case acceptance'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original','ui-chm','api-chm','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();check(a.output.resolve() not in {a.original.resolve(),a.ui_chm.resolve(),a.api_chm.resolve()},'Do not overwrite sources')
    a.output.write_text(json.dumps(audit(a.original,a.ui_chm,a.api_chm),indent=2)+'\n')
    print('Exact six metadata container provenance PASS; no native acceptance claim')


if __name__=='__main__':main()
