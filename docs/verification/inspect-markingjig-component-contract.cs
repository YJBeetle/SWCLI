// Offline installed PIA metadata only. No COM or target method invocation.
using System;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Collections.Generic;
public static class Program {
 static string Hash(string path) {using(SHA256 h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();}
 static Assembly Pinned(string path,string sha,string basename) {
  if(Path.GetFileName(path)!=basename || Hash(path)!=sha)throw new InvalidOperationException("PIA identity differs");
  return Assembly.LoadFrom(Path.GetFullPath(path));
 }
 static object Parameter(ParameterInfo p) {
  List<object> attrs=new List<object>();
  foreach(CustomAttributeData a in CustomAttributeData.GetCustomAttributes(p)) {
   List<object> values=new List<object>();foreach(CustomAttributeTypedArgument v in a.ConstructorArguments)values.Add(new {type=v.ArgumentType.FullName,value=v.Value==null?null:v.Value.ToString()});
   List<object> named=new List<object>();foreach(CustomAttributeNamedArgument n in a.NamedArguments)named.Add(new {name=n.MemberName,type=n.TypedValue.ArgumentType.FullName,value=n.TypedValue.Value==null?null:n.TypedValue.Value.ToString()});
   attrs.Add(new {type=a.AttributeType.FullName,arguments=values,named_arguments=named});
  }
  return new {name=p.Name,type=p.ParameterType.FullName,is_out=p.IsOut,is_in=p.IsIn,position=p.Position,attributes=attrs};
 }
 public static int Main(string[] args) {
  try {
   if(args.Length!=4)throw new InvalidOperationException("two PIA paths and hashes required");
   Assembly sw=Pinned(args[0],args[1],"SolidWorks.Interop.sldworks.dll");
   Assembly constants=Pinned(args[2],args[3],"SolidWorks.Interop.swconst.dll");
   List<object> methods=new List<object>();
   string[][] targets=new string[][] {new string[]{"IComponent2","GetBodies3","GetModelDoc2","get_ReferencedConfiguration"},new string[]{"IBody2","GetType","GetBodyBox","GetMassProperties","GetFaceCount","GetEdgeCount"}};
   foreach(string[] target in targets) {
    Type t=sw.GetType("SolidWorks.Interop.sldworks."+target[0],true);
    for(int i=1;i<target.Length;i++) {
     MethodInfo m=t.GetMethod(target[i]);if(m==null)throw new InvalidOperationException("missing "+target[i]);
     List<object> parameters=new List<object>();foreach(ParameterInfo p in m.GetParameters())parameters.Add(Parameter(p));
     List<object> attrs=new List<object>();foreach(CustomAttributeData a in CustomAttributeData.GetCustomAttributes(m))
      if(a.AttributeType.FullName=="System.Runtime.InteropServices.DispIdAttribute")attrs.Add(new {type=a.AttributeType.FullName,value=a.ConstructorArguments[0].Value});
     methods.Add(new {owner=t.FullName,name=m.Name,returns=Parameter(m.ReturnParameter),parameters=parameters,attributes=attrs});
    }
   }
   List<object> enums=new List<object>();
   foreach(string name in new string[]{"swBodyInfo_e","swBodyType_e"}) {
    Type t=constants.GetType("SolidWorks.Interop.swconst."+name,true);List<object> fields=new List<object>();
    foreach(FieldInfo f in t.GetFields(BindingFlags.Public|BindingFlags.Static)) {
     if(!f.IsLiteral)throw new InvalidOperationException("not literal");
     fields.Add(new {name=f.Name,value=f.GetRawConstantValue()});
    }
    enums.Add(new {name=t.FullName,underlying_type=Enum.GetUnderlyingType(t).FullName,fields=fields});
   }
   Console.WriteLine(JsonSerializer.Serialize(new {schema="swcli.markingjig-component-PIA-metadata.v1",sldworks_pia_sha256=args[1],swconst_pia_sha256=args[3],sldworks_assembly=sw.FullName,swconst_assembly=constants.FullName,methods=methods,enums=enums,COM_created=0,target_methods_invoked=0}));
   return 0;
  }catch(Exception e){Console.Error.WriteLine(e.ToString());return 1;}
 }
}
