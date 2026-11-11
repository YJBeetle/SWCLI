"""Explicit installed-TLB-constrained Invoke + NULL: two changed variables.

This is deliberately NOT proof or reuse of a formerly unknown method binding.
No LoadFile4 getattr, FlagAsMethod, rewrap, host replacement or InvokeTypes.
"""
import hashlib
import importlib.util
from pathlib import Path
from types import MethodType
from gate_support import step_null_binding as prior
from gate_support.step_binding_observation import existing_dispatch,read_load_dispid,snapshot_state,type_name

TLB_SHA='585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159'
ISLDWORKS_IID='83a33d22-27c5-11ce-bfd4-00400513bb57'
ARG_TYPES=((8,1),(8,1),(9,1),(16387,3))
INVOKE_SOURCE=dict(url='https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyIDispatch.cpp',
                   sha256='8cb132de33fdbfeaaf42085687ce74d4a973f813d98f6f88e7284be9cb229fff',
                   scope='reviewed C++ source, not loaded native binary attestation')
RETURN_HANDLERS=('_get_good_object_','_get_good_single_object_','_wrap_dispatch_')


def require(ok,message):
    if not ok:raise RuntimeError('Explicit installed binding refused: '+message)


def installed_contract(path):
    """Parse the same reviewed fixed MSFT file, before host acquisition."""
    parser_path=Path(__file__).resolve().parents[1]/'inspect-step-loadfile4-metadata.py'
    spec=importlib.util.spec_from_file_location('_explicit_step_installed_tlb',parser_path)
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    raw=path.read_bytes();method=parser.typelib(raw)['LoadFile4']
    require(method['interface']['guid']==ISLDWORKS_IID and method['dispid']==227 and method['optional_count']==0,'installed method identity differs')
    p=method['parameters']
    require([(x['name'],x['flags']) for x in p]==[('FileName',1),('ArgString',1),('ImportData',1),('Errors',3),('Retval',10)],'installed parameters differ')
    require([x['datatype']['type'] for x in p[:3]]==['VT_BSTR','VT_BSTR','VT_DISPATCH'],'installed input types differ')
    require(p[3]['datatype']['type']=='VT_PTR' and p[3]['datatype']['target']['type']=='VT_I4','installed errors ABI differs')
    ret=p[4]['datatype'];require(ret['type']=='VT_PTR' and ret['target']['type']=='VT_PTR' and ret['target']['target']['reference']['name']=='IModelDoc2','installed retval ABI differs')
    require(method['return_type']['type']=='VT_HRESULT','installed native result differs')
    require(hashlib.sha256(raw).hexdigest()==TLB_SHA,'installed TLB bytes differ')
    return dict(verified=True,tlb_sha256=TLB_SHA,dispid=227,lcid=0,invkind=1,arg_types=ARG_TYPES,
                method=method,parser_sha256=hashlib.sha256(parser_path.read_bytes()).hexdigest(),
                binding='explicit Generic Invoke constrained by installed declaration; not old bound method')


class InstalledTlbNullInvoke:
    def __init__(self,raw,variant_class,pythoncom,package,contract,evidence,call,persist):
        self.raw,self.variant_class,self.package=raw,variant_class,package
        self.evidence,self.persist=evidence,persist
        self.invoked=self.invalid=False
        evidence.update(status='started',explicit_invoke_attempted=False,
            changed_variables_from_60f1cf8=['invocation binding','ImportData semantic value'],single_null_causal_claim=False)
        persist()
        require(package and package.get('verified') is True,'unverified b312 source')
        require(contract and contract.get('verified') is True and contract.get('tlb_sha256')==TLB_SHA and
                contract.get('dispid')==227 and contract.get('lcid')==0 and contract.get('invkind')==1 and
                tuple(tuple(x) for x in contract.get('arg_types',()))==ARG_TYPES,'unverified installed contract')
        self.dynamic,self.build,self.client=prior.modules()
        prior.verify_handlers(self.dynamic,package)
        require(type(raw) in (self.dynamic.CDispatch,self.client.CDispatch),'unsupported original wrapper')
        self.wrapper_class=type(raw)
        if type(raw) is self.client.CDispatch:prior.verify_client_wrapper(self.dynamic,self.client,package)
        require(variant_class is self.client.VARIANT,'unverified VARIANT class')
        self.state,self.ole=existing_dispatch(raw,pythoncom)
        self.ole_class=type(self.ole)
        require(not any(k in self.state for k in prior.INSTANCE_OVERRIDES+RETURN_HANDLERS),'wrapper instance overrides')
        self._verify_return_policy()
        evidence['existing_python_state']=snapshot_state(self.state,self.build);persist()
        read_load_dispid(self.ole,call,evidence,persist)  # name lookup only, exactly once; no Invoke probe.
        evidence['state_after_name_lookup']=snapshot_state(self.state,self.build)
        require(evidence['state_after_name_lookup']==evidence['existing_python_state'],'name lookup changed Python maps')
        self.argument=variant_class(9,None)
        self.return_policy=raw._get_good_object_  # known inherited Python member, never LoadFile4 lookup.
        require(isinstance(self.return_policy,MethodType) and self.return_policy.__self__ is raw and
                self.return_policy.__func__ is self.dynamic.CDispatch._get_good_object_,'return policy replaced')
        evidence.update(status='verified',binding='explicit existing PyIDispatch.Invoke',installed_contract=contract,
            original_bound_method_used=False,host_rewrapped=False,invoke_source=INVOKE_SOURCE,raw_typeinfo='not queried; installed declaration constrains this new binding',
            pointer_evidence_kind='explicit VARIANT9/None plus b312 conversion proof; no native-memory measurement')
        self.validate(self.argument);persist()

    def _verify_return_policy(self):
        for name in RETURN_HANDLERS:
            fn=getattr(self.dynamic.CDispatch,name)
            require(prior.code_digest(fn.__code__)==self.package.get('runtime_return_handlers',{}).get(name),'return helper source changed: '+name)
        if type(self.raw) is self.client.CDispatch:prior.verify_client_wrapper(self.dynamic,self.client,self.package)

    def validate(self,argument):
        try:
            require(not self.invalid,'previous refusal; no fallback')
            require(self.package.get('verified') is True and self.variant_class is self.client.VARIANT,'package/carrier class changed')
            prior.verify_handlers(self.dynamic,self.package);self._verify_return_policy()
            require(type(self.raw) is self.wrapper_class and object.__getattribute__(self.raw,'__dict__') is self.state and
                    self.state.get('_oleobj_') is self.ole and type(self.ole) is self.ole_class,'original receiver/pointer changed')
            require(type(self.return_policy) is MethodType and self.return_policy.__self__ is self.raw and
                    self.return_policy.__func__ is self.dynamic.CDispatch._get_good_object_,'cached return policy changed')
            require(not any(k in self.state for k in prior.INSTANCE_OVERRIDES+RETURN_HANDLERS),'instance binding changed')
            require(argument is self.argument and type(argument) is self.variant_class and type(argument.varianttype) is int and
                    argument.varianttype==9 and argument.value is None,'only inspected explicit NULL DISPATCH carrier allowed')
            self.evidence['actual_argument']=dict(python_form='VARIANT(VT_DISPATCH,None)',observed_varianttype=9,
                observed_value_is_none=True,null_dispatch_pointer_by_conversion_proof=True)
            self.persist()
        except BaseException as exc:
            self.invalid=True;self.evidence.update(status='unknown',validation_error=dict(type=type(exc).__name__,message=str(exc)));self.persist();raise

    def invoke_explicit(self,path,arguments,argument,errors):
        self.validate(argument)
        try:
            require(not self.invoked,'one explicit Invoke only')
            require(type(path) is str and type(arguments) is str and arguments=='r','fixed BSTR argument forms differ')
            require(type(errors) is self.variant_class and type(errors.varianttype) is int and errors.varianttype==16387 and
                    type(errors.value) is int and errors.value==0,'errors carrier differs from original BYREF I4 zero')
        except BaseException as exc:
            self.invalid=True
            self.evidence.update(status='unknown',validation_error=dict(type=type(exc).__name__,message=str(exc)))
            self.persist();raise
        self.invoked=True;self.evidence['explicit_invoke_attempted']=True;self.persist()
        try:
            result=self.ole.Invoke(227,0,1,1,path,arguments,argument,errors)
            self.partial_result=result  # Retain returned pointer even if Python wrapping fails.
            self.evidence['raw_return']=dict(returned=result is not None,python_type=type_name(result),
                                            scope='after Invoke; before original Python return policy')
            self.persist()
            wrapped=self.return_policy(result,'LoadFile4')
            self.evidence['original_return_policy_completed']=True;self.persist()
            return wrapped
        except BaseException as exc:
            self.invalid=True
            self.evidence.update(status='failed',first_invocation_error=dict(type=type(exc).__name__,message=str(exc)))
            self.persist();raise
