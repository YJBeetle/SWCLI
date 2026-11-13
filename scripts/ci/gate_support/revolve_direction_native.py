"""Lazy native backend for the direction singleton; never imported by public SWCLI."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import time

from .revolve_direction import durable, require


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeBackend:
    def __init__(self, output, swconst, sldworks):
        self.output, self.swconst, self.sldworks = Path(output), Path(swconst), Path(sldworks)
        self.app = self.document = self.process = self.feature = None
        self.initialized = self.owned = self.close_attempted = False
        self.call = None

    def start(self):
        require(sys.platform == "win32", "direction singleton requires native Windows")
        import ctypes
        require(getattr(ctypes.WinDLL("ntdll"), "wine_get_version", None) is None, "Wine is outside direction calibration")
        import pythoncom
        import win32com.client as client
        from swcli.daemon.server import acquire_resident_app
        from swcli.host_processes import solidworks_process_ids
        from swcli.hosts.windows import _com_value, wait_windows_host_ready
        from swcli.hosts.windows_revolves import _native_constants
        self.pythoncom = pythoncom
        self.inventory = solidworks_process_ids
        self.value = _com_value
        prior = solidworks_process_ids()
        require(prior == [], "existing native host; never attach, replace or terminate it")
        pythoncom.CoInitialize()
        self.initialized = True
        original = load_script("_revolve_full_turn_typelib_reader", Path(__file__).parents[1]/"verify-revolve-calibration.py")
        typelib = original.read_type_libraries(pythoncom, self.swconst, self.sldworks)
        self.launched = time.time()
        self.app, self.owned = acquire_resident_app(client, visible=False)
        require(self.owned, "direction singleton must own exactly one fresh host")
        pid = _com_value(self.app,"GetProcessID")
        require(type(pid) is int and pid > 0 and pid not in prior, "owned native PID is unavailable")
        self.owned_native = load_script("_revolve_owned_native", Path(__file__).with_name("unit_owned_native.py"))
        self.process, identity = self.owned_native.capture(pid, self.launched,
            observe=lambda observation: durable(self.output/"host-identity-observation.json",observation))
        durable(self.output/"owned-host.json", dict(identity=identity,launch_timestamp=self.launched))
        require(solidworks_process_ids() == [pid], "fresh host PID inventory is not exclusive")
        wait_windows_host_ready(self.app, timeout_seconds=120)
        require(not tuple(_com_value(self.app,"GetDocuments") or ()), "fresh host catalog is not empty")
        self.constants = _native_constants(self.app)
        require(self.constants is not None and self.constants == typelib["constants"], "exact native revision/constants differ")
        return dict(revision=_com_value(self.app,"RevisionNumber"),process_id=pid,owned=True,
                    prior_pids=prior,identity=identity,typelib=typelib)

    def fixture(self, case):
        from swcli.hosts.windows_parts import create_part_windows_with_handle
        from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle
        made,self.document = create_part_windows_with_handle(app=self.app)
        self.close_attempted = False
        require(made["ok"] is True and self.document is not None, "independent empty part creation failed: "+str(made))
        x0,y0,x1,y1=case["bounds_mm"]
        sketch_made,self.sketch = create_rectangle_sketch_windows_with_handle(app=self.app,document=self.document,
            plane=case["plane"],width_mm=x1-x0,height_mm=y1-y0,center_x_mm=(x0+x1)/2,center_y_mm=(y0+y1)/2)
        require(sketch_made["ok"] is True and self.sketch is not None, "center rectangle creation failed: "+str(sketch_made))
        configuration = self.value(self.value(self.document,"ConfigurationManager"),"ActiveConfiguration")
        name = self.value(configuration,"Name")
        require(isinstance(name,str) and bool(name), "fixture configuration is unavailable")
        return dict(part=made,sketch=sketch_made,configuration=name)

    def create(self, case):
        from swcli.hosts.native_trace import trace_native_request
        from swcli.hosts.windows_revolves import _calibrate_revolve_windows_with_handle
        with trace_native_request("revolve-direction-singleton", "feature.revolve.internal-direction"):
            result,self.feature = _calibrate_revolve_windows_with_handle(app=self.app,document=self.document,
                sketch_feature=self.sketch,expected_profile_mm=case["bounds_mm"],axis_mm=case["axis_mm"],
                angle_deg=case["angle_deg"],constants=self.constants,
                rotation_sign=case["rotation_sign"],axis_direction=case["axis_direction"])
        return result,self.feature is not None

    def save(self):
        from swcli.hosts.windows_native_files import save_as_native_windows
        path = self.output/"front-direction-90.SLDPRT"
        require(not path.exists(), "never overwrite native direction evidence")
        result = save_as_native_windows(str(path),document=self.document)
        return dict(path=str(path),save=result,file_size_bytes=path.stat().st_size if path.is_file() else 0,
                    file_sha256=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)

    def close(self):
        self.close_attempted = True
        self.app.CloseDoc(self.value(self.document,"GetTitle"))
        require(not tuple(self.value(self.app,"GetDocuments") or ()), "owned direction document did not close")
        self.document = None

    def reopen(self, saved, creation, case, observed):
        from swcli.hosts.windows_documents import open_windows_document_with_handle, _diagnose_features
        from swcli.hosts.windows_measurements import measure_part_windows
        from swcli.hosts.windows_rectangle_profiles import observe_rectangle_profile, _point_mm
        from swcli.hosts.windows_revolves import observe_revolve_definition
        from swcli.hosts.windows_sketches import _features
        observed["reopen"],self.document = open_windows_document_with_handle(saved["path"],app=self.app,read_only=True)
        self.close_attempted = False
        require(observed["reopen"]["ok"] is True and self.document is not None, "saved direction open failed")
        features = [f for f in _features(self.document) if self.value(f,"GetTypeName2") == "Revolution"]
        observed["feature_count"] = len(features)
        require(len(features)==1, "saved model lacks exactly one native Revolution")
        sub = self.value(features[0],"GetFirstSubFeature")
        sketches=[]
        for _ in range(100):
            if sub is None: break
            if self.value(sub,"GetTypeName2") == "ProfileFeature": sketches.append(sub)
            sub = self.value(sub,"GetNextSubFeature")
        else: raise RuntimeError("saved profile traversal exceeded bound")
        observed["profile_count"] = len(sketches)
        require(len(sketches)==1,"saved Revolution lacks exactly one absorbed sketch")
        sketch = self.value(sketches[0],"GetSpecificFeature2")
        profile = observe_rectangle_profile(sketch)
        observed.update(bounds_mm=list(profile.bounds_mm),
            model_to_sketch_transform=list(self.value(self.value(sketch,"ModelToSketchTransform"),"ArrayData")),
            axis_points_mm=[_point_mm(self.value(profile.left_edge,name)) for name in ("GetStartPoint2","GetEndPoint2")],
            construction_segment_count=profile.construction_segment_count,native_segment_count=profile.native_segment_count)
        require(observed["construction_segment_count"]==2 and observed["native_segment_count"]==6,
                "saved center rectangle construction count differs")
        observed["definition"] = {}
        observe_revolve_definition(self.app,self.document,features[0],profile.left_edge,self.constants,
            observed["definition"],angle_deg=case["angle_deg"],expected_axis_points_mm=creation["candidate"]["axis_points_mm"])
        observed["body_count"] = len(tuple(self.document.GetBodies2(-1,False) or ()))
        observed["measurement"] = measure_part_windows(document=self.document)
        observed["diagnostics"] = _diagnose_features(self.document,500)
        configuration = self.value(self.value(self.document,"ConfigurationManager"),"ActiveConfiguration")
        observed["state"] = dict(read_only=self.value(self.document,"IsOpenedReadOnly"),
            modified=self.value(self.document,"GetSaveFlag"),editing=self.value(self.value(self.document,"SketchManager"),"ActiveSketch") is not None,
            selected=self.value(self.document,"SelectionManager").GetSelectedObjectCount2(-1),
            foreground_same=self.app.IsSame(self.value(self.app,"ActiveDoc"),self.document),
            configurations=list(self.value(self.document,"GetConfigurationNames")),active_configuration=self.value(configuration,"Name"))
        observed["file_sha256"] = hashlib.sha256(Path(saved["path"]).read_bytes()).hexdigest()

    def cleanup(self):
        errors=[]
        def clean(name, function):
            try: self.call(name,function,required=False)
            except BaseException as error: errors.append(dict(stage=name,error=str(error)))
        if self.document is not None and not self.close_attempted: clean("close-owned-document",self.close)
        if self.owned: clean("ExitApp",lambda:self.value(self.app,"ExitApp"))
        if self.process is not None:
            import win32event
            clean("wait-owned-exit",lambda:require(win32event.WaitForSingleObject(self.process,10000)==win32event.WAIT_OBJECT_0,
                                                   "owned direction host exit was not observed"))
            clean("close-owned-handle",self.process.Close)
        if self.initialized: clean("CoUninitialize",self.pythoncom.CoUninitialize)
        if self.owned: clean("verify-final-pid-inventory",lambda:require(self.inventory()==[],"owned native PID remains after cleanup"))
        return errors
