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
   DispIdAttribute id = (DispIdAttribute)Attribute.GetCustomAttribute(m, typeof(DispIdAttribute));
   Core.Require(id != null && id.Value == 315 && m.ReturnParameter.GetCustomAttributes(typeof(MarshalAsAttribute), false).Length == 0,
                "SaveAs3 DISPID/return marshaling differs");
   ParameterInfo[] ps = m.GetParameters();
   Type[] types = { typeof(string), typeof(int), typeof(int), typeof(object), typeof(object), typeof(int).MakeByRefType(), typeof(int).MakeByRefType() };
   Core.Require(ps.Length == 7, "SaveAs3 parameter count differs");
   for (int i=0; i<7; ++i) {
    Core.Require(ps[i].ParameterType == types[i] && ps[i].IsIn && ps[i].IsOut == (i>=5) && !ps[i].IsOptional,
                 "SaveAs3 parameter flags/type differ at " + i);
    MarshalAsAttribute ma = (MarshalAsAttribute)Attribute.GetCustomAttribute(ps[i], typeof(MarshalAsAttribute));
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
   object active=Hold(app.ActiveDoc), actualExtension=Hold(doc.Extension);
   IdentityCheck check=new IdentityCheck { phase=phase };
   receipt.identity_checks=receipt.identity_checks.Concat(new IdentityCheck[] {check}).ToArray();
   check.document_iunknown_same=SameUnknown(doc,active); check.extension_iunknown_same=SameUnknown(extension,actualExtension);
   Core.Require(check.document_iunknown_same==true && check.extension_iunknown_same==true, "canonical IUnknown identity differs");
   int same=app.IsSame(doc, active); check.foreground_same=same; Core.Require(same==1, "foreground swObjectSame unavailable");
   int pid=app.GetProcessID(); Process sw=Process.GetProcessById(pid);
   Snapshot s=new Snapshot();
   using (sw) { s.pid=pid; s.created_filetime=sw.StartTime.ToUniversalTime().ToFileTimeUtc(); s.exe_path=sw.MainModule.FileName; s.exe_sha256=Hash(s.exe_path); }
   Core.Require(s.exe_sha256==ExeSha, "SOLIDWORKS executable differs from inspected installation");
   s.runtime=app.RevisionNumber(); s.document_count=app.GetDocumentCount();
   s.visible=app.Visible; s.command_in_progress=app.CommandInProgress; s.user_control=app.UserControl; s.background=app.UserControlBackground;
   s.path=doc.GetPathName(); s.title=doc.GetTitle(); s.document_type=doc.GetType(); s.update_stamp=doc.GetUpdateStamp(); s.modified=doc.GetSaveFlag();
   IConfigurationManager manager=(IConfigurationManager)Hold(doc.ConfigurationManager);
   IConfiguration config=(IConfiguration)Hold(manager.ActiveConfiguration); s.configuration=config.Name;
   Array names=doc.GetConfigurationNames() as Array; Core.Require(names != null && names.Length>0 && names.Length<=1000, "configuration names unreadable");
   List<string> all=new List<string>(); foreach (object n in names) { Core.Require(n is string && !String.IsNullOrEmpty((string)n), "configuration name is not a string"); all.Add((string)n); }
   Core.Require(all.Distinct().Count()==all.Count, "configuration names duplicate"); s.configurations=all.ToArray();
   s.read_only=doc.IsOpenedReadOnly(); s.view_only=doc.IsOpenedViewOnly();
   ISketchManager sketches=(ISketchManager)Hold(doc.SketchManager); s.active_sketch=Hold(sketches.ActiveSketch)!=null;
   s.foreground_same=same; s.source_sha256=Hash(s.path); return s;
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
      if (!alive || elapsed.Elapsed.TotalSeconds>=600) Environment.Exit(124);
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
