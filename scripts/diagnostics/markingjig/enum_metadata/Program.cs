// Offline PIA metadata only; no COM creation, target method or static-field invocation.
using System;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
public static class Program {
 public static int Main(string[] args) {
  try {
   if(args.Length!=2) throw new InvalidOperationException("PIA path and approved SHA256 required");
   byte[] bytes=File.ReadAllBytes(args[0]);string sha;
   using(SHA256 h=SHA256.Create()) sha=BitConverter.ToString(h.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
   if(sha!=args[1] || Path.GetFileName(args[0])!="SolidWorks.Interop.swconst.dll") throw new InvalidOperationException("pinned swconst PIA identity differs");
   AssemblyName name=AssemblyName.GetAssemblyName(args[0]);
   if(name.Name!="SolidWorks.Interop.swconst") throw new InvalidOperationException("not a swconst PIA");
   Assembly assembly=Assembly.LoadFrom(Path.GetFullPath(args[0]));
   Type type=assembly.GetType("SolidWorks.Interop.swconst.swFileLoadWarning_e",true);
   FieldInfo field=type.GetField("swFileLoadWarning_ReadOnly",BindingFlags.Public|BindingFlags.Static);
   if(!type.IsEnum || field==null || !field.IsLiteral || Enum.GetUnderlyingType(type)!=typeof(int)) throw new InvalidOperationException("warning enum metadata shape differs");
   object value=field.GetRawConstantValue();
   Console.WriteLine(JsonSerializer.Serialize(new {pia_sha256=sha,assembly_full_name=assembly.FullName,enum_name=type.FullName,member=field.Name,raw_value=value,raw_type=value.GetType().FullName,target_methods_invoked=0,COM_created=0}));
   return value is int && (int)value==2 ? 0 : 1;
  } catch(Exception e) {Console.Error.WriteLine(e.GetType().FullName+": "+e.Message);return 1;}
 }
}
