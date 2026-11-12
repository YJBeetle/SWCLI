"""Bounded read-only binding evidence; never resolve a business member."""
from types import FunctionType
import uuid
from gate_support.step_import_observation import error


def check(ok,message):
    if not ok:raise RuntimeError('Binding observation refused: '+message)


def type_name(value):return type(value).__module__+'.'+type(value).__qualname__


def snapshot_state(state,build):
    """Read only built-in dictionaries/known Python entries; no COM repr/str."""
    check(type(state) is dict,'Python state is not a dictionary')
    result=dict(state_keys=sorted(k for k in state if type(k) is str)[:256],
                lazydata=dict(key_present='_lazydata_' in state,is_none=state.get('_lazydata_') is None,
                              python_type=type_name(state.get('_lazydata_'))))
    lazy=state.get('_lazydata_')
    if type(lazy) in (tuple,list):result['lazydata']['items_python_types']=[type_name(x) for x in lazy[:4]]
    rep=state.get('_olerepr_');result['representation_type']=type_name(rep)
    if type(rep) not in (build.DispatchItem,build.LazyDispatchItem):
        result['representation_status']='unrecognized; not inspected'
        return result
    rep_state=object.__getattribute__(rep,'__dict__')
    result['maps']={}
    for name in ('mapFuncs','propMap','propMapGet','propMapPut'):
        values=rep_state.get(name)
        row=result['maps'][name]=dict(python_type=type_name(values))
        if type(values) is not dict:continue
        row.update(count=len(values),keys=sorted(k for k in values if type(k) is str)[:64],keys_truncated=len(values)>64,targets={})
        for target in ('LoadFile4','GetImportFileData'):
            entry=values.get(target);item=row['targets'][target]=dict(present=target in values)
            if entry is None:continue
            item['python_type']=type_name(entry)
            if type(entry) is build.MapEntry:
                data=object.__getattribute__(entry,'__dict__')
                item['dispid']=data.get('dispid') if type(data.get('dispid')) is int else None
                item['descriptor_is_none']=data.get('desc') is None
                item['descriptor_type']=type_name(data.get('desc'))
                names=data.get('names')
                if type(names) in (tuple,list):item['names']=[x for x in names[:12] if type(x) is str]
    cached=state.get('_builtMethods_');result['built_methods']=dict(python_type=type_name(cached))
    if type(cached) is dict:
        result['built_methods'].update(count=len(cached),load_present='LoadFile4' in cached)
        value=cached.get('LoadFile4')
        if type(value) is FunctionType:
            result['built_methods']['load_code_names']=list(value.__code__.co_names)
            result['built_methods']['load_code_filename']=value.__code__.co_filename
        elif value is not None:result['built_methods']['load_python_type']=type_name(value)
    return result


def existing_dispatch(raw,pythoncom):
    state=object.__getattribute__(raw,'__dict__')
    ole=state.get('_oleobj_')
    expected=pythoncom.TypeIIDs[pythoncom.IID_IDispatch]
    check(type(ole) is expected,'existing pointer is not the registered PyIDispatch type')
    return state,ole


def read_load_dispid(ole,call,record,persist):
    row=record['GetIDsOfNames']=dict(status='started',lcid=0,names=['LoadFile4'])
    persist()
    try:
        value=call('binding.GetIDsOfNames.LoadFile4',lambda:ole.GetIDsOfNames(0,'LoadFile4'))
        row.update(value=value if type(value) is int else None,python_type=type_name(value))
        check(type(value) is int and value==227,'DISPID is unknown or differs from installed LoadFile4')
    except BaseException as exc:
        row.update(status='unknown',error=error(exc));persist();raise
    row['status']='observed';persist()
    return value


def collect_native_metadata(raw,pythoncom,build,call,record,persist):
    """Prepared/unwired diagnostic: at most one of each metadata API, zero Invoke.

    This does not populate wrapper maps or select an invocation path.
    """
    state,ole=existing_dispatch(raw,pythoncom)
    record.update(scope='read-only native metadata; no binding created',before=snapshot_state(state,build),status='started')
    persist()
    def read(label,function,summarize):
        row=record[label]=dict(status='started');persist()
        try:
            value=call('binding.'+label,function)
            row.update(summarize(value),status='observed')
        except BaseException as exc:
            row.update(status='unknown',error=error(exc));persist();raise
        persist();return value
    try:
        read_load_dispid(ole,call,record,persist)
        def count_summary(value):
            check(type(value) is int and value in (0,1),'TypeInfo count is unknown')
            return dict(value=value)
        count=read('GetTypeInfoCount',ole.GetTypeInfoCount,count_summary)
        if count==0:
            record['type_info']=dict(status='not-available',reason='observed count=0; index0 not attempted')
        else:
            info=read('GetTypeInfo.0',lambda:ole.GetTypeInfo(0,0),lambda x:dict(python_type=type_name(x)))
            check(type(info) is pythoncom.TypeIIDs[pythoncom.IID_ITypeInfo],'TypeInfo wrapper is unknown')
            def attrs(value):
                guid=value[0];check(type(guid) is type(pythoncom.IID_IUnknown),'TypeInfo GUID type unknown')
                normalized='{'+str(uuid.UUID(str(guid).strip('{}'))).upper()+'}'
                result=dict(guid=normalized)
                for name,index in [('typekind',5),('function_count',6),('variable_count',7),('impl_count',8),('flags',11),('major',12),('minor',13)]:
                    check(type(value[index]) is int,'TypeInfo numeric attribute unknown')
                    result[name]=value[index]
                return result
            read('GetTypeAttr',info.GetTypeAttr,attrs)
            comp=read('GetTypeComp',info.GetTypeComp,lambda x:dict(python_type=type_name(x),returned=x is not None))
            check(type(comp) is pythoncom.TypeIIDs[pythoncom.IID_ITypeComp],'TypeComp wrapper unknown')
            record['type_info']=dict(status='observed',scope='current native object; not historical constructor result')
        record.update(after=snapshot_state(state,build),status='complete')
        check(record['before']==record['after'],'read-only collection changed Python binding maps')
        persist()
    except BaseException as exc:
        record.update(status='unknown',first_error=error(exc),after=snapshot_state(state,build));persist();raise
