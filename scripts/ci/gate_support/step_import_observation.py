"""Read-only import provenance; unknown diagnostics never replace CAD errors."""
import hashlib
from pathlib import Path

TOGGLES=("swMultiCAD_Enable3DInterconnect","swImportSolidSurface","swImportFreeCurves",
         "swImportNeutral_SolidandSurface","swImportNeutral_FreeCurvesAndPoints","swImportStepConfigData")
INTEGERS=("swImportCurvePreference","swImportNeutral_CurvesAndPointsOption")


def error(exc):
    result={"type":type(exc).__name__,"message":str(exc)}
    code=getattr(exc,"hresult",None)
    if type(code) is int:
        result["hresult"]=code
    return result


def probe(call,label,function):
    def capture():
        try:
            return {"status":"observed","value":function()}
        except Exception as exc:
            return {"status":"unknown","error":error(exc)}
    return call(label,capture)


def read_interface_contract(path,pythoncom):
    path=Path(path)
    library=pythoncom.LoadTypeLib(str(path))
    interfaces={}
    for index in range(library.GetTypeInfoCount()):
        info=library.GetTypeInfo(index)
        name=info.GetDocumentation(-1)[0]
        if name in ("IImportStepData","IImportIgesData"):
            if name in interfaces:
                raise ValueError("ambiguous installed import interface: "+name)
            interfaces[name]=str(info.GetTypeAttr()[0])
    if set(interfaces)!={"IImportStepData","IImportIgesData"}:
        raise ValueError("installed import interfaces are incomplete")
    return {"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"interfaces":interfaces}


def observe_preferences(app,constants,call):
    result={}
    for name in TOGGLES+INTEGERS:
        expected=bool if name in TOGGLES else int
        kind="Toggle" if expected is bool else "IntegerValue"
        def read():
            value=getattr(app,"GetUserPreference"+kind)(constants[name])
            if type(value) is not expected:
                raise ValueError("unexpected preference type: "+name)
            return value
        result[name]=probe(call,"observe-import-context."+name,read)
    return result


def observe_dispatch(value,interfaces,call,label,*,step_mapping=False):
    result={"returned":value is not None,"python_type":type(value).__module__+"."+type(value).__name__}
    if value is None:
        return result
    def typeinfo():
        dispatch=getattr(value,"_oleobj_",value)
        count=dispatch.GetTypeInfoCount()
        if type(count) is not int or count<0:
            raise ValueError("invalid type-info count")
        if not count:
            return {"count":0,"name":None,"iid":None}
        info=dispatch.GetTypeInfo()
        return {"count":count,"name":info.GetDocumentation(-1)[0],"iid":str(info.GetTypeAttr()[0])}
    result["typeinfo"]=probe(call,label+".typeinfo",typeinfo)
    result["interfaces"]={}
    for name,iid in interfaces.items():
        result["interfaces"][name]=probe(call,label+".query-interface."+name,
            lambda:getattr(value,"_oleobj_",value).QueryInterface(iid) is not None)
    if step_mapping:
        matched=result["interfaces"].get("IImportStepData",{})
        if matched.get("status")=="observed" and matched.get("value") is True:
            def mapping():
                observed=value.MapConfigurationData
                if type(observed) is not bool:
                    raise ValueError("MapConfigurationData is not boolean")
                return observed
            result["map_configuration_data"]=probe(call,label+".MapConfigurationData",mapping)
        else:
            result["map_configuration_data"]={"status":"unknown","reason":"STEP interface not positively observed"}
    return result
