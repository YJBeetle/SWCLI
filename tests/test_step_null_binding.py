"""Fake binding/argument traps; no native pointer or CAD acceptance claim."""
import hashlib
import importlib.util
from pathlib import Path
from types import CodeType, MethodType, SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec=importlib.util.spec_from_file_location('step_null_test',ROOT/'scripts/ci/gate_support/step_null_binding.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class Variant:
    def __init__(self,kind,value):self.varianttype=kind;self.value=value


class MapEntry:
    def __init__(self,route='typed'):
        self.dispid=227;self.names=('LoadFile4','FileName','ArgString','ImportData','Errors')
        self.desc=None if route=='generic' else (227,None,((8,1,None),(8,1,None),(9,1,None),(16387,3,None)),4,1,4,0,0,(9,0,None))


class DispatchItem:
    def __init__(self,entry):self.mapFuncs={'LoadFile4':entry} if entry else {}
    def MakeFuncMethod(self,entry,name,makeclass):
        if entry.desc is None:
            return ['def LoadFile4(self, *args):',"    return self._get_good_object_(self._oleobj_.Invoke(*((227,0,1,1)+args)), 'LoadFile4')"]
        return ['def LoadFile4(self, FileName, ArgString, ImportData, Errors):',
            "    return self._ApplyTypes_(227,1,(9,0),((8,1),(8,1),(9,1),(16387,3)),'LoadFile4',None,FileName,ArgString,ImportData,Errors)"]


class LazyDispatchItem(DispatchItem):pass


class Endpoint:
    def __init__(self,target=None):self.target=target;self.calls=[]
    def InvokeTypes(self,*args):
        self.calls.append(('InvokeTypes',args))
        return self.target.LoadFile4(*args[5:]) if self.target else 'model'
    def Invoke(self,*args):
        self.calls.append(('Invoke',args))
        return self.target.LoadFile4(*args[4:]) if self.target else 'model'


class CDispatch:
    def __init__(self,entry,target=None,*,lazy=False,unknown=False):
        self._app=target;self._oleobj_=Endpoint(target)
        self._olerepr_=DispatchItem(None if lazy or unknown else entry)
        self._pending_entry=None if unknown else entry
        self._lazydata_=(object(),object()) if lazy or unknown else None
        self._builtMethods_={};self.lookups=0;self.lazy_reads=0
    def __getattr__(self,name):
        if name=='LoadFile4':
            self.lookups+=1
            if name not in self._olerepr_.mapFuncs:raise AssertionError('unknown lookup could invoke; forbidden')
            if name not in self._builtMethods_:return self._make_method_(name)
            return MethodType(self._builtMethods_[name],self)
        if self._app is not None:return getattr(self._app,name)
        raise AttributeError(name)
    def _LazyAddAttr_(self,name):
        self.lazy_reads+=1
        if self._pending_entry:self._olerepr_.mapFuncs[name]=self._pending_entry
    def _make_method_(self,name):
        src='\n'.join(self._olerepr_.MakeFuncMethod(self._olerepr_.mapFuncs[name],name,0))
        ns={};exec(compile(src,'<fake normal binder>','exec'),{},ns)
        self._builtMethods_[name]=ns[name]
        return MethodType(ns[name],self)
    def _ApplyTypes_(self,dispid,flags,ret,args,name,clsid,*values):
        return self._get_good_object_(self._oleobj_.InvokeTypes(dispid,0,flags,ret,args,*values),name,clsid)
    def _get_good_object_(self,value,*args):return value
    def _get_good_single_object_(self,value,*args):return value


class ClientCDispatch(CDispatch):
    def _wrap_dispatch_(self,ob,userName=None,returnCLSID=None):return ob
    def __dir__(self):return CDispatch.__dir__(self)


def client_dispatch_ex(*args):raise AssertionError('inspection must not create a host')
def client_dispatch(*args):raise AssertionError('inspection must not rewrap a host')
def client_wrap(*args):raise AssertionError('inspection must not replace return policy')


def environment(m,*,route='typed',target=None,lazy=False,unknown=False,wrong_type=False,wrapper='dynamic'):
    entry=MapEntry(route)
    if wrong_type:
        d=list(entry.desc);a=list(d[2]);a[2]=(12,1,None);d[2]=tuple(a);entry.desc=tuple(d)
    klass=ClientCDispatch if wrapper=='client' else CDispatch
    raw=klass(entry,target,lazy=lazy,unknown=unknown)
    dynamic=SimpleNamespace(CDispatch=CDispatch)
    build=SimpleNamespace(DispatchItem=DispatchItem,LazyDispatchItem=LazyDispatchItem,MapEntry=MapEntry)
    client=SimpleNamespace(VARIANT=Variant,CDispatch=ClientCDispatch,DispatchEx=client_dispatch_ex,Dispatch=client_dispatch,**{'__WrapDispatch':client_wrap})
    package=dict(verified=True,runtime_handlers={name:m.code_digest(getattr(CDispatch,name).__code__) for name in m.HANDLERS},
        client_wrapper_handlers={name:m.code_digest(getattr(ClientCDispatch,name).__code__) for name in m.CLIENT_HANDLERS},
        client_factory_handlers={name:m.code_digest(getattr(client,name).__code__) for name in m.CLIENT_FACTORIES})
    return raw,(dynamic,build,client),package


class NullBindingTests(unittest.TestCase):
    def prepare(self,**options):
        m=load();raw,mods,package=environment(m,**options);e={}
        with mock.patch.object(m,'modules',return_value=mods):
            binding=m.NullDispatchBinding(raw,Variant,package,e,lambda:None)
        return m,raw,mods,package,e,binding

    def test_typed_signature_none_preserves_cached_original_method_and_type(self):
        _,raw,_,_,e,b=self.prepare(lazy=True)
        self.assertEqual(raw.lazy_reads,1);self.assertEqual(raw.lookups,1);self.assertIsNone(b.argument)
        self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(e['route'],'typed-ApplyTypes-InvokeTypes')
        self.assertEqual(e['actual_argument']['signature_vartype'],9)
        self.assertEqual(b.invoke_original('fixed','r',None,object()),'model')
        self.assertEqual(len(raw._oleobj_.calls),1);kind,args=raw._oleobj_.calls[0]
        self.assertEqual(kind,'InvokeTypes');self.assertEqual(args[4][2],(9,1));self.assertIsNone(args[7])
        self.assertTrue(e['bound_method_invocation_attempted']);self.assertIn('no native-memory',e['pointer_evidence_kind'])
        with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',None,object())
        self.assertEqual(len(raw._oleobj_.calls),1)

    def test_known_generic_route_uses_only_inspected_explicit_dispatch_carrier(self):
        _,raw,_,_,e,b=self.prepare(route='generic')
        self.assertEqual(e['route'],'generic-Invoke');self.assertEqual(b.argument.varianttype,9);self.assertIsNone(b.argument.value)
        b.invoke_original('fixed','r',b.argument,object())
        self.assertEqual(len(raw._oleobj_.calls),1);kind,args=raw._oleobj_.calls[0]
        self.assertEqual(kind,'Invoke');self.assertIs(args[6],b.argument)
        self.assertEqual(e['actual_argument']['observed_varianttype'],9)

    def test_unknown_metadata_or_wrong_signature_never_looks_up_or_invokes_load(self):
        for options in ({'unknown':True},{'wrong_type':True}):
            m=load();raw,mods,p=environment(m,**options);e={}
            with self.subTest(options=options),mock.patch.object(m,'modules',return_value=mods):
                with self.assertRaises(RuntimeError):m.NullDispatchBinding(raw,Variant,p,e,lambda:None)
            self.assertEqual(raw.lookups,0);self.assertEqual(raw._oleobj_.calls,[])
            self.assertFalse(e['bound_method_invocation_attempted'])

    def test_wrong_id_parameter_names_or_optional_metadata_rejects_zero_load(self):
        for field,value in [('dispid',228),('names',('Other',)),('optional',-1)]:
            m=load();raw,mods,p=environment(m);entry=raw._olerepr_.mapFuncs['LoadFile4']
            if field=='optional':d=list(entry.desc);d[6]=value;entry.desc=tuple(d)
            else:setattr(entry,field,value)
            with self.subTest(field=field),mock.patch.object(m,'modules',return_value=mods):
                with self.assertRaises(RuntimeError):m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
            self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw.lookups,0)

    def test_nonnull_and_wrong_variant_type_are_not_converted_or_retried(self):
        for route in ('typed','generic'):
            for bad in (object(),None,Variant(12,None),Variant(9,object())):
                if route=='typed' and bad is None:continue
                _,raw,_,_,e,b=self.prepare(route=route)
                with self.subTest(route=route,bad=type(bad).__name__),self.assertRaises(RuntimeError):
                    b.invoke_original('fixed','r',bad,object())
                self.assertFalse(e['bound_method_invocation_attempted']);self.assertEqual(raw._oleobj_.calls,[])
                with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',b.argument,object())
                self.assertEqual(e['status'],'unknown')

    def test_mutated_actual_carrier_and_method_cache_reject_before_native(self):
        _,raw,_,_,e,b=self.prepare(route='generic');b.argument.value=object()
        with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',b.argument,object())
        self.assertEqual(raw._oleobj_.calls,[]);self.assertFalse(e['bound_method_invocation_attempted'])
        _,raw,_,_,e,b=self.prepare();raw._builtMethods_['LoadFile4']=lambda *args:None
        with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',None,object())
        self.assertEqual(raw._oleobj_.calls,[])

    def test_existing_unknown_method_code_is_not_replaced_or_called(self):
        m=load();raw,mods,p=environment(m)
        def unexpected(self,*args):raise AssertionError('must not execute')
        raw._builtMethods_['LoadFile4']=unexpected
        with mock.patch.object(m,'modules',return_value=mods):
            with self.assertRaises(RuntimeError):m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
        self.assertIs(raw._builtMethods_['LoadFile4'],unexpected);self.assertEqual(raw._oleobj_.calls,[])

    def test_unattested_package_or_runtime_conversion_change_rejects_zero_load(self):
        m=load();raw,mods,p=environment(m);p['runtime_handlers']['_ApplyTypes_']='unknown'
        with mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
            m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
        self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw.lookups,0)
        with mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
            m.NullDispatchBinding(raw,Variant,None,{},lambda:None)

    def test_package_source_and_runtime_handler_attestation_with_crlf_normalization(self):
        m=load();source='class CDispatch:\n'+''.join('    def '+name+'(self, *args):\n        return None\n' for name in m.HANDLERS+('_get_good_object_','_get_good_single_object_'))
        client_source=('class CDispatch(dynamic.CDispatch):\n'+''.join('    def '+name+'(self, *args):\n        return None\n' for name in m.CLIENT_HANDLERS)+
                       ''.join('def '+name+'(*args):\n    return None\n' for name in m.CLIENT_FACTORIES))
        ns={};exec(compile(source,'<fake package>','exec'),ns)
        client_ns={'dynamic':SimpleNamespace(CDispatch=ns['CDispatch'])};exec(compile(client_source,'<fake client>','exec'),client_ns)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=[]
            for name,data in [('dynamic',source),('build','\n'),('client',client_source)]:
                p=root/(name+'.py');p.write_bytes(data.replace('\n','\r\n').encode());paths.append(p)
            mods=(SimpleNamespace(__file__=str(paths[0]),CDispatch=ns['CDispatch']),
                  SimpleNamespace(__file__=str(paths[1])),SimpleNamespace(__file__=str(paths[2]),CDispatch=client_ns['CDispatch'],
                       **{name:client_ns[name] for name in m.CLIENT_FACTORIES}))
            hashes={k:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,p in zip(('dynamic','build','client'),paths)}
            with mock.patch.object(m,'modules',return_value=mods),mock.patch.object(m,'PACKAGE_SHA',hashes):
                self.assertTrue(m.attest_package()['verified'])
                paths[0].write_text(source+'# changed\n')
                with self.assertRaises(RuntimeError):m.attest_package()


    def test_runtime_conversion_handler_changed_after_prepare_is_zero_invoke(self):
        _,raw,_,_,e,b=self.prepare()
        def replaced(self,*args):raise AssertionError('do not call changed conversion')
        with mock.patch.object(CDispatch,'_ApplyTypes_',replaced):
            with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',None,object())
        self.assertFalse(e['bound_method_invocation_attempted']);self.assertEqual(raw._oleobj_.calls,[])

    def test_controller_requires_prepared_null_and_refuses_factory_before_original_call(self):
        spec=importlib.util.spec_from_file_location('step_null_controller',ROOT/'scripts/ci/diagnose-step-wire-import-once.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        raw,mods,p=environment(m.step_null_binding)
        raw.GetImportFileData=lambda path:object()
        constants={n:i for i,n in enumerate(m.TOGGLES+m.INTEGERS)}
        app=m.ImportOnceApp(raw,constants,neutral_3d_candidate=True,null_import_data_candidate=True,binding_package=p)
        data=app.GetImportFileData(m.INPUT)
        with self.assertRaises(RuntimeError):app.LoadFile4(m.INPUT,'r',None,object())
        with mock.patch.object(m.step_null_binding,'modules',return_value=mods):
            app.prepare_null_binding(Variant,{},lambda:None)
        with self.assertRaises(RuntimeError):app.LoadFile4(m.INPUT,'r',data,object())
        self.assertEqual(raw._oleobj_.calls,[])
        with self.assertRaises(RuntimeError):app.LoadFile4(m.INPUT,'r',None,object())
        with mock.patch.object(m.step_null_binding,'modules',return_value=mods),self.assertRaises(RuntimeError):
            app.prepare_null_binding(Variant,{},lambda:None)
        self.assertEqual(raw._oleobj_.calls,[])


    def test_code_proof_handles_python314_slice_constants_and_exception_tables(self):
        m=load()
        def sliced(value):return value[:3]
        self.assertEqual(m.code_key(sliced.__code__),m.code_key(sliced.__code__))
        original=sliced.__code__.replace(co_consts=(True,slice(None,3,None)))
        changed=sliced.__code__.replace(co_consts=(1,('slice',None,3,None)))
        self.assertNotEqual(m.code_key(original),m.code_key(changed))
        if hasattr(sliced.__code__,'co_exceptiontable'):
            changed=sliced.__code__.replace(co_exceptiontable=b'changed')
            self.assertNotEqual(m.code_key(changed),m.code_key(sliced.__code__))


    def test_exact_original_client_typed_and_generic_keep_receiver_route_and_return_policy(self):
        for route in ('typed','generic'):
            with self.subTest(route=route):
                m,raw,mods,p,e,b=self.prepare(wrapper='client',route=route,lazy=True)
                self.assertIs(type(raw),ClientCDispatch);self.assertIs(b.method.__self__,raw)
                self.assertTrue(e['binding_handlers_inherited']);self.assertTrue(e['return_wrapper_policy_preserved'])
                self.assertEqual(raw.lookups,1);self.assertEqual(raw.lazy_reads,1)
                original_policy=type(raw)._wrap_dispatch_
                self.assertEqual(b.invoke_original('fixed','r',b.argument,object()),'model')
                self.assertEqual(raw._oleobj_.calls[0][0],'InvokeTypes' if route=='typed' else 'Invoke')
                self.assertIs(type(raw),ClientCDispatch);self.assertIs(type(raw)._wrap_dispatch_,original_policy)

    def test_custom_client_subclass_and_altered_mro_are_not_whitelisted(self):
        m=load();raw,mods,p=environment(m,wrapper='client')
        class Custom(ClientCDispatch):pass
        raw.__class__=Custom
        with mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
            m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
        self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw.lookups,0)
        class OtherBase:pass
        class Multiple(CDispatch,OtherBase):
            _wrap_dispatch_=ClientCDispatch._wrap_dispatch_
            __dir__=ClientCDispatch.__dir__
        raw=Multiple(MapEntry());mods[2].CDispatch=Multiple
        with mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
            m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
        self.assertEqual(raw._oleobj_.calls,[])

    def test_client_inherited_binding_override_and_policy_change_reject_zero_load(self):
        for name in ('_ApplyTypes_','_wrap_dispatch_','__dir__'):
            m=load();raw,mods,p=environment(m,wrapper='client')
            def changed(*args):raise AssertionError('changed handler must not execute')
            with self.subTest(name=name),mock.patch.object(ClientCDispatch,name,changed), \
                    mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
                m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
            self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw.lookups,0)

    def test_client_policy_or_acquisition_code_change_after_inspection_is_terminal(self):
        m,raw,mods,p,e,b=self.prepare(wrapper='client')
        def changed(*args):raise AssertionError('must not execute changed client policy')
        with mock.patch.object(ClientCDispatch,'_wrap_dispatch_',changed),self.assertRaises(RuntimeError):
            b.invoke_original('fixed','r',b.argument,object())
        self.assertEqual(e['status'],'unknown');self.assertEqual(raw._oleobj_.calls,[])
        with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',b.argument,object())
        m=load();raw,mods,p=environment(m,wrapper='client');mods[2].Dispatch=changed
        with mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
            m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
        self.assertEqual(raw._oleobj_.calls,[])

    def test_client_binding_unknown_and_nonnull_still_zero_load_no_fallback(self):
        for options in ({'unknown':True},{'wrong_type':True}):
            m=load();raw,mods,p=environment(m,wrapper='client',**options)
            with self.subTest(options=options),mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
                m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
            self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw.lookups,0)
        for route in ('typed','generic'):
            _,raw,_,_,e,b=self.prepare(wrapper='client',route=route)
            with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',object(),object())
            with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',b.argument,object())
            self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(e['status'],'unknown')


    def test_client_receiver_class_or_attribute_lookup_change_is_zero_load(self):
        _,raw,_,_,e,b=self.prepare(wrapper='client')
        raw.__class__=CDispatch
        with self.assertRaises(RuntimeError):b.invoke_original('fixed','r',b.argument,object())
        self.assertEqual(e['status'],'unknown');self.assertEqual(raw._oleobj_.calls,[])
        m=load();raw,mods,p=environment(m,wrapper='client')
        def changed(self,name):return object.__getattribute__(self,name)
        with mock.patch.object(CDispatch,'__getattribute__',changed), \
                mock.patch.object(m,'modules',return_value=mods),self.assertRaises(RuntimeError):
            m.NullDispatchBinding(raw,Variant,p,{},lambda:None)
        self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw.lookups,0)
