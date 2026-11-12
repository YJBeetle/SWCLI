"""Preselected explicit NULL binding + reviewed AsSketches observer. No fallback."""
import hashlib
import importlib.metadata
from pathlib import Path
from gate_support import step_null_binding,step_explicit_null_binding

PUBLIC_PROFILE=dict(zip(
    ('swMultiCAD_Enable3DInterconnect','swImportSolidSurface','swImportFreeCurves','swImportNeutral_SolidandSurface',
     'swImportNeutral_FreeCurvesAndPoints','swImportStepConfigData','swImportCurvePreference','swImportNeutral_CurvesAndPointsOption'),
    (False,True,True,True,False,False,0,0)))


def require(ok,message):
    if not ok:raise RuntimeError('NULL/sketch candidate refused: '+message)


def public_profile(neutral_free_candidate=False):
    require(type(neutral_free_candidate) is bool,'candidate flag must be bool')
    return {**PUBLIC_PROFILE,'swImportNeutral_FreeCurvesAndPoints':True} if neutral_free_candidate else dict(PUBLIC_PROFILE)


def preflight(swconst,*,neutral_free_candidate=False):
    """Same reviewed b312 source and installed TLB, before owned host acquisition."""
    require(importlib.metadata.version('pywin32')=='312','only reviewed pywin32312 is supported')
    package=step_null_binding.attest_package()
    contract=step_explicit_null_binding.installed_contract(Path(swconst).with_name('sldworks.tlb'))
    here=Path(__file__).resolve().parent
    files=[here/name for name in ('step_null_sketch_readback_candidate.py','step_sketch_readback_candidate.py','step_explicit_null_binding.py','step_null_binding.py')]+[here.parent/'verify-step-export-calibration.py',here.parent/'inspect-step-loadfile4-metadata.py']
    return dict(binding_package=package,installed_invocation_contract=contract,
        source_files_sha256={str(p.relative_to(here.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        neutral_free_candidate=neutral_free_candidate,
        selection=('same e039 NULL binding/AsSketches0; only NeutralFree=true, preselected before any LoadFile4' if neutral_free_candidate else 'explicit installed-TLB NULL binding plus fixed f56f792 AsSketches profile; selected before any LoadFile4'),
        single_null_causal_claim=False)


def load_model(app,path,arguments,factory,errors,call,case,persist,verify_profile,proof,*,neutral_free_candidate=False):
    """Exactly one preparation and one explicit invocation; factory is observed only."""
    require('null_sketch_import' not in case,'one preparation only; no alternative route/retry')
    evidence=case['null_sketch_import']=dict(status='started',comparison_head=('e039ae596d20d870752c6de7b02c8e1b283d5d62' if neutral_free_candidate else 'f56f7929c6877248926ba2497523c8be9d65c5f4'),
        changed_variables=(['swImportNeutral_FreeCurvesAndPoints'] if neutral_free_candidate else ['invocation binding','ImportData semantic value']),
        same_invocation_route_as_e039=neutral_free_candidate,single_null_causal_claim=False,
        factory_argument_used=False,binding={})
    persist()
    try:
        require(proof and proof['binding_package']['verified'] is True and proof['installed_invocation_contract']['verified'] is True,'prehost proof is missing')
        require(proof.get('neutral_free_candidate',False) is neutral_free_candidate,'preflight selection differs')
        require(case['sketch_observer_preferences']['requested']==public_profile(neutral_free_candidate),'full eight-value profile differs from selected candidate')
        observation=case['import_data_observation']
        require(factory is not None and observation.get('returned') is True and
                observation.get('interfaces',{}).get('IImportStepData')==dict(status='observed',value=True),'observed factory/STEP QI unknown')
        mapping=observation.get('map_configuration_data',{})
        require(mapping.get('status')=='observed' and type(mapping.get('value')) is bool,'mapping getter unknown')
        require(arguments=='r' and type(path) is str,'fixed public path/argument form differs')
        expected_sha=case['public_output']['sha256']
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected_sha,'actual STEP changed before binding')
        import pythoncom
        from win32com.client import VARIANT
        binding=step_explicit_null_binding.InstalledTlbNullInvoke(app,VARIANT,pythoncom,
            proof['binding_package'],proof['installed_invocation_contract'],evidence['binding'],call,persist,
            comparison_baseline='f56f792')
        observation['role']='observation only; not actual ImportData'
        evidence['prehost_proof']=proof
        case['import_return']['import_data']='explicit NULL IDispatch; existing installed-TLB binding; factory observed only'
        persist()
        verify_profile()  # Full eight-value CAS after binding, immediately before the single call.
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected_sha,'actual STEP changed after binding')
        result=binding.invoke_explicit(path,arguments,binding.argument,errors)
        evidence.update(status='returned',document_returned=result is not None,errors=errors.value);persist()
        return result
    except BaseException as exc:
        evidence.update(status='failed',first_error=dict(type=type(exc).__name__,message=str(exc)));persist();raise
