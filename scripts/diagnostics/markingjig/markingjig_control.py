"""Review-only diagnostic: fixed MarkingJig readonly copy, OpenDoc7, one modern export.
No COM at import. Inventory is metadata only; this module never copies business files.
"""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import stat
import sys

SOURCE = 'MarkingJig.REND.SLDASM'
REFERENCE_GLB_SHA = '375b01a84bd4ca1f9100f9caea44782fb84f228a82a9becd0236186a3315cb6c'
SOURCE_SHA = '80bfa9d4bc453277dc0ba4dd9dbdf8f0d315a090aa3bab429843b1f9bc308530'
AVAILABLE = (SOURCE, 'MarkingJig.SLDASM', 'M3x6_SHCS.SLDPRT', 'Magnet_D6x15.SLDPRT',
             'MarkingJigBlock.SLDPRT', 'MarkingJigBlockPrint.SLDPRT', 'MarkingJigEpoxy.SLDPRT',
             'MarkingJigRod.SLDPRT', 'MarkingJigRodPrint.SLDPRT', 'Spirit_Level.SLDPRT')
SPEC = dict(DocumentType=2, ReadOnly=True, Silent=True, UseLightWeightDefault=False,
            LightWeight=False, ViewOnly=False, LoadModel=True, AutoRepair=False)
MAX_COMPONENTS = 1024
DEPENDENCY_OPTIONS = dict(Traverseflag=True, Searchflag=False, AddReadOnlyInfo=False,
                          ListBrokenRefs=True, AppendImportedPaths=True)


def split_ctime_channels():
    # Only the already observed CPython Windows 3.14.7 path/handle ctime split.
    return os.name == 'nt' and sys.implementation.name == 'cpython' and sys.version_info[:3] == (3, 14, 7)


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))


def fingerprint(value):
    return {key: getattr(value, key, None) for key in
            ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns',
             'st_birthtime_ns', 'st_file_attributes','st_nlink')}


def stable_file(path, *, readonly=False):
    """Strict cross-channel identity; only known Windows 3.14.7 ctime stays channel-local."""
    path = Path(path)
    require(not path.is_symlink(), 'symlink input refused')
    before = fingerprint(os.stat(path, follow_symlinks=False))
    require(stat.S_ISREG(before['st_mode']) and before['st_dev'] and before['st_ino'] and
            0 < before['st_size'] <= 64*1024*1024 and not ((before['st_file_attributes'] or 0) & 0x400),
            'ordinary bounded file identity unavailable')
    if readonly:
        require(bool((before['st_file_attributes'] or 0) & 1) if os.name == 'nt'
                else not before['st_mode'] & 0o222, 'working-copy native file must be filesystem read only')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        opened = fingerprint(os.fstat(stream.fileno()))
        for key in before:
            if key == 'st_ctime_ns' and split_ctime_channels():
                continue
            require(before[key] == opened[key], 'path/opened file differs: '+key)
        remaining = before['st_size']
        while remaining:
            block = stream.read(min(65536, remaining))
            require(bool(block), 'input shortened during read')
            digest.update(block); remaining -= len(block)
        require(stream.read(1) == b'', 'input grew during read')
        closed = fingerprint(os.fstat(stream.fileno()))
        require(opened == closed, 'held input metadata changed')
    after = fingerprint(os.stat(path, follow_symlinks=False))
    require(before == after, 'input path metadata changed')
    return dict(path=str(path), size_bytes=before['st_size'], sha256=digest.hexdigest(),
                path_before=before, handle_before=opened, handle_after=closed, path_after=after)


def inventory(directory):
    root = Path(directory).resolve()
    files = {name: stable_file(root/name) for name in AVAILABLE}
    require(files[SOURCE]['sha256'] == SOURCE_SHA, 'user source assembly hash changed')
    reference=stable_file(root/'MarkingJig.REND.GLB')
    require(reference['sha256']==REFERENCE_GLB_SHA,'historical GLB changed')
    return dict(schema='swcli.markingjig-inventory.v1', source=SOURCE, files=files, protected_existing_glb=reference,
                complete_references_proven=False, purpose='available fixed candidates only; not a dependency claim',
                business_binary_copied=False)


class WorkingCopy:
    def __init__(self, inventory_record, directory, selected):
        raw_root = Path(os.path.abspath(directory))
        for parent in (raw_root, *raw_root.parents):
            info = os.stat(parent, follow_symlinks=False)
            require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                    not (getattr(info, 'st_file_attributes', 0) & 0x400),
                    'copy directory symlink/reparse refused')
        self.root = raw_root.resolve()
        require(inventory_record.get('schema') == 'swcli.markingjig-inventory.v1', 'inventory schema differs')
        require(inventory_record['source'] == SOURCE and inventory_record['files'][SOURCE]['sha256'] == SOURCE_SHA,
                'fixed source identity differs')
        require(type(selected) is list and SOURCE in selected and len(set(selected)) == len(selected)
                and set(selected) <= set(AVAILABLE), 'explicit fixed copy list required')
        self.files = {name: inventory_record['files'][name] for name in selected}
        self.before = self.snapshot()

    def snapshot(self):
        require(all(p.name in self.files for p in self.root.iterdir() if p.suffix.casefold() in ('.sldprt','.sldasm')), 'unlisted native input file')
        rows = {}
        for name, pinned in self.files.items():
            row = stable_file(self.root/name, readonly=True)
            require(row['path_before']['st_nlink']==1,'working copy must not be a hard link')
            require((row['sha256'], row['size_bytes']) == (pinned['sha256'], pinned['size_bytes']), 'working copy differs: '+name)
            rows[name] = row
        return rows

    def unchanged(self):
        after = self.snapshot()
        require(after == self.before, 'working-copy bytes/identity/state changed')
        return after

    def external(self, raw_path):
        require(type(raw_path) is str and raw_path, 'external path missing')
        name = PureWindowsPath(raw_path).name if '\\' in raw_path else Path(raw_path).name
        names = [n for n in self.files if n.casefold() == name.casefold()]
        require(len(names) == 1, 'external reference outside fixed copy list: '+name)
        actual, expected = Path(raw_path), self.root/names[0]
        require(actual.is_file() and os.path.samefile(actual, expected), 'loaded file is outside private copy')
        return names[0]


def exact(value, kind, reason):
    require(type(value) is kind, reason)
    return value


def vector(value, size, reason):
    require(isinstance(value, (tuple, list)) and len(value) == size and all(
        type(x) in (int, float) and math.isfinite(x) for x in value), reason)
    return list(value)


class Observation:
    def __init__(self, app, value, call, copy, constants, owned_pid, process_identity, *,
                 component_context_policy='strict-model-configuration', component_bodies=None):
        self.app, self.value, self.call, self.copy = app, value, call, copy
        self.constants, self.owned_pid, self.process_identity = constants, owned_pid, process_identity
        self.component_context_policy, self.component_bodies = component_context_policy, component_bodies
        require(component_context_policy in ('strict-model-configuration','component-bodies-probe'),'component context policy unknown')
        require(component_context_policy=='strict-model-configuration' or callable(component_bodies),'component body binding required')

    def get(self, obj, name, *args):
        return self.call('read-'+name, lambda: getattr(obj, name)(*args) if args else self.value(obj, name))

    def same(self, first, second, reason):
        require(exact(self.get(self.app, 'IsSame', first, second), int, reason) == 1, reason)

    def document(self, doc, row, *, top=False, embedded=False):
        # Populate caller-owned rows one value at a time: late errors preserve earlier observations.
        for member, key, kind in (
            ('GetType','type',int), ('GetPathName','path',str), ('GetTitle','title',str),
            ('GetUpdateStamp','stamp',int), ('GetSaveFlag','modified',bool),
            ('IsOpenedReadOnly','readonly',bool), ('IsOpenedViewOnly','viewonly',bool)):
            row[key] = exact(self.get(doc, member), kind, 'unreadable document '+key)
        require(row['type'] in (1,2) and not row['modified'] and not row['viewonly'], 'unknown/dirty/view-only model')
        require(row['readonly'] or embedded, 'external native model not opened read only')
        extension = self.get(doc, 'Extension')
        row['needs_rebuild'] = exact(self.get(extension, 'NeedsRebuild2'), int, 'rebuild state unknown')
        require(row['needs_rebuild'] == 0, 'model requires rebuild; no repair')
        manager = self.get(doc, 'ConfigurationManager')
        config = self.get(manager, 'ActiveConfiguration')
        row['configuration'] = exact(self.get(config, 'Name'), str, 'configuration unknown')
        require(bool(row['configuration']), 'configuration empty')
        names = self.get(doc, 'GetConfigurationNames')
        require(isinstance(names,(list,tuple)) and row['configuration'] in names and all(type(n) is str for n in names), 'configuration set unknown')
        row['configurations'] = list(names)
        sketches = self.get(doc, 'SketchManager')
        require(sketches is not None and self.get(sketches,'ActiveSketch') is None, 'sketch edit/unknown')
        if row['type'] == 2:
            self.same(self.get(doc,'GetEditTarget'), doc, 'assembly edit target differs/unknown')
            require(self.get(doc,'HasUnloadedComponents') is False, 'unloaded assembly references')
            require(exact(self.get(doc,'GetLightWeightComponentCount'),int,'lightweight count unknown') == 0, 'initial lightweight assembly')
        if top:
            require(row['type']==2 and row['readonly'], 'top source is not readonly assembly')
            self.same(doc,self.get(self.app,'ActiveDoc'),'foreground changed')
        else:
            row['geometry'] = self.geometry(doc, row['type'])
        return row

    def geometry(self, doc, kind):
        if kind == 2:
            return dict(kind='subassembly', model_state_observed=True)
        bodies = self.get(doc,'GetBodies2',-1,False)
        require(isinstance(bodies,(list,tuple)) and 0 < len(bodies) <= 8192,'part body geometry unavailable')
        rows=[]
        for body in bodies:
            bounds=vector(self.get(body,'GetBodyBox'),6,'body bounds unknown')
            require(all(bounds[i] <= bounds[i+3] for i in range(3)),'body bounds reversed')
            props=vector(self.get(body,'GetMassProperties',1.0),12,'body mass geometry unavailable')
            require(props[3]>=0 and props[4]>0,'body area/volume invalid')
            rows.append(dict(type=exact(self.get(body,'GetType'),int,'body type unknown'),bounds=bounds,
                             volume_m3=props[3],area_m2=props[4],centroid_m=props[:3],
                             faces=exact(self.get(body,'GetFaceCount'),int,'face count unknown'),
                             edges=exact(self.get(body,'GetEdgeCount'),int,'edge count unknown')))
        return rows

    def component_geometry(self, component, model, row):
        """Assembly-instance bodies and independent modelDoc state; no activation."""
        context = row['component_context'] = dict(complete=False, policy='component-bodies-probe',
            model_active_configuration=row['model']['configuration'],
            referenced_configuration=row['referenced_configuration'],
            model_active_matches_reference=row['model']['configuration']==row['referenced_configuration'],
            model_geometry_basis='GetModelDoc2 active-document state only')
        if row['model']['type'] == 2:
            # GetBodies3 explicitly supports part components only. Nested part
            # instances remain in the original complete flat component census.
            context.update(kind='subassembly', geometry_basis='complete child component census')
        else:
            context.update(kind='part', geometry_basis='IComponent2.GetBodies3; native body values, no transform applied',
                           requested_body_type=self.constants['swAllBodies'])
            raw = self.call('read-component-GetBodies3', lambda: self.component_bodies(component, self.constants['swAllBodies']))
            require(type(raw) is tuple and len(raw)==2, 'component body binding result unknown')
            bodies, info = raw
            context['bodies_returned_type'] = type(bodies).__name__
            context['body_info_returned_type'] = type(info).__name__
            context['body_count'] = len(bodies) if isinstance(bodies,(tuple,list)) else None
            # Preserve unexpected primitive out values too, without serializing COM
            # objects or asking them for a string representation on failure.
            def primitive(v):
                if type(v) in (int,str,bool,type(None)):return v
                if type(v) is float:return v if math.isfinite(v) else dict(unexpected_type='float',hex_value=v.hex())
                return dict(unexpected_type=type(v).__name__)
            context['body_info_raw'] = [primitive(v) for v in info] if isinstance(info,(tuple,list)) else primitive(info)
            require(isinstance(bodies,(tuple,list)) and 0<len(bodies)<=8192, 'component bodies unavailable')
            require(isinstance(info,(tuple,list)) and len(info)==len(bodies)
                    and all(type(v) is int and v in (self.constants['swUserBody_e'],self.constants['swNormalBody_e']) for v in info),
                    'component body-info shape/value unknown')
            geometry = context['bodies'] = []
            for body, classification in zip(bodies,info):
                current = dict(body_info=classification); geometry.append(current)
                current['type'] = exact(self.get(body,'GetType'),int,'component body type unknown')
                require(current['type'] in (self.constants['swSolidBody'],self.constants['swSheetBody']), 'unsupported component body type')
                require(not (current['type']==self.constants['swSheetBody'] and classification==self.constants['swUserBody_e']),
                        'surface body cannot be classified as user body')
                current['bounds_raw'] = self.get(body,'GetBodyBox')
                current['bounds'] = bounds = vector(current['bounds_raw'],6,'component body bounds unknown')
                require(all(bounds[i]<=bounds[i+3] for i in range(3)), 'component body bounds reversed')
                current['mass_properties_raw'] = self.get(body,'GetMassProperties',1.0)
                props = vector(current['mass_properties_raw'],12,'component mass geometry unavailable')
                require(props[3]>=0 and props[4]>0, 'component body area/volume invalid')
                current.update(volume_m3=props[3],area_m2=props[4],centroid_m=props[:3])
                current['faces'] = exact(self.get(body,'GetFaceCount'),int,'component face count unknown')
                current['edges'] = exact(self.get(body,'GetEdgeCount'),int,'component edge count unknown')
                require(current['faces']>0 and current['edges']>=0, 'component topology counts invalid')
        self.same(self.get(component,'GetModelDoc2'),model,'component model identity changed during body observation')
        context['referenced_configuration_after'] = exact(self.get(component,'ReferencedConfiguration'),str,'reference configuration unknown after geometry')
        require(context['referenced_configuration_after']==row['referenced_configuration'], 'component reference configuration changed during body observation')
        after = context['model_state_after'] = {}
        self.document(model,after,embedded=row['virtual'])
        require(canonical(after)==canonical(row['model']), 'independent model state changed during component body observation')
        context['complete'] = True

    def dependencies(self, model, state, report):
        query = dict(model_path=state['path'], reads=[], independent_native_string_count=None,
                     count_basis='returned five-argument SAFEARRAY only; no documented comparable native counter')
        report.append(query)
        extension = self.get(model, 'Extension')
        require(extension is not None, 'dependency extension unavailable')
        arrays = []
        # Inclusive first. The fixed second read classifies broken refs, never a fallback/retry.
        for include_broken in (True, False):
            options = dict(DEPENDENCY_OPTIONS, ListBrokenRefs=include_broken)
            read = dict(options=options); query['reads'].append(read)
            raw = self.get(extension, 'GetDependencies', *options.values())
            read['returned_type'] = type(raw).__name__
            if isinstance(raw, (tuple, list)):
                read['raw_strings'] = list(raw) if all(type(x) is str for x in raw) else None
                read['returned_string_count'] = len(raw)
            else:
                read['raw_strings'] = None
            # No unsupported conversion of None/VT_EMPTY into a proven zero count.
            require(isinstance(raw, (tuple, list)), 'modern dependency array unknown; no legacy count fallback')
            require(len(raw) <= 4096 and len(raw) % 2 == 0 and all(type(x) is str and x for x in raw),
                    'modern dependency pair array malformed/incomplete')
            arrays.append(list(raw))
        inclusive, without_broken = arrays
        pairs = lambda raw: Counter(zip(raw[::2], raw[1::2]))
        require(pairs(inclusive) == pairs(without_broken), 'broken dependency or inconsistent inclusive census; no save')
        query['broken_census_equal'] = True
        return inclusive

    def snapshot(self, doc, report):
        result = dict(complete=False, host={}, top={}, components=[], dependencies=[], dependency_queries=[], catalog=[])
        report.append(result)
        self.copy.unchanged()
        h=result['host'];h['pid']=exact(self.get(self.app,'GetProcessID'),int,'host PID unknown')
        require(h['pid']==self.owned_pid,'owned host changed')
        h.update(self.process_identity(h['pid']))
        h['revision']=exact(self.get(self.app,'RevisionNumber'),str,'runtime revision unknown')
        require(h['revision']=='33.5.0','runtime differs from the current controlled environment')
        for member in ('Visible','CommandInProgress','UserControl','UserControlBackground'):
            h[member]=exact(self.get(self.app,member),bool,'host flag unknown')
        require(h['Visible'] is False,'owned hidden mode changed')
        self.document(doc,result['top'],top=True)
        require(self.copy.external(result['top']['path'])==SOURCE,'top source differs')
        components=self.get(doc,'GetComponents',False)
        require(isinstance(components,(list,tuple)) and 0<len(components)<=MAX_COMPONENTS,'component graph unavailable')
        require(exact(self.get(doc,'GetComponentCount',False),int,'component count unknown')==len(components),'component graph incomplete')
        models=[(doc,result['top'],False)]; by_name={}; virtual_paths={}; virtual_instances={}
        for component in components:
            row={};result['components'].append(row)
            row['name']=exact(self.get(component,'Name2'),str,'component name unknown')
            require(row['name'] and row['name'] not in by_name,'ambiguous component name')
            by_name[row['name']]=(component,row)
            row['path']=exact(self.get(component,'GetPathName'),str,'component path unknown')
            row['virtual']=exact(self.get(component,'IsVirtual'),bool,'virtual state unknown')
            row['suppression']=exact(self.get(component,'GetSuppression2'),int,'component suppression unknown')
            require(row['suppression'] in (self.constants['swComponentFullyResolved'],self.constants['swComponentResolved']), 'component not initially resolved')
            require(self.get(component,'IsSuppressed') is False and self.get(component,'HasUnloadedComponents') is False,'suppressed/unloaded component')
            child=self.get(component,'GetModelDoc2');require(child is not None,'component model not loaded')
            row['model']={};self.document(child,row['model'],embedded=row['virtual'])
            row['referenced_configuration']=exact(self.get(component,'ReferencedConfiguration'),str,'reference configuration unknown')
            if self.component_context_policy=='strict-model-configuration':
                require(row['referenced_configuration']==row['model']['configuration'],'component model represents different configuration; no activation')
            else:
                require(row['referenced_configuration'] and row['referenced_configuration'] in row['model']['configurations'],
                        'component referenced configuration absent from independent model configuration set')
            transform=self.get(component,'Transform2');require(transform is not None,'component transform unknown')
            row['transform']=vector(self.get(transform,'ArrayData'),16,'component transform unknown')
            if not row['virtual']:
                row['file']=self.copy.external(row['path'])
                require(self.copy.external(row['model']['path'])==row['file'],'component/model file differs')
            else:
                require(row['model']['path'],'virtual model path unavailable')
                virtual_paths[row['model']['path']]=row
                virtual_instances.setdefault(row['model']['path'],[]).append((child,row))
            if self.component_context_policy=='component-bodies-probe':
                self.component_geometry(component,child,row)
            models.append((child,row['model'],row['virtual']))
        for component,row in by_name.values():
            if row['virtual']:
                parent=self.get(component,'GetParent');seen=set()
                while parent is not None:
                    name=exact(self.get(parent,'Name2'),str,'virtual owner name unknown')
                    require(name in by_name and name not in seen,'virtual ownership incomplete/cyclic');seen.add(name)
                    parent_row=by_name[name][1]
                    if not parent_row['virtual']:
                        require(parent_row['model']['type']==2,'virtual owner is not assembly');row['owner_file']=parent_row['file'];break
                    parent=self.get(parent,'GetParent')
                else:row['owner_file']=SOURCE
                require(row['owner_file'] in self.copy.files,'embedded owner outside fixed inputs')
        for instances in virtual_instances.values():
            first_model,first_row=instances[0]
            for current_model,current_row in instances[1:]:
                require(current_row['owner_file']==first_row['owner_file'] and canonical(current_row['model'])==canonical(first_row['model']), 'ambiguous embedded source ownership/state')
                self.same(current_model,first_model,'embedded source identities differ')
        # Modern traversal includes suppressed/derived/broken refs and imported origins.
        top_dependency_files = set()
        for model_index,(model,state,embedded) in enumerate(models):
            raw=self.dependencies(model,state,result['dependency_queries'])
            for index in range(0,len(raw),2):
                pair=dict(name=raw[index],stored_path=raw[index+1],model_path=state['path'])
                result['dependencies'].append(pair)
                require('|' not in pair['stored_path'], 'imported source dependency outside approved native inputs; no stripping/omission')
                virtual=[v for path,v in virtual_paths.items() if
                         PureWindowsPath(path).name.casefold()==PureWindowsPath(pair['stored_path']).name.casefold()]
                if virtual:
                    require(len(virtual)==1,'ambiguous embedded dependency')
                    pair['embedded_owner']=virtual[0]['owner_file'];pair['loaded_virtual_path']=virtual[0]['model']['path']
                else:
                    name=PureWindowsPath(pair['stored_path']).name
                    matching=[n for n in self.copy.files if n.casefold()==name.casefold()]
                    require(len(matching)==1,'dependency outside fixed list; do not guess/copy')
                    pair['file']=matching[0]
                    if model_index == 0:top_dependency_files.add(matching[0])
                    loaded=self.get(self.app,'GetOpenDocumentByName',str(self.copy.root/matching[0]))
                    require(loaded is not None,'dependency not loaded in initial complete model')
                    known=[m for m,s,v in models if not v and s['path'] and self.copy.external(s['path'])==matching[0]]
                    require(bool(known),'dependency model not represented in complete loaded graph')
                    self.same(loaded,known[0],'loaded dependency identity differs')
        expected_external={row['file'] for component,row in by_name.values() if not row['virtual']}
        require(expected_external <= top_dependency_files, 'modern recursive dependencies omit loaded external component')
        docs=self.get(self.app,'GetDocuments');require(isinstance(docs,(list,tuple)),'document catalog unknown')
        require(exact(self.get(self.app,'GetDocumentCount'),int,'catalog count unknown')==len(docs),'catalog incomplete')
        for current in docs:
            key=(self.get(current,'GetPathName'),self.get(current,'GetTitle'))
            known=[m for m,s,v in models if (s['path'],s['title'])==key]
            require(bool(known),'unexpected loaded native document')
            self.same(current,known[0],'catalog document identity differs');result['catalog'].append(list(key))
        require([result['top']['path'],result['top']['title']] in result['catalog'],'top missing from catalog')
        final_top={};self.document(doc,final_top,top=True)
        require(canonical(final_top)==canonical(result['top']),'top source state changed while observing')
        if self.component_context_policy=='component-bodies-probe':
            require(any(row['model']['type']==1 and row['component_context']['complete']
                        for component,row in by_name.values()), 'complete census has no part component geometry')
        self.copy.unchanged();result['complete']=True
        return result


def open_readonly(app, source, value, call, live, report, constants):
    readonly_warning=exact(constants.get('swFileLoadWarning_ReadOnly'),int,'installed readonly warning enum unknown')
    require(readonly_warning==2,'installed readonly warning enum differs')
    spec=call('get-open-spec',lambda:app.GetOpenDocSpec(str(source)))
    require(spec is not None,'OpenDoc7 specification missing')
    report['requested_spec']=dict(SPEC);report['actual_spec']={}
    for key,wanted in SPEC.items():
        call('set-open-spec-'+key,lambda key=key,wanted=wanted:setattr(spec,key,wanted))
        actual=call('read-open-spec-'+key,lambda key=key:value(spec,key));report['actual_spec'][key]=actual
        require(type(actual) is type(wanted) and actual==wanted,'OpenDoc7 spec did not retain '+key)
    doc=call('OpenDoc7-readonly',lambda:app.OpenDoc7(spec));live['document']=doc
    report['open_errors']=exact(value(spec,'Error'),int,'OpenDoc7 error code unknown')
    report['open_warnings']=exact(value(spec,'Warning'),int,'OpenDoc7 warning code unknown')
    require(doc is not None and report['open_errors']==0, 'OpenDoc7 failed; no alternate opening')
    warning=report['open_warnings']
    require(warning in (0,readonly_warning), 'OpenDoc7 unexpected warning; no alternate opening')
    report['open_warning_policy']=dict(raw_warning=warning,installed_readonly_value=readonly_warning,
                                      exact_readonly_warning=warning==readonly_warning,complete_model_gate_still_required=True)
    if warning==readonly_warning:
        require(report['actual_spec']['ReadOnly'] is True, 'readonly warning without requested/readback readonly')
        checks=report['expected_readonly_warning_model']={}
        for member,key,wanted in (('IsOpenedReadOnly','readonly',True),('GetSaveFlag','modified',False),
                                  ('IsOpenedViewOnly','viewonly',False)):
            raw=call('read-open-model-'+key,lambda member=member:value(doc,member));checks[key]=raw
            require(type(raw) is bool and raw is wanted, 'readonly warning actual model state differs/unknown: '+key)
        checks['provisional_only']=True
    return doc


def one_case(app, copy, mode, output, value, call, live, report, constants, owned_pid, exporter, process_identity, *, phase_guard=None,
             component_context_policy='strict-model-configuration', component_bodies=None):
    require(mode in ('probe','invoke'),'mode required')
    require(component_context_policy in ('strict-model-configuration','component-bodies-probe'),'component context policy unknown')
    if component_context_policy=='component-bodies-probe':
        require(mode=='probe' and phase_guard is not None and callable(component_bodies),
                'component bodies require explicit opening-transition zero-export probe and binding')
        require(all(type(constants.get(k)) is int and constants[k]==v for k,v in
                    dict(swAllBodies=-1,swSolidBody=0,swSheetBody=1,swUserBody_e=0,swNormalBody_e=1).items()),
                'installed component-body constants differ')
        report['component_context_policy']=component_context_policy
    report.update(mode=mode,observations=[],export_attempts=0,geometry_comparison='before/after same loaded native models; historical display context unknown')
    if phase_guard is not None:
        require(mode=='probe', 'opening-transition candidate is zero-export probe only')
        report['phase_policy']='opening-transition-probe'
        phase_guard.before_open()
        try:
            doc=open_readonly(app,copy.root/SOURCE,value,call,live,report,constants)
        except BaseException:
            # Capture after even a failed opening, without replacing its original error.
            try:phase_guard.after_open()
            except BaseException as error:
                report['failed_open_phase_capture_error']=dict(type=type(error).__name__,message=str(error))
            raise
        phase_guard.after_open()
        observer=Observation(app,value,call,phase_guard,constants,owned_pid,process_identity,
                             component_context_policy=component_context_policy,component_bodies=component_bodies)
        admitted=observer.snapshot(doc,report['observations'])
        phase_guard.seal_loaded(admitted)
        loaded=observer.snapshot(doc,report['observations'])
        require(canonical(admitted)==canonical(loaded), 'loaded-stage complete model state changed')
        phase_guard.unchanged()
        report['probe_success']=True
        return
    doc=open_readonly(app,copy.root/SOURCE,value,call,live,report,constants)
    observer=Observation(app,value,call,copy,constants,owned_pid,process_identity)
    before=observer.snapshot(doc,report['observations'])
    if mode=='probe':report['probe_success']=True;return
    require(not report['export_attempts'],'one export only');report['export_attempts']=1
    report['export_result']=result=call('export-modern-GLB',lambda:exporter(str(Path(output)/'MarkingJig.REND.GLB'),app=app,document=doc,strict=True))
    # Product exporter keeps its original staging/SaveAs3/manifest/strict BIN policy.
    require(result.get('ok') is True,'first export native/content failure; no postfailure CAD reads')
    after=observer.snapshot(doc,report['observations'])
    require(canonical(before)==canonical(after),'export changed complete source/model/reference/geometry snapshot')
    report['success']=True
