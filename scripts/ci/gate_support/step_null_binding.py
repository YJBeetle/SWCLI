"""Prove a single NULL IDispatch argument without changing its method binding.

No Invoke/InvokeTypes call is made by inspection. Unknown metadata fails closed.
Native pointer evidence is explicitly derived from b312 conversion source plus
actual Python argument/signature, never presented as native-memory inspection.
"""
import hashlib
from pathlib import Path
from types import CodeType, MethodType
from gate_support.step_binding_observation import snapshot_state

PACKAGE_SHA = {
    'dynamic': 'b217819b4d9b1cbd474b463b4181a683e311d2cf0a2a14fd1dd1b00595bb7797',
    'build': 'ef246eee3d2bb7b852d522b65a155678f3fc01f7010c1c38f5ed6c8b7424056f',
    'client': 'a0fa92dcf3bd6cb6ce8bba38c6bee95b12b95a325852b1dbeb559464d431b36a',
}
SOURCES = {
    'dynamic': 'https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/dynamic.py',
    'build': 'https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/build.py',
    'client': 'https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/__init__.py',
    'conversion': 'https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/oleargs.cpp',
    'interface_conversion': 'https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyComHelpers.cpp',
}


def require(condition, message):
    if not condition:
        raise RuntimeError('NULL binding refused: ' + message)


def modules():
    import win32com.client as client
    from win32com.client import build, dynamic
    return dynamic, build, client


def attest_package():
    dynamic, build, client = modules()
    result = dict(verified=False, version_requirement='312; checked by worker', normalization='CRLF to LF only', sources=SOURCES,
        conversion_source_sha256={'oleargs.cpp':'f57f75638443b740f36c8273381f6b63d78beca371112867bb125f973f55efab',
                                  'PyComHelpers.cpp':'d048ca6567c82595237c7a46f8a0b469805f1589e2cfca9510eca79f96cf61ce'},files={})
    bodies = {}
    for name, module in [('dynamic',dynamic),('build',build),('client',client)]:
        path = Path(module.__file__)
        raw = path.read_bytes()
        bodies[name] = raw.replace(b'\r\n',b'\n')
        digest = hashlib.sha256(bodies[name]).hexdigest()
        result['files'][name] = dict(path=str(path),normalized_sha256=digest)
        require(digest == PACKAGE_SHA[name], 'installed b312 source differs: '+name)
    compiled = compile(bodies['dynamic'],str(dynamic.__file__),'exec',dont_inherit=True)
    cls = next(x for x in compiled.co_consts if isinstance(x,CodeType) and x.co_name == 'CDispatch')
    expected = {x.co_name:x for x in cls.co_consts if isinstance(x,CodeType)}
    result['runtime_return_handlers'] = {}
    for name in ('_get_good_object_','_get_good_single_object_','_wrap_dispatch_'):
        actual = getattr(dynamic.CDispatch,name)
        require(code_key(actual.__code__) == code_key(expected[name]),'runtime return helper differs: '+name)
        result['runtime_return_handlers'][name] = code_digest(actual.__code__)
    result['runtime_handlers'] = {}
    for name in HANDLERS:
        actual = getattr(dynamic.CDispatch,name)
        require(isinstance(actual.__code__,CodeType) and code_key(actual.__code__) == code_key(expected[name]),
                'runtime handler differs from verified source: '+name)
        result['runtime_handlers'][name] = code_digest(actual.__code__)
    client_compiled = compile(bodies['client'],str(client.__file__),'exec',dont_inherit=True)
    client_cls = next(x for x in client_compiled.co_consts if isinstance(x,CodeType) and x.co_name == 'CDispatch')
    client_expected = {x.co_name:x for x in client_cls.co_consts if isinstance(x,CodeType)}
    result['client_wrapper_handlers'] = {}
    for name in CLIENT_HANDLERS:
        actual = getattr(client.CDispatch,name)
        require(code_key(actual.__code__) == code_key(client_expected[name]),'client wrapper differs from verified source: '+name)
        result['client_wrapper_handlers'][name] = code_digest(actual.__code__)
    result['client_factory_handlers'] = {}
    factory_expected = {x.co_name:x for x in client_compiled.co_consts if isinstance(x,CodeType)}
    for name in CLIENT_FACTORIES:
        actual = getattr(client,name)
        require(code_key(actual.__code__) == code_key(factory_expected[name]),'client factory differs from verified source: '+name)
        result['client_factory_handlers'][name] = code_digest(actual.__code__)
    verify_handlers(dynamic,result)
    verify_client_wrapper(dynamic,client,result)
    result['verified'] = True
    return result


def code_key(code):
    """Ignore filenames/line tables; retain instructions/constants and closure ABI."""
    def constant(value):
        if isinstance(value,CodeType):return ('code',code_key(value))
        if isinstance(value,tuple):return ('tuple',tuple(constant(x) for x in value))
        if isinstance(value,slice):return ('slice',constant(value.start),constant(value.stop),constant(value.step))
        require(type(value) in (int,str,bytes,float,bool,type(None)), 'unrecognized code constant')
        return (type(value).__name__,value)
    return (code.co_code, tuple(constant(x) for x in code.co_consts), code.co_names,
            code.co_varnames, code.co_argcount, code.co_kwonlyargcount, code.co_posonlyargcount,
            code.co_flags, code.co_freevars, code.co_cellvars,
            code.co_stacksize, getattr(code,'co_exceptiontable',b''))


HANDLERS = ('__getattr__','_LazyAddAttr_','_make_method_','_ApplyTypes_')
CLIENT_HANDLERS = ('_wrap_dispatch_','__dir__')
CLIENT_FACTORIES = ('DispatchEx','Dispatch','__WrapDispatch')
INSTANCE_OVERRIDES = HANDLERS + CLIENT_HANDLERS + ('LoadFile4',)


def code_digest(code):
    return hashlib.sha256(repr(code_key(code)).encode()).hexdigest()


def verify_handlers(dynamic, package):
    require(dynamic.CDispatch.__getattribute__ is object.__getattribute__, 'runtime attribute lookup changed')
    proof = package.get('runtime_handlers',{})
    for name in HANDLERS:
        function = getattr(dynamic.CDispatch,name)
        require(isinstance(getattr(function,'__code__',None),CodeType) and
                code_digest(function.__code__) == proof.get(name), 'runtime binding handler changed: '+name)


def verify_client_wrapper(dynamic, client, package):
    cls = client.CDispatch
    require(cls is not dynamic.CDispatch and cls.__bases__ == (dynamic.CDispatch,) and
            cls.__mro__ == (cls,dynamic.CDispatch,object), 'client wrapper inheritance differs')
    for name in HANDLERS + ('__getattribute__','_get_good_object_','_get_good_single_object_'):
        require(getattr(cls,name) is getattr(dynamic.CDispatch,name),'client overrides inherited binding: '+name)
    require('LoadFile4' not in cls.__dict__ and 'LoadFile4' not in dynamic.CDispatch.__dict__, 'class overrides normal LoadFile4 lookup')
    for name in CLIENT_HANDLERS:
        function = getattr(cls,name)
        require(isinstance(getattr(function,'__code__',None),CodeType) and
                code_digest(function.__code__) == package.get('client_wrapper_handlers',{}).get(name),
                'client wrapper handler changed: '+name)
    for name in CLIENT_FACTORIES:
        function = getattr(client,name)
        require(isinstance(getattr(function,'__code__',None),CodeType) and
                code_digest(function.__code__) == package.get('client_factory_handlers',{}).get(name),
                'client acquisition/return policy changed: '+name)


class NullDispatchBinding:
    def __init__(self, raw, variant_class, package, evidence, persist):
        self.raw, self.variant_class = raw, variant_class
        self.evidence, self.persist = evidence, persist
        self.method = self.argument = None
        self.invalid = self.invoked = False
        evidence.update(status='started',wrapper_type=type(raw).__module__+'.'+type(raw).__qualname__,
            bound_method_invocation_attempted=False,mode='same bound method; no replacement invocation')
        persist()
        require(package is not None and package.get('verified') is True, 'package source was not verified')
        dynamic, build, client = modules()
        verify_handlers(dynamic,package)
        self.dynamic, self.client, self.package = dynamic,client,package
        self.wrapper_class = type(raw)
        self.is_client_wrapper = type(raw) is getattr(client,'CDispatch',None)
        require(type(raw) is dynamic.CDispatch or self.is_client_wrapper, 'unsupported wrapper class; do not replace it')
        if self.is_client_wrapper:
            verify_client_wrapper(dynamic,client,package)
            evidence.update(wrapper_family='exact client.CDispatch; inherited dynamic binding',
                wrapper_mro=[x.__module__+'.'+x.__qualname__ for x in type(raw).__mro__],
                binding_handlers_inherited=True,return_wrapper_policy_preserved=True)
        else:
            evidence['wrapper_family'] = 'exact dynamic.CDispatch'
        require(variant_class is client.VARIANT, 'unverified VARIANT implementation')
        state = object.__getattribute__(raw,'__dict__')
        require(not any(key in state for key in INSTANCE_OVERRIDES),
                'instance overrides normal binding')
        representation = state.get('_olerepr_')
        require(type(representation) in (build.DispatchItem,build.LazyDispatchItem), 'unknown method-map implementation')
        require(type(representation).MakeFuncMethod is build.DispatchItem.MakeFuncMethod, 'custom method generator')
        evidence['existing_python_state'] = snapshot_state(state,build)
        persist()
        if 'LoadFile4' not in representation.mapFuncs:
            # Exact b312 lazy metadata path used by normal __getattr__. It only
            # binds type information. Never continue to unknown-member Invoke.
            require(state.get('_lazydata_') is not None, 'no known method and no readable lazy metadata')
            evidence['metadata_lookup'] = 'existing _LazyAddAttr_ only; no unknown-member fallback'
            persist()
            raw._LazyAddAttr_('LoadFile4')
        entry = representation.mapFuncs.get('LoadFile4')
        require(type(entry) is build.MapEntry and entry.dispid == 227, 'LoadFile4 method entry unavailable/mismatched')
        require(entry.names and tuple(entry.names[:1]) == ('LoadFile4',), 'method name differs')
        if entry.desc is None:
            route = 'generic-Invoke'
            evidence['resolved_signature'] = None
        else:
            desc = entry.desc
            require(desc[0] == 227 and desc[4] == 1 and desc[6] == 0, 'DISPID/invkind/optional metadata differs')
            args = tuple(tuple(x[:2]) for x in desc[2])
            require(args[:4] == ((8,1),(8,1),(9,1),(16387,3)), 'typed argument ABI differs')
            require(len(args) == 4 or len(args) == 5 and args[4] == (16393,10), 'unrecognized retval projection')
            require(tuple(entry.names[:5]) == ('LoadFile4','FileName','ArgString','ImportData','Errors'), 'typed parameter names differ')
            route = 'typed-ApplyTypes-InvokeTypes'
            evidence['resolved_signature'] = dict(dispid=desc[0],invkind=desc[4],optional_count=desc[6],
                argument_types=args,return_type=tuple(desc[8][:2]),names=tuple(entry.names))
        source = '\n'.join(representation.MakeFuncMethod(entry,'LoadFile4',0))
        compiled = compile(source,'<reviewed normal LoadFile4 binding>','exec')
        expected = [x for x in compiled.co_consts if isinstance(x,CodeType) and x.co_name == 'LoadFile4']
        require(len(expected) == 1, 'normal generator did not produce one method')
        evidence.update(route=route,generator_source=source,generator_source_sha256=hashlib.sha256(source.encode()).hexdigest())
        persist()
        method = getattr(raw,'LoadFile4')  # Safe: exact class and known map entry above.
        require(isinstance(method,MethodType) and method.__self__ is raw, 'method is not bound to this host')
        require(state.get('_builtMethods_',{}).get('LoadFile4') is method.__func__, 'method-cache identity differs')
        require(code_key(method.__func__.__code__) == code_key(expected[0]), 'actual bound method differs from normal generator')
        names = set(method.__func__.__code__.co_names)
        if route == 'generic-Invoke':
            require(names == {'_get_good_object_','_oleobj_','Invoke'}, 'unknown generic invocation code')
            argument = variant_class(9,None)
        else:
            require(names == {'_ApplyTypes_'}, 'unknown typed invocation code')
            apply = raw._ApplyTypes_
            require(isinstance(apply,MethodType) and apply.__self__ is raw and apply.__func__ is dynamic.CDispatch._ApplyTypes_,
                    'typed conversion method replaced')
            argument = None
        self.method, self.argument = method, argument
        self.function = method.__func__
        self.function_digest = code_digest(method.__func__.__code__)
        self.state = state
        self.route = route
        evidence.update(status='verified',bound_receiver_same=True,normal_generator_code_equal=True,
            bound_function_code_sha256=self.function_digest,bound_function_filename=self.function.__code__.co_filename,
            factory_object_role='observation only; never the LoadFile4 ImportData argument',
            conversion_sources=dict(oleargs=SOURCES['conversion'],interfaces=SOURCES['interface_conversion']),
            pointer_evidence_kind='b312 conversion proof + observed argument/signature; no native-memory inspection')
        self.validate(argument)
        persist()

    def validate(self, argument):
        try:
            require(not self.invalid,'previous binding/argument refusal; no fallback')
            self._validate(argument)
        except BaseException as exc:
            self.invalid = True
            self.evidence.update(status='unknown',validation_error=dict(type=type(exc).__name__,message=str(exc)))
            self.persist()
            raise

    def _validate(self, argument):
        verify_handlers(self.dynamic,self.package)
        require(type(self.raw) is self.wrapper_class, 'wrapper identity changed after inspection')
        if self.is_client_wrapper:
            verify_client_wrapper(self.dynamic,self.client,self.package)
        require(code_digest(self.function.__code__) == self.function_digest, 'bound method code changed')
        require(not any(key in self.state for key in INSTANCE_OVERRIDES), 'binding instance changed')
        require(self.method is not None and self.method.__self__ is self.raw and
                self.state.get('_builtMethods_',{}).get('LoadFile4') is self.function, 'bound method changed after inspection')
        if self.route == 'generic-Invoke':
            require(argument is self.argument and type(argument) is self.variant_class and
                    type(argument.varianttype) is int and argument.varianttype == 9 and argument.value is None,
                    'generic ImportData must be the inspected VT_DISPATCH/null carrier')
            payload = dict(python_form='VARIANT(VT_DISPATCH,None)',observed_varianttype=argument.varianttype,
                           observed_value_is_none=argument.value is None)
        else:
            require(argument is None,'typed ImportData must be None under verified DISPATCH signature')
            payload = dict(python_form='None',observed_value_is_none=True,signature_vartype=9)
        self.evidence['actual_argument'] = {**payload,'effective_vartype':9,'null_dispatch_pointer_by_conversion_proof':True}
        self.persist()

    def invoke_original(self, path, arguments, argument, errors):
        self.validate(argument)
        require(not self.invoked,'only one original method invocation')
        self.invoked = True
        self.evidence['bound_method_invocation_attempted'] = True
        self.persist()
        return self.method(path,arguments,argument,errors)
