// One existing Python-owned host, three one-use OBJREF parcels, zero or one typed save.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using Microsoft.Win32.SafeHandles;
using SolidWorks.Interop.sldworks;

namespace TypedGlb {
 public static class Program {
  const string PiaSha = "a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1";
  const string PiaName = "SolidWorks.Interop.sldworks, Version=33.5.0.53, Culture=neutral, PublicKeyToken=7c4797c3e4eeac03";
  const string ExeSha = "911309f7494e806f22914bab40aa65531c01b45888ec482ac555fbd8b4f0a18b";
  static readonly Guid DispatchId = new Guid("00020400-0000-0000-C000-000000000046");
  static readonly List<object> Owned = new List<object>();
  [StructLayout(LayoutKind.Sequential)] struct SecurityAttributes { public int length; public IntPtr descriptor; public int inherit; }
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern SafePipeHandle CreateNamedPipe(string name, uint openMode, uint mode, uint instances, uint output, uint input, uint timeout, ref SecurityAttributes security);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool ConnectNamedPipe(SafePipeHandle pipe, IntPtr overlapped);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint pid);
  [DllImport("ole32.dll")] static extern int CoInitializeEx(IntPtr reserved, uint mode);
  [DllImport("ole32.dll")] static extern void CoUninitialize();
  [DllImport("ole32.dll")] static extern int CreateStreamOnHGlobal(IntPtr global, bool deleteOnRelease, out IStream stream);
  [DllImport("ole32.dll")] static extern int CoUnmarshalInterface(IStream stream, ref Guid iid, out IntPtr value);
  [StructLayout(LayoutKind.Sequential)] struct FileIdInfo { public ulong volume; public ulong idLow; public ulong idHigh; }
  [StructLayout(LayoutKind.Sequential)] struct FileBasicInfo { public long creation; public long access; public long write; public long change; public uint attributes; }
  [StructLayout(LayoutKind.Sequential)] struct FileStandardInfo { public long allocation; public long size; public uint links; [MarshalAs(UnmanagedType.U1)] public bool deleted; [MarshalAs(UnmanagedType.U1)] public bool directory; }
  [DllImport("kernel32.dll",EntryPoint="GetFileInformationByHandleEx",SetLastError=true)] static extern bool ReadFileId(SafeFileHandle file,int kind,out FileIdInfo info,uint size);
  [DllImport("kernel32.dll",EntryPoint="GetFileInformationByHandleEx",SetLastError=true)] static extern bool ReadFileBasic(SafeFileHandle file,int kind,out FileBasicInfo info,uint size);
  [DllImport("kernel32.dll",EntryPoint="GetFileInformationByHandleEx",SetLastError=true)] static extern bool ReadFileStandard(SafeFileHandle file,int kind,out FileStandardInfo info,uint size);
  static SourceFileState SourceState(FileStream stream) {
   FileIdInfo id; FileBasicInfo basic; FileStandardInfo standard;
   if(!ReadFileId(stream.SafeFileHandle,18,out id,(uint)Marshal.SizeOf(typeof(FileIdInfo))) ||
      !ReadFileBasic(stream.SafeFileHandle,0,out basic,(uint)Marshal.SizeOf(typeof(FileBasicInfo))) ||
      !ReadFileStandard(stream.SafeFileHandle,1,out standard,(uint)Marshal.SizeOf(typeof(FileStandardInfo))))
    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
   return new SourceFileState {volume_serial=id.volume.ToString("x16"),file_id_128=id.idHigh.ToString("x16")+id.idLow.ToString("x16"),
    size_bytes=standard.size,creation_filetime=basic.creation,write_filetime=basic.write,change_filetime=basic.change,
    attributes=basic.attributes,links=standard.links,delete_pending=standard.deleted,directory=standard.directory};
  }
  static string HashSource(string path, Receipt receipt, string phase) {
   SourceRead evidence=new SourceRead {path=path,phase=phase};
   receipt.source_reads=receipt.source_reads.Concat(new SourceRead[] {evidence}).ToArray();
   try {
    using(FileStream stream=Core.OpenSourceReadOnly(path)) {
     return Core.StableSourceHash(stream,delegate {return SourceState(stream);},delegate {
      using(FileStream current=Core.OpenSourceReadOnly(path)) return SourceState(current);
     },evidence);
    }
   } catch(Exception ex) { evidence.error=ex.GetType().FullName+": "+ex.Message; evidence.hresult=Marshal.GetHRForException(ex);
    System.ComponentModel.Win32Exception win32=ex as System.ComponentModel.Win32Exception; if(win32!=null) evidence.win32_error=win32.NativeErrorCode; throw; }
  }
  static object Hold(object value) { if (value != null && Marshal.IsComObject(value)) Owned.Add(value); return value; }
  public static string Hash(string path) { using (FileStream s = File.OpenRead(path)) using (SHA256 sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(s)).Replace("-", "").ToLowerInvariant(); }
  static void CheckContract(Receipt r) {
   Assembly a = typeof(IModelDocExtension).Assembly;
   r.pia_path = a.Location; r.pia_sha256 = Hash(a.Location);
   Core.Require(IntPtr.Size == 8 && a.FullName == PiaName && r.pia_sha256 == PiaSha, "installed x64 PIA identity differs");
   Type type = typeof(IModelDocExtension);
   Core.Require(type.IsImport && type.GUID == new Guid("99F4D4AF-F268-4EE1-8C55-041F7BECF879"), "PIA interface identity differs");
   MethodInfo m = type.GetMethod("SaveAs3");
   Core.Require(m != null && m.ReturnType == typeof(bool) && (int)m.GetMethodImplementationFlags() == 4099,
                "SaveAs3 return/implementation metadata differs");
   DispIdAttribute id = (DispIdAttribute)System.Attribute.GetCustomAttribute(m, typeof(DispIdAttribute));
   Core.Require(id != null && id.Value == 315 && m.ReturnParameter.GetCustomAttributes(typeof(MarshalAsAttribute), false).Length == 0,
                "SaveAs3 DISPID/return marshaling differs");
   ParameterInfo[] ps = m.GetParameters();
   Type[] types = { typeof(string), typeof(int), typeof(int), typeof(object), typeof(object), typeof(int).MakeByRefType(), typeof(int).MakeByRefType() };
   Core.Require(ps.Length == 7, "SaveAs3 parameter count differs");
   for (int i=0; i<7; ++i) {
    Core.Require(ps[i].ParameterType == types[i] && ps[i].IsIn && ps[i].IsOut == (i>=5) && !ps[i].IsOptional,
                 "SaveAs3 parameter flags/type differ at " + i);
    MarshalAsAttribute ma = (MarshalAsAttribute)System.Attribute.GetCustomAttribute(ps[i], typeof(MarshalAsAttribute));
    if (i==0 || i==3 || i==4) Core.Require(ma != null && ma.Value == (i==0 ? UnmanagedType.BStr : UnmanagedType.IDispatch), "SaveAs3 parameter marshaling differs");
    else Core.Require(ma == null, "unexpected SaveAs3 parameter marshaling");
   }
   r.contract_accepted = true;
  }
  static NamedPipeServerStream Server(string name, int parent) {
   PipeSecurity acl = new PipeSecurity();
   acl.SetAccessRuleProtection(true, false);
   SecurityIdentifier sid = WindowsIdentity.GetCurrent().User;
   Core.Require(sid != null, "current user SID unavailable");
   acl.SetOwner(sid); acl.AddAccessRule(new PipeAccessRule(sid, PipeAccessRights.FullControl, AccessControlType.Allow));
   byte[] descriptor = acl.GetSecurityDescriptorBinaryForm();
   GCHandle pin = GCHandle.Alloc(descriptor, GCHandleType.Pinned);
   try {
    SecurityAttributes sa = new SecurityAttributes(); sa.length=Marshal.SizeOf(typeof(SecurityAttributes)); sa.descriptor=pin.AddrOfPinnedObject(); sa.inherit=0;
    // Duplex + FIRST_PIPE_INSTANCE; byte/wait mode + REJECT_REMOTE_CLIENTS; one instance.
    SafePipeHandle handle = CreateNamedPipe(@"\\.\pipe\"+name, 0x00080003, 0x00000008, 1, 65536, 65536, 0, ref sa);
    if (handle.IsInvalid) { int e=Marshal.GetLastWin32Error(); handle.Dispose(); throw new System.ComponentModel.Win32Exception(e); }
    try {
     if (!ConnectNamedPipe(handle,IntPtr.Zero) && Marshal.GetLastWin32Error()!=535) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
     uint client; Core.Require(GetNamedPipeClientProcessId(handle,out client) && client==(uint)parent, "pipe client PID differs");
     return new NamedPipeServerStream(PipeDirection.InOut, false, true, handle);
    }
    catch { handle.Dispose(); throw; }
   } finally { pin.Free(); }
  }
  static object Unmarshal(byte[] data) {
   IStream stream; Marshal.ThrowExceptionForHR(CreateStreamOnHGlobal(IntPtr.Zero, true, out stream));
   IntPtr ptr = IntPtr.Zero;
   try {
    stream.Write(data, data.Length, IntPtr.Zero); stream.Seek(0, 0, IntPtr.Zero);
    Guid iid=DispatchId;
    // A failed unmarshal remains uncertain to the sender; never retry this parcel.
    Marshal.ThrowExceptionForHR(CoUnmarshalInterface(stream, ref iid, out ptr));
    return Hold(Marshal.GetObjectForIUnknown(ptr));
   } finally {
    if (ptr != IntPtr.Zero) Marshal.Release(ptr);
    Marshal.ReleaseComObject(stream);
   }
  }
  static bool SameUnknown(object a, object b) {
   Core.Require(a != null && b != null, "missing COM identity");
   IntPtr pa = Marshal.GetIUnknownForObject(a), pb = IntPtr.Zero;
   try { pb = Marshal.GetIUnknownForObject(b); return pa==pb; }
   finally { if (pb!=IntPtr.Zero) Marshal.Release(pb); Marshal.Release(pa); }
  }
  static Snapshot Observe(ISldWorks app, IModelDoc2 doc, IModelDocExtension extension, Receipt receipt, string phase) {
   Observation observation=new Observation {phase=phase};
   receipt.observations=receipt.observations.Concat(new Observation[] {observation}).ToArray();
   observation.current_field="canonical identity";
   object active=Hold(app.ActiveDoc), actualExtension=Hold(doc.Extension);
   IdentityCheck check=new IdentityCheck { phase=phase };
   receipt.identity_checks=receipt.identity_checks.Concat(new IdentityCheck[] {check}).ToArray();
   check.document_iunknown_same=SameUnknown(doc,active); check.extension_iunknown_same=SameUnknown(extension,actualExtension);
   Core.Require(check.document_iunknown_same==true && check.extension_iunknown_same==true, "canonical IUnknown identity differs");
   int same=observation.Read("foreground_same",delegate {return app.IsSame(doc,active);}); check.foreground_same=same; Core.Require(same==1, "foreground swObjectSame unavailable");
   Snapshot s=new Snapshot(); s.pid=observation.Read("pid",delegate {return app.GetProcessID();});
   using(Process sw=Process.GetProcessById(s.pid)) {
    s.created_filetime=observation.Read("created_filetime",delegate {return sw.StartTime.ToUniversalTime().ToFileTimeUtc();});
    s.exe_path=observation.Read("exe_path",delegate {return sw.MainModule.FileName;});
    s.exe_sha256=observation.Read("exe_sha256",delegate {return Hash(s.exe_path);});
   }
   Core.Require(s.exe_sha256==ExeSha, "SOLIDWORKS executable differs from inspected installation");
   s.runtime=observation.Read("runtime",delegate {return app.RevisionNumber();});
   s.document_count=observation.Read("document_count",delegate {return app.GetDocumentCount();});
   s.visible=observation.Read("visible",delegate {return app.Visible;});
   s.command_in_progress=observation.Read("command_in_progress",delegate {return app.CommandInProgress;});
   s.user_control=observation.Read("user_control",delegate {return app.UserControl;});
   s.background=observation.Read("background",delegate {return app.UserControlBackground;});
   s.path=observation.Read("path",delegate {return doc.GetPathName();});
   s.title=observation.Read("title",delegate {return doc.GetTitle();});
   s.document_type=observation.Read("document_type",delegate {return doc.GetType();});
   s.update_stamp=observation.Read("update_stamp",delegate {return doc.GetUpdateStamp();});
   s.modified=observation.Read("modified",delegate {return doc.GetSaveFlag();});
   observation.current_field="ConfigurationManager.ActiveConfiguration";
   IConfigurationManager manager=(IConfigurationManager)Hold(doc.ConfigurationManager);
   IConfiguration config=(IConfiguration)Hold(manager.ActiveConfiguration);
   s.configuration=observation.Read("configuration",delegate {return config.Name;});
   s.configurations=observation.Read("configurations",delegate {
    Array names=doc.GetConfigurationNames() as Array; Core.Require(names!=null && names.Length>0 && names.Length<=1000,"configuration names unreadable");
    List<string> all=new List<string>(); foreach(object n in names) { Core.Require(n is string && !String.IsNullOrEmpty((string)n),"configuration name is not a string"); all.Add((string)n); }
    Core.Require(all.Distinct().Count()==all.Count,"configuration names duplicate"); return all.ToArray();
   });
   s.read_only=observation.Read("read_only",delegate {return doc.IsOpenedReadOnly();});
   s.view_only=observation.Read("view_only",delegate {return doc.IsOpenedViewOnly();});
   observation.current_field="SketchManager"; ISketchManager sketches=(ISketchManager)Hold(doc.SketchManager);
   s.active_sketch=observation.Read("active_sketch",delegate {return Hold(sketches.ActiveSketch)!=null;});
   s.foreground_same=same;
   s.source_sha256=observation.Read("source_sha256",delegate {return HashSource(s.path,receipt,phase);});
   observation.complete=true; return s;
  }
  static void WriteNew(string path, byte[] data) { using (FileStream s=new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) { s.Write(data,0,data.Length); s.Flush(true); } }
  [STAThread] public static int Main(string[] args) {
   // --pipe NAME --nonce HEX --parent PID --receipt PATH --trace PATH
   if (args.Length!=10 || args[0]!="--pipe" || args[2]!="--nonce" || args[4]!="--parent" || args[6]!="--receipt" || args[8]!="--trace") return 64;
   string name=args[1], nonce=args[3], receiptPath=Path.GetFullPath(args[7]), tracePath=Path.GetFullPath(args[9]);
   int parent; if (!Int32.TryParse(args[5],out parent) || parent<=0 || !System.Text.RegularExpressions.Regex.IsMatch(name,@"^swcli-glb-[0-9a-f]{32}$") ||
                  !System.Text.RegularExpressions.Regex.IsMatch(nonce,@"^[0-9a-f]{64}$") || File.Exists(receiptPath) || File.Exists(tracePath)) return 64;
   Receipt r=new Receipt(); r.helper_pid=Process.GetCurrentProcess().Id; r.python_worker_pid=parent;
   bool initialized=false; StreamWriter trace=null; NamedPipeServerStream pipe=null;
   List<string> cleanup=new List<string>(); List<string> consumed=new List<string>();
   using (ManualResetEvent finished=new ManualResetEvent(false)) {
    Thread guard=new Thread(delegate() {
     Stopwatch elapsed=Stopwatch.StartNew();
     while (!finished.WaitOne(250)) {
      bool alive; try { using(Process p=Process.GetProcessById(parent)) alive=!p.HasExited; } catch { alive=false; }
      if (!alive || elapsed.Elapsed.TotalSeconds>=600) System.Environment.Exit(124);
     }
    }); guard.IsBackground=true; guard.Start();
    try {
     trace=new StreamWriter(new FileStream(tracePath,FileMode.CreateNew,FileAccess.Write,FileShare.Read),new UTF8Encoding(false)); trace.AutoFlush=true;
     int hr=CoInitializeEx(IntPtr.Zero,2); Marshal.ThrowExceptionForHR(hr); initialized=true;
     CheckContract(r); pipe=Server(name,parent);
     Message hello=Core.Receive(pipe,nonce,"hello",null);
     Core.Require(hello.mode=="identity" || hello.mode=="invoke", "unknown operation mode"); r.identity_only=hello.mode=="identity";
     r.output=hello.output; Core.Fixture(hello.expected,hello.output);
     Core.Send(pipe,new Message { kind="ready",nonce=nonce });
     List<object> interfaces=new List<object>();
     foreach (string role in new string[] {"app","document","extension"}) {
      Message parcel=Core.Receive(pipe,nonce,"parcel",role); byte[] data=Core.Parcel(parcel);
      Core.Send(pipe,new Message {kind="prepared",nonce=nonce,role=role});
      Core.Receive(pipe,nonce,"consume",role);
      interfaces.Add(Unmarshal(data)); consumed.Add(role); r.consumed_roles=consumed.ToArray(); Array.Clear(data,0,data.Length);
      Core.Send(pipe,new Message {kind="consumed",nonce=nonce,role=role});
     }
     ISldWorks app=(ISldWorks)interfaces[0]; IModelDoc2 doc=(IModelDoc2)interfaces[1]; IModelDocExtension extension=(IModelDocExtension)interfaces[2];
     r.before=Observe(app,doc,extension,r,"handshake"); Core.Fixture(r.before,r.output); Core.SameSnapshot(hello.expected,r.before); r.identity_accepted=true;
     Core.Send(pipe,new Message {kind="identity",nonce=nonce,receipt=r});
     Core.Receive(pipe,nonce,r.identity_only?"finish":"invoke",null);
     if (!r.identity_only) {
      Core.SameSnapshot(r.before,Observe(app,doc,extension,r,"before-save"));
      trace.WriteLine("{\"event\":\"typed-glb.native-call\",\"phase\":\"begin\",\"helper_pid\":"+r.helper_pid+",\"call\":\"IModelDocExtension.SaveAs3\",\"utc\":\""+DateTime.UtcNow.ToString("o")+"\"}");
      try { Core.SaveOnce(extension,r.output,r); }
      finally { trace.WriteLine("{\"event\":\"typed-glb.native-call\",\"phase\":\""+(r.first_error==null?"end":"error")+"\",\"helper_pid\":"+r.helper_pid+",\"utc\":\""+DateTime.UtcNow.ToString("o")+"\"}"); }
      // No CAD reads after false, native error, exception, or unwritten outputs.
      r.after=Observe(app,doc,extension,r,"after-normal-return"); Core.SameSnapshot(r.before,r.after); r.post_state_accepted=true;
     }
     r.success=true;
    } catch(Exception ex) {
     if (r.first_error==null) { r.first_error=ex.GetType().FullName+": "+ex.Message; r.hresult=Marshal.GetHRForException(ex); r.hresult_kind=ex is COMException?"COMException":"managed-exception"; }
    } finally {
     for(int i=Owned.Count-1;i>=0;--i) { try { Marshal.ReleaseComObject(Owned[i]); } catch(Exception ex) { cleanup.Add(ex.GetType().FullName+": "+ex.Message); } } Owned.Clear();
     if(initialized) CoUninitialize(); r.cleanup_errors=cleanup.ToArray(); if(cleanup.Count>0) r.success=false;
     // The final result is sent only after helper-owned reference cleanup.
     if(pipe!=null && pipe.IsConnected) { try { Core.Send(pipe,new Message {kind="result",nonce=nonce,receipt=r}); } catch(Exception ex) { if(r.first_error==null) r.first_error="result delivery: "+ex.Message; r.success=false; } }
     try { if(pipe!=null) pipe.Dispose(); } catch(Exception ex) { cleanup.Add("pipe dispose: "+ex.Message); r.success=false; }
     try { if(trace!=null) trace.Dispose(); } catch(Exception ex) { cleanup.Add("trace dispose: "+ex.Message); r.success=false; }
     r.cleanup_errors=cleanup.ToArray();
     try { WriteNew(receiptPath,Core.Encode(r)); } catch { r.success=false; }
     finished.Set(); guard.Join(1000);
    }
   }
   return r.success?0:1;
  }
 }
}
