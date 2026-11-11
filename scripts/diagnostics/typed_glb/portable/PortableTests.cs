// Pure protocol/gate tests plus full candidate syntax compilation against test-only stubs.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Linq;
using SolidWorks.Interop.sldworks;
using TypedGlb;
sealed class FakeExtension : IModelDocExtension {
 public int Calls, Mode;
 public bool SaveAs3(string name,int version,int options,object data,object advanced,ref int errors,ref int warnings) {
  ++Calls;
  if(name!="unchanged.GLB" || version!=0 || options!=1 || data!=null || advanced!=null || errors!=Int32.MinValue || warnings!=Int32.MinValue)
   throw new Exception("native arguments/initial outputs changed");
  if(Mode==3) { errors=7; throw new COMException("first native error",unchecked((int)0x80004005)); }
  errors=0; if(Mode!=4) warnings=2;
  if(Mode==2) errors=32;
  return Mode!=1;
 }
}
static class PortableTests {
 static int assertions;
 static void Check(bool ok) { ++assertions; if(!ok) throw new Exception("assertion "+assertions); }
 static void Fails(Action fn) { bool failed=false; try {fn();} catch {failed=true;} Check(failed); }
 static SourceFileState State() { return new SourceFileState {volume_serial="0000000000000001",file_id_128="00000000000000000000000000000002",size_bytes=3,creation_filetime=100,write_filetime=200,change_filetime=300,links=1}; }
 static SourceFileState Copy(SourceFileState s) { return Core.Decode<SourceFileState>(Core.Encode(s)); }
 static void SourceTests() {
  Check(Marshal.SizeOf(typeof(Program).GetNestedType("FileIdInfo",System.Reflection.BindingFlags.NonPublic))==24);
  Check(Marshal.SizeOf(typeof(Program).GetNestedType("FileBasicInfo",System.Reflection.BindingFlags.NonPublic))==40);
  Check(Marshal.SizeOf(typeof(Program).GetNestedType("FileStandardInfo",System.Reflection.BindingFlags.NonPublic))==24);
  byte[] bytes={1,2,3}; SourceFileState state=State(); SourceRead evidence=new SourceRead();
  using(MemoryStream stream=new MemoryStream(bytes,false)) {
   string hash=Core.StableSourceHash(stream,delegate {return Copy(state);},delegate {return Copy(state);},evidence);
   Check(hash=="039058c6f2c0cb492c533b0a4d14ef77cc0f78abccced5287d84a1a2011cfb81" && evidence.complete && evidence.bytes_read==3);
  }
  foreach(string changed in new string[]{"id","volume","write","change","creation","size","attributes","links"}) {
   SourceFileState after=Copy(state);
   if(changed=="id") after.file_id_128=new string('f',32);
   if(changed=="volume") after.volume_serial=new string('e',16);
   if(changed=="write") ++after.write_filetime;
   if(changed=="change") ++after.change_filetime;
   if(changed=="creation") ++after.creation_filetime;
   if(changed=="size") ++after.size_bytes;
   if(changed=="attributes") after.attributes=1;
   if(changed=="links") ++after.links;
   int reads=0; SourceRead rejected=new SourceRead();
   using(MemoryStream stream=new MemoryStream(bytes,false)) Fails(delegate {Core.StableSourceHash(stream,delegate {return ++reads==1?Copy(state):after;},delegate {throw new Exception("path must not be read after held mismatch");},rejected);});
   Check(!rejected.complete && rejected.before!=null && rejected.after!=null && rejected.sha256!=null);
  }
  SourceFileState replaced=Copy(state);replaced.file_id_128=new string('b',32);evidence=new SourceRead();
  using(MemoryStream stream=new MemoryStream(bytes,false)) Fails(delegate {Core.StableSourceHash(stream,delegate {return Copy(state);},delegate {return replaced;},evidence);});
  Check(!evidence.complete && evidence.path_after.file_id_128==replaced.file_id_128);
  foreach(long size in new long[]{2,4}) {
   SourceFileState wrong=Copy(state);wrong.size_bytes=size;SourceRead rejected=new SourceRead();
   using(MemoryStream stream=new MemoryStream(bytes,false)) Fails(delegate {Core.StableSourceHash(stream,delegate {return wrong;},delegate {return wrong;},rejected);});
   Check(!rejected.complete && rejected.before!=null);
  }
  SourceFileState unknown=Copy(state);unknown.file_id_128=new string('0',32);
  Fails(delegate {Core.ValidSourceState(unknown);});
  using(MemoryStream stream=new MemoryStream(bytes)) Fails(delegate {Core.StableSourceHash(stream,delegate {return state;},delegate {return state;},new SourceRead());});
  string path=Path.GetTempFileName();
  try {
   File.WriteAllBytes(path,bytes);
   using(FileStream held=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.ReadWrite))
   using(FileStream read=Core.OpenSourceReadOnly(path)) { Check(read.CanRead && !read.CanWrite); Fails(delegate {read.WriteByte(9);}); }
   Check(File.ReadAllBytes(path).SequenceEqual(bytes));
  } finally {File.Delete(path);}
  Receipt receipt=new Receipt();Observation observation=new Observation {phase="handshake"};receipt.observations=new Observation[]{observation};
  observation.Read("exe_path",delegate {return @"C:\raw\SLDWORKS.exe";});observation.Read("pid",delegate {return 42;});
  Fails(delegate {observation.Read<string>("source_sha256",delegate {throw new IOException("first source read error");});});
  Receipt decoded=Core.Decode<Receipt>(Core.Encode(receipt));
  Check(decoded.before==null && !decoded.identity_accepted && !decoded.observations[0].complete && decoded.observations[0].current_field=="source_sha256");
  Check(decoded.observations[0].fields.Count==2 && decoded.observations[0].fields[0].text==@"C:\raw\SLDWORKS.exe");
 }
 static Receipt Ready() { return new Receipt {identity_accepted=true,contract_accepted=true}; }
 public static int Main() {
  SourceTests();
  FakeExtension f=new FakeExtension(); Receipt r=Ready(); Core.SaveOnce(f,"unchanged.GLB",r);
  Check(f.Calls==1 && r.api_saved==true && r.save_errors==0 && r.save_warnings==2 && r.errors_local==0 && r.first_error==null);
  Fails(delegate {Core.SaveOnce(f,"unchanged.GLB",r);}); Check(f.Calls==1);
  for(int mode=1;mode<=4;++mode) {
   f=new FakeExtension {Mode=mode}; r=Ready();
   Fails(delegate {Core.SaveOnce(f,"unchanged.GLB",r);}); Check(f.Calls==1 && r.save_attempts==1 && r.first_error!=null && r.end_utc!=null);
   if(mode==1) Check(r.api_saved==false && r.save_errors==0 && r.save_warnings==2);
   if(mode==2) Check(r.api_saved==true && r.save_errors==32 && r.save_warnings==2);
   if(mode==3) Check(r.api_saved==null && r.save_errors==null && r.save_warnings==null && r.errors_local==7 && r.hresult==unchecked((int)0x80004005));
   if(mode==4) Check(r.api_saved==true && r.save_errors==0 && r.save_warnings==null);
  }
  foreach(Receipt blocked in new Receipt[] { new Receipt(), new Receipt {contract_accepted=true}, new Receipt {identity_accepted=true}, new Receipt {identity_accepted=true,contract_accepted=true,identity_only=true} }) {
   f=new FakeExtension(); Fails(delegate {Core.SaveOnce(f,"unchanged.GLB",blocked);}); Check(f.Calls==0);
  }
  using(MemoryStream s=new MemoryStream()) {
   Core.Send(s,new Message {kind="consumed",nonce="nonce",role="app"}); s.Position=0;
   Check(Core.Receive(s,"nonce","consumed","app").role=="app"); s.Position=0;
   Fails(delegate {Core.Receive(s,"wrong","consumed","app");});
  }
  using(MemoryStream s=new MemoryStream(new byte[]{255,255,255,127})) Fails(delegate {Core.Receive(s,"n","ready",null);});
  using(MemoryStream s=new MemoryStream(new byte[]{5,0,0,0,1})) Fails(delegate {Core.Receive(s,"n","ready",null);});
  Check(Core.Parcel(new Message {data="AQID"}).Length==3);
  Fails(delegate {Core.Parcel(new Message {data=""});});
  Fails(delegate {Core.Parcel(new Message {data=new string('A',1398105)});});
  Snapshot snap=new Snapshot {configurations=new string[]{"A"}};
  Core.SameSnapshot(snap,Core.Decode<Snapshot>(Core.Encode(snap))); Check(true);
  Snapshot other=Core.Decode<Snapshot>(Core.Encode(snap)); other.update_stamp=1;
  Fails(delegate {Core.SameSnapshot(snap,other);});
  using(MemoryStream s=new MemoryStream()) {
   Core.Send(s,new Message {kind="parcel",nonce="n",role="app",data=Convert.ToBase64String(new byte[Core.MaxParcel])}); s.Position=0;
   Check(Core.Parcel(Core.Receive(s,"n","parcel","app")).Length==Core.MaxParcel);
  }
  // Hypothetical aliases only: this does not claim native Windows path evidence.
  Snapshot shortPath=Core.Decode<Snapshot>(Core.Encode(snap)); shortPath.exe_path=@"C:\PROGRA~1\SOLIDW~1\SLDWORKS.exe"; shortPath.exe_sha256=new string('a',64);
  Snapshot longPath=Core.Decode<Snapshot>(Core.Encode(shortPath)); longPath.exe_path=@"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe";
  Fails(delegate {Core.SameSnapshot(shortPath,longPath);});
  Check(shortPath.exe_path!=longPath.exe_path && shortPath.exe_sha256==longPath.exe_sha256);
  Check(typeof(IModelDocExtension).GetMethod("SaveAs3").GetParameters()[5].IsIn && typeof(IModelDocExtension).GetMethod("SaveAs3").GetParameters()[5].IsOut);
  Console.WriteLine("portable assertions="+assertions+"; COM/Windows/installed PIA not executed"); return 0;
 }
}
