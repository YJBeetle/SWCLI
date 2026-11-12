"""Portable traps for a separately labelled two-variable candidate; zero CAD."""
import sys
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/ci'))
from gate_support import step_explicit_null_binding as explicit
from gate_support import step_binding_observation as observation
from test_step_null_binding import environment,Variant,Endpoint


def contract():
    return dict(verified=True,tlb_sha256=explicit.TLB_SHA,dispid=227,lcid=0,invkind=1,arg_types=explicit.ARG_TYPES)


def pythoncom():
    return SimpleNamespace(IID_IDispatch='dispatch',TypeIIDs={'dispatch':Endpoint})


def call(label,fn):return fn()


class ExplicitBindingTests(unittest.TestCase):
    def prepare(self,**options):
        raw,mods,package=environment(explicit.prior,unknown=True,**options)
        raw._lazydata_=None  # Exact 8c refusal shape: new binding never fills its maps.
        evidence={}
        patches=mock.patch.object(explicit.prior,'modules',return_value=mods)
        patches.start();self.addCleanup(patches.stop)
        binding=explicit.InstalledTlbNullInvoke(raw,Variant,pythoncom(),package,contract(),evidence,call,lambda:None)
        return raw,mods,package,evidence,binding

    def test_unknown_old_maps_stay_empty_one_name_lookup_and_one_explicit_invoke(self):
        for wrapper in ('dynamic','client'):
            with self.subTest(wrapper=wrapper):
                raw,mods,p,e,b=self.prepare(wrapper=wrapper)
                errors=Variant(16387,0)
                self.assertEqual(b.invoke_explicit('fixed','r',b.argument,errors),'model')
                self.assertIs(b.raw,raw);self.assertIs(b.ole,raw._oleobj_)
                self.assertEqual(raw.lookups,0);self.assertEqual(raw.lazy_reads,0)
                self.assertEqual(raw._olerepr_.mapFuncs,{})
                self.assertEqual(raw._builtMethods_,{})
                self.assertEqual(raw._oleobj_.metadata_calls,[('GetIDsOfNames',(0,'LoadFile4'))])
                self.assertEqual(len(raw._oleobj_.calls),1)
                kind,args=raw._oleobj_.calls[0]
                self.assertEqual((kind,args[:4]),('Invoke',(227,0,1,1)))
                self.assertEqual(args[4:6],('fixed','r'));self.assertIs(args[6],b.argument);self.assertIs(args[7],errors)
                self.assertEqual((args[6].varianttype,args[6].value),(9,None))
                self.assertFalse(e['original_bound_method_used']);self.assertFalse(e['host_rewrapped'])
                self.assertFalse(e['single_null_causal_claim']);self.assertEqual(len(e['changed_variables_from_60f1cf8']),2)
                self.assertTrue(e['original_return_policy_completed']);self.assertTrue(e['raw_return']['returned'])
                with self.assertRaises(RuntimeError):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
                self.assertEqual(len(raw._oleobj_.calls),1)

    def test_wrong_unknown_or_boolean_dispid_stops_before_any_load_lookup_or_invoke(self):
        for value in (228,None,True,Failure('lookup error')):
            raw,mods,p=environment(explicit.prior,unknown=True);raw._oleobj_.dispid=value;e={}
            with self.subTest(value=type(value).__name__),mock.patch.object(explicit.prior,'modules',return_value=mods):
                with self.assertRaises((RuntimeError,Failure)):
                    explicit.InstalledTlbNullInvoke(raw,Variant,pythoncom(),p,contract(),e,call,lambda:None)
            self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw.lookups,0)
            self.assertEqual(e['GetIDsOfNames']['status'],'unknown');self.assertFalse(e['explicit_invoke_attempted'])

    def test_unverified_contract_or_package_never_even_performs_name_lookup(self):
        for key,value in [('verified',False),('tlb_sha256','wrong'),('dispid',228),('arg_types',((8,1),))]:
            raw,mods,p=environment(explicit.prior,unknown=True);bad=contract();bad[key]=value
            with self.subTest(key=key),mock.patch.object(explicit.prior,'modules',return_value=mods),self.assertRaises(RuntimeError):
                explicit.InstalledTlbNullInvoke(raw,Variant,pythoncom(),p,bad,{},call,lambda:None)
            self.assertEqual(raw._oleobj_.metadata_calls,[]);self.assertEqual(raw._oleobj_.calls,[])
        raw,mods,p=environment(explicit.prior);p['verified']=False
        with mock.patch.object(explicit.prior,'modules',return_value=mods),self.assertRaises(RuntimeError):
            explicit.InstalledTlbNullInvoke(raw,Variant,pythoncom(),p,contract(),{},call,lambda:None)
        self.assertEqual(raw._oleobj_.metadata_calls,[])

    def test_carrier_argument_and_errors_refusals_are_terminal_without_native_retry(self):
        for bad in (None,object(),Variant(12,None),Variant(9,object()),Variant(9,None)):
            raw,mods,p,e,b=self.prepare()
            with self.subTest(kind=type(bad).__name__),self.assertRaises(RuntimeError):
                b.invoke_explicit('fixed','r',bad,Variant(16387,0))
            with self.assertRaises(RuntimeError):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
            self.assertEqual(raw._oleobj_.calls,[])
        for path,arg,errors in [(1,'r',Variant(16387,0)),('fixed','',Variant(16387,0)),
                                ('fixed','r',Variant(3,0)),('fixed','r',Variant(16387,True)),('fixed','r',Variant(16387,1))]:
            raw,mods,p,e,b=self.prepare()
            with self.subTest(arg=arg,errors=errors.value),self.assertRaises(RuntimeError):b.invoke_explicit(path,arg,b.argument,errors)
            with self.assertRaises(RuntimeError):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
            self.assertEqual(raw._oleobj_.calls,[]);self.assertFalse(e['explicit_invoke_attempted'])

    def test_pointer_return_policy_package_and_source_drift_refuse_zero_invoke(self):
        changes=(lambda raw,mods,p,b:setattr(raw,'_oleobj_',Endpoint()),
                 lambda raw,mods,p,b:setattr(raw,'_get_good_object_',lambda *args:None),
                 lambda raw,mods,p,b:setattr(b,'return_policy',lambda *args:None),
                 lambda raw,mods,p,b:p['runtime_return_handlers'].update(_get_good_object_='changed'),
                 lambda raw,mods,p,b:p['runtime_handlers'].update(_ApplyTypes_='changed'),
                 lambda raw,mods,p,b:setattr(mods[2],'VARIANT',object),
                 lambda raw,mods,p,b:setattr(b.argument,'value',object()))
        for index,change in enumerate(changes):
            raw,mods,p,e,b=self.prepare();ole=b.ole;change(raw,mods,p,b)
            with self.subTest(change=index),self.assertRaises(RuntimeError):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
            self.assertEqual(ole.calls,[]);self.assertFalse(e['explicit_invoke_attempted'])

    def test_wrong_registered_dispatch_type_rejects_before_name_resolution(self):
        raw,mods,p=environment(explicit.prior);com=pythoncom();com.TypeIIDs['dispatch']=object
        with mock.patch.object(explicit.prior,'modules',return_value=mods),self.assertRaises(RuntimeError):
            explicit.InstalledTlbNullInvoke(raw,Variant,com,p,contract(),{},call,lambda:None)
        self.assertEqual(raw._oleobj_.metadata_calls,[])

    def test_native_first_error_is_retained_and_cannot_fall_back(self):
        raw,mods,p,e,b=self.prepare();raw._oleobj_.Invoke=mock.Mock(side_effect=Failure('native first error'))
        with self.assertRaisesRegex(Failure,'native first error'):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
        self.assertTrue(e['explicit_invoke_attempted']);self.assertEqual(e['first_invocation_error']['message'],'native first error')
        with self.assertRaises(RuntimeError):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
        raw._oleobj_.Invoke.assert_called_once();self.assertNotIn('raw_return',e)

    def test_wrapping_failure_retains_raw_return_and_does_not_invoke_again(self):
        raw,mods,p,e,b=self.prepare();result=object();raw._oleobj_.Invoke=mock.Mock(return_value=result)
        with mock.patch.object(explicit.InstalledTlbNullInvoke,'_verify_return_policy'):
            def fail(self,value,*args):raise Failure('return wrapping error')
            # Keep exact bound receiver/function identity while injecting this phase failure.
            with mock.patch.object(mods[0].CDispatch,'_get_good_object_',fail):
                b.return_policy=raw._get_good_object_
                with self.assertRaisesRegex(Failure,'return wrapping error'):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
        self.assertIs(b.partial_result,result);self.assertTrue(e['raw_return']['returned'])
        self.assertNotIn('original_return_policy_completed',e)
        self.assertEqual(e['first_invocation_error']['message'],'return wrapping error')
        with self.assertRaises(RuntimeError):b.invoke_explicit('fixed','r',b.argument,Variant(16387,0))
        raw._oleobj_.Invoke.assert_called_once()

    def test_static_loader_rejects_nonpinned_input_without_native_import(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sldworks.tlb';path.write_bytes(b'not pinned')
            with self.assertRaisesRegex(RuntimeError,'pinned actual TLB'):explicit.installed_contract(path)


class Failure(Exception):pass


class BindingObservationTests(unittest.TestCase):
    def fixture(self):
        raw,mods,p=environment(explicit.prior,unknown=True)
        return raw,mods[1],pythoncom()

    def test_snapshot_missing_none_and_property_cache_evidence_does_not_resolve_unknown_member(self):
        raw,build,com=self.fixture();state=raw.__dict__;state.pop('_lazydata_')
        first=observation.snapshot_state(state,build)
        self.assertFalse(first['lazydata']['key_present']);self.assertTrue(first['lazydata']['is_none'])
        state['_lazydata_']=None;state['_olerepr_'].propMap={'LoadFile4':raw._pending_entry}
        state['_builtMethods_']['LoadFile4']=lambda:None
        second=observation.snapshot_state(state,build)
        self.assertTrue(second['lazydata']['key_present'])
        self.assertTrue(second['maps']['propMap']['targets']['LoadFile4']['present'])
        self.assertTrue(second['built_methods']['load_present']);self.assertEqual(raw.lookups,0)
        self.assertEqual(raw._oleobj_.calls,[]);self.assertEqual(raw._oleobj_.metadata_calls,[])

    def test_unknown_objects_are_only_typed_without_repr_or_attribute_probes(self):
        class Trap:
            def __repr__(self):raise AssertionError('repr touched')
            def __str__(self):raise AssertionError('str touched')
            def __getattr__(self,name):raise AssertionError('unknown attribute touched')
        raw,build,com=self.fixture();raw._olerepr_=Trap();raw._lazydata_=Trap()
        result=observation.snapshot_state(raw.__dict__,build)
        self.assertEqual(result['representation_status'],'unrecognized; not inspected')
        self.assertEqual(raw.lookups,0)

    def test_count_zero_does_not_try_index_zero_and_never_invokes(self):
        raw,build,com=self.fixture();ole=raw._oleobj_
        ole.GetTypeInfoCount=mock.Mock(return_value=0);ole.GetTypeInfo=mock.Mock(side_effect=AssertionError('index forbidden'))
        e={};observation.collect_native_metadata(raw,com,build,call,e,lambda:None)
        self.assertEqual(e['status'],'complete');self.assertEqual(e['type_info']['status'],'not-available')
        ole.GetTypeInfoCount.assert_called_once_with();ole.GetTypeInfo.assert_not_called()
        self.assertEqual(ole.calls,[]);self.assertEqual(e['before'],e['after'])

    def test_count_one_collects_only_bounded_known_metadata(self):
        class IID(str):pass
        class Comp:pass
        class Info:
            def GetTypeAttr(self):return (IID(explicit.ISLDWORKS_IID),0,0,0,0,4,900,0,1,0,0,0,33,0)
            def GetTypeComp(self):return Comp()
        raw,build,com=self.fixture();com.IID_IUnknown=IID('safe');com.IID_ITypeInfo='info';com.IID_ITypeComp='comp'
        com.TypeIIDs.update(info=Info,comp=Comp);ole=raw._oleobj_
        ole.GetTypeInfoCount=mock.Mock(return_value=1);ole.GetTypeInfo=mock.Mock(return_value=Info())
        e={};observation.collect_native_metadata(raw,com,build,call,e,lambda:None)
        self.assertEqual(e['GetTypeAttr']['guid'],'{'+explicit.ISLDWORKS_IID.upper()+'}')
        self.assertEqual(e['GetTypeAttr']['function_count'],900);self.assertEqual(e['type_info']['status'],'observed')
        ole.GetTypeInfo.assert_called_once_with(0,0);self.assertEqual(ole.calls,[]);self.assertEqual(raw.lookups,0)

    def test_unknown_count_or_first_metadata_error_stops_without_fallback(self):
        for value in (None,True,2,Failure('metadata first error')):
            raw,build,com=self.fixture();ole=raw._oleobj_;ole.GetTypeInfo=mock.Mock()
            ole.GetTypeInfoCount=mock.Mock(side_effect=value if isinstance(value,Exception) else None,return_value=value)
            e={}
            with self.subTest(value=type(value).__name__),self.assertRaises((RuntimeError,Failure)):
                observation.collect_native_metadata(raw,com,build,call,e,lambda:None)
            self.assertEqual(e['status'],'unknown');ole.GetTypeInfo.assert_not_called();self.assertEqual(ole.calls,[])

    def test_name_lookup_failure_does_not_query_other_metadata(self):
        raw,build,com=self.fixture();ole=raw._oleobj_;ole.dispid=Failure('first name failure')
        ole.GetTypeInfoCount=mock.Mock();e={}
        with self.assertRaisesRegex(Failure,'first name failure'):observation.collect_native_metadata(raw,com,build,call,e,lambda:None)
        ole.GetTypeInfoCount.assert_not_called();self.assertEqual(ole.calls,[])
        self.assertEqual(e['first_error']['message'],'first name failure')

    def test_wrong_typeinfo_wrapper_stops_before_attribute_or_comp_binding(self):
        raw,build,com=self.fixture();ole=raw._oleobj_
        com.IID_ITypeInfo='info';com.TypeIIDs['info']=object
        info=SimpleNamespace(GetTypeAttr=mock.Mock(),GetTypeComp=mock.Mock())
        ole.GetTypeInfoCount=mock.Mock(return_value=1);ole.GetTypeInfo=mock.Mock(return_value=info);e={}
        with self.assertRaisesRegex(RuntimeError,'TypeInfo wrapper is unknown'):
            observation.collect_native_metadata(raw,com,build,call,e,lambda:None)
        info.GetTypeAttr.assert_not_called();info.GetTypeComp.assert_not_called();self.assertEqual(ole.calls,[])
        self.assertEqual(e['status'],'unknown')

    def test_metadata_errors_preserve_first_without_retry_or_invoke(self):
        class Info:
            GetTypeAttr=mock.Mock(side_effect=Failure('attribute first error'))
            GetTypeComp=mock.Mock()
        raw,build,com=self.fixture();com.IID_ITypeInfo='info';com.TypeIIDs['info']=Info
        ole=raw._oleobj_;ole.GetTypeInfoCount=mock.Mock(return_value=1);ole.GetTypeInfo=mock.Mock(return_value=Info());e={}
        with self.assertRaisesRegex(Failure,'attribute first error'):
            observation.collect_native_metadata(raw,com,build,call,e,lambda:None)
        Info.GetTypeAttr.assert_called_once_with();Info.GetTypeComp.assert_not_called()
        self.assertEqual(e['first_error']['message'],'attribute first error');self.assertEqual(ole.calls,[])


if __name__=='__main__':unittest.main()
