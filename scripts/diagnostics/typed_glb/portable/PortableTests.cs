// Pure protocol/gate tests plus full candidate syntax compilation against test-only stubs.
using System;
using System.IO;
using System.Runtime.InteropServices;
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
 static Receipt Ready() { return new Receipt {identity_accepted=true,contract_accepted=true}; }
 public static int Main() {
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
  Check(typeof(IModelDocExtension).GetMethod("SaveAs3").GetParameters()[5].IsIn && typeof(IModelDocExtension).GetMethod("SaveAs3").GetParameters()[5].IsOut);
  Console.WriteLine("portable assertions="+assertions+"; COM/Windows/installed PIA not executed"); return 0;
 }
}
