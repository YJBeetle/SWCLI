"""Portable doubles for the public independent reader. No native CAD is activated."""
from contextlib import contextmanager
from copy import deepcopy
import math
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/ci'))
from gate_support import step_periodic_driver as driver
from gate_support import step_periodic_supervisor as supervisor


class FakeAPI:
    def __init__(self,fault=None):
        self.fault=fault;self.documents=[];self.closed=[];self.exports=[];self.imports=[];self.health_records=[]
        self.events=[];self.serial=0
        self.app=SimpleNamespace(GetProcessID=1234,RevisionNumber='33.5.0',Visible=False,ActiveDoc=None,CommandInProgress=False)
        self.app.GetCurrentLanguage = 'english'
        self.app.CloseDoc=self.close
    def value(self,obj,name):
        if obj is self.app and name=='GetDocumentCount':return len(self.documents)
        value=getattr(obj,name);return value() if callable(value) else value
    def proof(self,path):
        self.events.append('proof')
        if self.fault=='proof':raise RuntimeError('first proof failure')
        return dict(synthetic_offline_test=True)
    def verify_installation(self, app, path):
        self.events.append('installation')
        if self.fault == 'installation':
            raise driver.DriverFailure('host installation differs')
        return path

    def read_constants(self, path):
        self.events.append('constants')
        return {'synthetic': True}
    def initialize(self):self.events.append('init')
    def uninitialize(self):self.events.append('uninit')
    def acquire(self):self.events.append('acquire');return self.app,self.fault!='shared'
    def ready(self,app):
        if self.fault=='ready':raise RuntimeError('first readiness failure')
    def capture(self,pid):self.events.append('capture');return 'owned-handle'
    def wait(self,handle):
        self.events.append('wait')
        if self.fault in ('wait','pid-drift'):raise RuntimeError('owned exit unconfirmed')
    def close_handle(self,handle):self.events.append('handle-close')
    def exit(self,app):
        self.events.append('exit');self.documents.clear()
        if self.fault in ('save-cleanup','cleanup'):raise RuntimeError('cleanup exit failed')
    def doc(self,readonly=False,path=''):
        self.serial+=1
        doc=SimpleNamespace(GetTitle='doc'+str(self.serial),GetPathName=str(path),GetSaveFlag=False,GetUpdateStamp=7,
                            IsOpenedReadOnly=readonly,IsOpenedViewOnly=False,GetType=1)
        self.documents.append(doc);self.app.ActiveDoc=doc
        return doc
    def save(self,path,document):
        self.events.append('save:'+Path(path).name)
        self.recorder.call('native:native-save-as:IModelDocExtension.SaveAs3',
                           lambda: Path(path).write_bytes(b'synthetic native bytes'))
        document.GetPathName=str(path)
        if self.fault=='native-save' and '-imported' in str(path):return dict(ok=False,error=dict(type='SaveFailed',message='first native save'),save_errors=8)
        return dict(ok=True,api_saved=True,save_attempted=True,save_errors=0,save_warnings=0)
    def open(self,path,app):
        document=self.doc(True,path);imported='-imported' in str(path)
        if imported and self.fault=='reopen-hash':Path(path).write_bytes(b'changed native bytes')
        if imported and self.fault=='dirty-reopen':document.GetSaveFlag=True
        if imported and self.fault=='not-readonly':document.IsOpenedReadOnly=False
        if imported and self.fault=='wrong-reopen-path':document.GetPathName=str(path)+'-wrong'
        return dict(ok=True,path=str(path),document=dict(modified=False),api_errors=0,api_warnings=(1 if imported and self.fault=='reopen-warning' else 0),read_only=True),document
    def close(self,title):
        self.closed.append(title);self.documents[:]=[doc for doc in self.documents if doc.GetTitle!=title]
        self.app.ActiveDoc=self.documents[-1] if self.documents else None
    def mass(self,document):
        body=dict(index=0,volume_mm3=3000*math.pi,surface_area_mm2=800*math.pi,centroid_mm=dict(x=0.,y=0.,z=15.))
        value=dict(ok=True,method='native-body-mass-properties',metrics=dict(solid_body_count=1,**{k:v for k,v in deepcopy(body).items() if k!='index'}),bodies=[body])
        if self.fault=='mass' and self.imports:value['metrics']['volume_mm3']=3000
        return value
    def topology(self,document):
        return dict(solid_body_count=1,face_count=4 if self.fault=='topology' and '-imported' in document.GetPathName else 3,edge_count=3)
    def health(self,document,scope,app):
        value=dict(complete=not(self.fault=='health' and scope=='imported'),features=[dict(kind='synthetic')])
        self.health_records.append(value);return value
    def compare_mass(self,before,after):driver.verify_cylinder_mass(before);driver.verify_cylinder_mass(after)
    @contextmanager
    def import_preferences(self,app,case,recorder):
        journal=case['sketch_observer_preferences']=dict(before={'synthetic':0},requested={'synthetic':1},restored=False)
        first=None
        try:yield lambda:None
        except BaseException as exc:first=exc;raise
        finally:
            journal['after']={'synthetic':0};journal['restored']=self.fault not in ('import-restore','none-restore')
            if not journal['restored']:
                journal['restore_errors']=[dict(type='RuntimeError',message='import restore failed')]
                if first is None:raise RuntimeError('import restore failed')
    def import_once(self,app,target,case,proof,verify,recorder):
        verify();recorder.call('GetImportFileData',lambda:None);self.imports.append(str(target))
        doc=recorder.call('LoadFile4',lambda:None if self.fault in ('none','none-restore') else self.doc())
        case['import_return']=dict(state='returned',document_returned=doc is not None,errors=1 if self.fault in ('none','none-restore','partial-import-error') else 0)
        return doc
