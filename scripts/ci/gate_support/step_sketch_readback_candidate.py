"""Review-only explicit AsSketches observer; no arbitrary representation fallback.

Existing reference diagnostic remains the default. This candidate needs fresh
same-head eight-file public exports and independent native save/reopen evidence.
"""
from contextlib import contextmanager
import math
from gate_support.step_import_observation import TOGGLES, INTEGERS, error
from gate_support.step_fixture_checks import verify_wire_geometry

SKETCH_TYPES=frozenset(('ProfileFeature','3DProfileFeature'))
NON_GEOMETRY_TYPES=frozenset(('CommentsFolder','DocsFolder','SurfaceBodyFolder','SolidBodyFolder','EnvFolder',
    'DetailCabinet','EqnFolder','MaterialFolder','RefPlane','OriginProfileFeature','AmbientLight','DirectionLight','PointLight','CameraFeature'))
EXPECTED_OUTPUTS=tuple((p,g,'cli') for p in ('ap203','ap214') for g in ('solid-surface','wireframe','wireframe-sketches'))+(
    ('ap214','solid-surface','sdk'),('ap203','wireframe','mcp'))


def require(ok,message):
    if not ok:raise RuntimeError('Sketch observer refused: '+message)


def verify_fresh_public_report(report,head):
    require(type(head) is str and len(head)==40 and all(c in '0123456789abcdef' for c in head),'exact current head required')
    require(report.get('source_commit')==head and report.get('success') is True and report.get('cleanup_errors')==[],
            'fresh same-head successful writer and cleanup required')
    rows=report.get('outputs',[])
    require(tuple((x['protocol'],x['geometry'],x['surface']) for x in rows)==EXPECTED_OUTPUTS,'exact eight public outputs required')
    require(len({x['path'] for x in rows})==8 and all(type(x['sha256']) is str and len(x['sha256'])==64 and
            all(c in '0123456789abcdef' for c in x['sha256']) for x in rows),'unique paths and output digests required')


@contextmanager
def preferences(app,constants,call,case,persist,*,neutral_free_candidate=False):
    """Full eight-value CAS; change General profile only, explicit official zero."""
    require(type(constants.get('swGeneralImportAsSketches')) is int and constants['swGeneralImportAsSketches']==0 and
            type(constants.get('swGeneralImportAs3dCurves')) is int and constants['swGeneralImportAs3dCurves']==1,'official sketch/curve enums differ')
    from swcli.hosts.windows import _com_value
    names=TOGGLES+INTEGERS
    journal=case['sketch_observer_preferences']=dict(status='started',reads=[],writes=[],restore=[],stages=[],restored=False)
    persist()
    def snapshot(label):
        result={};stage=dict(label=label,status='started',values=result);journal['stages'].append(stage);persist()
        for name in names:
            kind='Toggle' if name in TOGGLES else 'IntegerValue'
            value=call(label+'.'+name,lambda:getattr(app,'GetUserPreference'+kind)(constants[name]))
            journal['reads'].append(dict(name=name,value=value));persist()
            require(type(value) is (bool if name in TOGGLES else int),'unknown preference '+name)
            result[name]=value
        stage['status']='observed';persist();return result
    def read_one(name,label):
        kind='Toggle' if name in TOGGLES else 'IntegerValue'
        value=call(label+'.'+name,lambda:getattr(app,'GetUserPreference'+kind)(constants[name]))
        require(type(value) is (bool if name in TOGGLES else int),'unknown cleanup preference '+name)
        return value
    def write(name,value,label):
        kind='Toggle' if name in TOGGLES else 'IntegerValue'
        status=call(label+'.'+name,lambda:getattr(app,'SetUserPreference'+kind)(constants[name],value))
        require(status is None if name in TOGGLES else status is True,'setter contract '+name)
    before=journal['before']=snapshot('sketch-snapshot-original')
    require(before['swImportCurvePreference'] in (0,1),'unknown original General curve option')
    desired={**before,'swMultiCAD_Enable3DInterconnect':False,'swImportSolidSurface':True,
             'swImportFreeCurves':True,'swImportCurvePreference':constants['swGeneralImportAsSketches']}
    owned_names=('swMultiCAD_Enable3DInterconnect','swImportSolidSurface','swImportFreeCurves','swImportCurvePreference')
    if neutral_free_candidate:
        from gate_support.step_null_sketch_readback_candidate import public_profile
        desired['swImportNeutral_FreeCurvesAndPoints']=True
        require(desired==public_profile(True),'Neutral candidate has other eight-value drift; no writes')
        journal['e039_baseline']=public_profile(False)
        journal['changed_from_e039']=[name for name in names if desired[name]!=public_profile(False)[name]]
        require(journal['changed_from_e039']==['swImportNeutral_FreeCurvesAndPoints'],'Neutral candidate must change one field')
        owned_names+=('swImportNeutral_FreeCurvesAndPoints',)
    journal['requested']=desired;expected=dict(before);attempted=[];first=None
    try:
        require(call('sketch-observer-empty-before-profile',lambda:_com_value(app,'GetDocumentCount'))==0,'host must be empty')
        for name in owned_names:
            require(snapshot('sketch-cas-before-set')==expected,'complete preference CAS drift')
            if expected[name]==desired[name]:continue
            row=dict(name=name,original=before[name],requested=desired[name],possible_mutation=True,status='started')
            attempted.append(row);journal['writes'].append(row);persist()
            write(name,desired[name],'sketch-set-owned')
            expected[name]=desired[name];row['readback']=snapshot('sketch-readback-after-set')
            require(row['readback']==expected,'complete preference readback differs')
            row['status']='verified';persist()
        require(snapshot('sketch-verify-fixed-profile')==desired,'explicit sketch profile differs')
        def verify_active():require(snapshot('sketch-cas-before-one-load')==desired,'complete CAS changed before LoadFile4')
        journal['status']='active';persist();yield verify_active
        require(snapshot('sketch-cas-after-readback')==desired,'preference drift during readback')
    except BaseException as exc:
        first=exc;case['success']=False;journal['first_error']=error(exc);persist();raise
    finally:
        failures=[]
        for row in reversed(attempted):
            name=row['name'];restore=dict(name=name,status='started',possible_mutation=False);journal['restore'].append(restore);persist()
            try:
                current=restore['current']=read_one(name,'sketch-restore-cas')
                require(current in (before[name],desired[name]),'foreign preference value; leave untouched: '+name)
                if current!=before[name]:
                    restore['possible_mutation']=True;write(name,before[name],'sketch-restore-owned')
                restore['readback']=read_one(name,'sketch-restore-readback')
                require(restore['readback']==before[name],'original value did not restore: '+name)
                restore['status']='verified'
            except Exception as exc:
                restore.update(status='failed',error=error(exc));failures.append(error(exc))
            persist()
        try:
            journal['after']=snapshot('sketch-verify-full-original-restored')
            require(journal['after']==before,'full original vector did not restore')
        except Exception as exc:failures.append(error(exc))
        journal.update(restore_errors=failures,restored=not failures,status='restored' if not failures else 'restore-failed');persist()
        if failures:case['success']=False;persist()
        if failures and first is None:raise RuntimeError('Sketch observer preferences could not be restored')


def read_wireframe(reader,document,evidence,call,geometry):
    """Known ISketch types only; nonzero/unknown feature codes fail before segments."""
    import pythoncom
    from win32com.client import VARIANT
    require(not tuple(document.GetBodies2(0,False) or ()),'wireframe contains bodies')
    lengths=[];inventory=[]
    evidence.update(complete=False,method='native-explicit-sketches-checked',feature_inventory=inventory)
    try:
        for feature,identity,parent,depth in reader._wire_features(document):
            kind=reader._com_value(feature,'GetTypeName2')
            row=dict(feature_id=identity,parent_id=parent,depth=depth,kind=kind,name=reader._com_value(feature,'Name'),lengths_mm=[])
            inventory.append(row)
            require(kind in SKETCH_TYPES|NON_GEOMETRY_TYPES,'unexpected feature type '+str(kind))
            if kind not in SKETCH_TYPES:continue
            warning=VARIANT(pythoncom.VT_BYREF|pythoncom.VT_BOOL,False)
            row['feature_health']=dict(status='started')
            code=call('sketch-feature.GetErrorCode2',lambda:feature.GetErrorCode2(warning))
            row['feature_health']=dict(status='observed',code=code,is_warning=warning.value if code!=0 else None)
            require(type(code) is int and code==0,'nonzero or unknown sketch feature error code')
            sketch=reader._com_value(feature,'GetSpecificFeature2');require(sketch is not None,'missing ISketch interface')
            segments=tuple(reader._com_value(sketch,'GetSketchSegments') or ())
            require(bool(segments),'empty sketch cannot establish complete fixture geometry')
            for segment in segments:
                value=reader._com_value(segment,'GetLength')
                require(type(value) in (float,int) and math.isfinite(value) and value>0,'invalid native sketch length')
                length=value*1000;lengths.append(length);row['lengths_mm'].append(length)
    except BaseException as exc:
        evidence['first_error']=error(exc);raise
    finally:
        evidence.update(segment_count=len(lengths),lengths_mm=sorted(lengths),total_length_mm=math.fsum(lengths))
    try:
        require(bool(lengths),'no sketch geometry')
        verify_wire_geometry(evidence,geometry)
    except BaseException as exc:
        evidence['first_error']=error(exc);raise
    evidence['complete']=True
    return evidence


def readback_case(reader,app,output,constants,plane,reverse,call,case,report,live,*,profile_kind,load_model=None,neutral_free_candidate=False):
    import hashlib,json
    from pathlib import Path
    require(call('sketch-observer-host-hidden',lambda:reader._com_value(app,'Visible')) is False,'owned host must be hidden')
    require(call('sketch-observer-revision',lambda:reader._com_value(app,'RevisionNumber'))=='33.5.0','unreviewed native revision')
    require(call('sketch-observer-host-identity',lambda:reader._com_value(app,'GetProcessID'))==report['host']['process_id'],'owned host identity changed')
    source=json.loads((output/'source-public-report.json').read_text(encoding='utf-8'))
    row=source['outputs'][int(profile_kind)];target=Path(row['path'])
    require(hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256'],'public STEP digest mismatch')
    case.update(public_output=row,actual_step=reader.verify_step_output(target,row['protocol'],row['geometry']),
        observer='explicit-official-AsSketches=0; not As3DCurves acceptance')
    def persist():(output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    def observe(document,evidence):return read_wireframe(reader,document,evidence,call,row['geometry'])
    with preferences(app,constants,call,case,persist,neutral_free_candidate=neutral_free_candidate) as verify_profile:
        override=None
        if load_model is not None:
            case['observer']=('single NeutralFree=true candidate over e039; same explicit NULL/AsSketches0' if neutral_free_candidate else 'preselected explicit NULL binding plus official AsSketches=0; not single-null causality')
            override=lambda app,path,arg,data,errors:load_model(app,path,arg,data,errors,call,case,persist,verify_profile)
        reader._verify_imported_geometry(app,target,output,target.stem,row['geometry'],constants,call,case,live,
            wire_reader=observe,before_load=verify_profile,load_model=override)
