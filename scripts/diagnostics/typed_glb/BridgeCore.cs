// C# 5 / .NET Framework 4. Diagnostic transport only; no COM activation.
using System;
using System.IO;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Linq;
using System.Runtime.InteropServices;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Text;
using SolidWorks.Interop.sldworks;

namespace TypedGlb {
 [DataContract] public sealed class Snapshot {
  [DataMember(IsRequired=true)] public int pid;
  [DataMember(IsRequired=true)] public long created_filetime;
  [DataMember(IsRequired=true)] public string exe_path;
  [DataMember(IsRequired=true)] public string exe_sha256;
  [DataMember(IsRequired=true)] public string runtime;
  [DataMember(IsRequired=true)] public int document_count;
  [DataMember(IsRequired=true)] public bool visible;
  [DataMember(IsRequired=true)] public bool command_in_progress;
  [DataMember(IsRequired=true)] public bool user_control;
  [DataMember(IsRequired=true)] public bool background;
  [DataMember(IsRequired=true)] public string path;
  [DataMember(IsRequired=true)] public string title;
  [DataMember(IsRequired=true)] public int document_type;
  [DataMember(IsRequired=true)] public int update_stamp;
  [DataMember(IsRequired=true)] public bool modified;
  [DataMember(IsRequired=true)] public string configuration;
  [DataMember(IsRequired=true)] public string[] configurations;
  [DataMember(IsRequired=true)] public bool read_only;
  [DataMember(IsRequired=true)] public bool view_only;
  [DataMember(IsRequired=true)] public bool active_sketch;
  [DataMember(IsRequired=true)] public int foreground_same;
  [DataMember(IsRequired=true)] public string source_sha256;
 }
 [DataContract] public sealed class Message {
  [DataMember(IsRequired=true)] public string kind;
  [DataMember(IsRequired=true)] public string nonce;
  [DataMember(EmitDefaultValue=false)] public string role;
  [DataMember(EmitDefaultValue=false)] public string data;
  [DataMember(EmitDefaultValue=false)] public string output;
  [DataMember(EmitDefaultValue=false)] public string mode;
  [DataMember(EmitDefaultValue=false)] public Snapshot expected;
  [DataMember(EmitDefaultValue=false)] public Receipt receipt;
 }
 [DataContract] public sealed class IdentityCheck {
  [DataMember] public string phase;
  [DataMember] public bool? document_iunknown_same;
  [DataMember] public bool? extension_iunknown_same;
  [DataMember] public int? foreground_same;
 }
 [DataContract] public sealed class NativeArguments {
  [DataMember] public string name;
  [DataMember] public int version=0;
  [DataMember] public int options=1;
  [DataMember] public string export_data="null object; installed PIA MarshalAs(IDispatch)";
  [DataMember] public string advanced_options="null object; installed PIA MarshalAs(IDispatch)";
  [DataMember] public string output_codes="Int32& [In,Out]; initialized Int32.MinValue";
 }
 [DataContract] public sealed class ObservedField {
  [DataMember] public string name;
  [DataMember] public string kind;
  [DataMember(EmitDefaultValue=false)] public string text;
  [DataMember(EmitDefaultValue=false)] public long? integer;
  [DataMember(EmitDefaultValue=false)] public bool? boolean;
  [DataMember(EmitDefaultValue=false)] public string[] strings;
 }
 [DataContract] public sealed class Observation {
  [DataMember] public string phase;
  [DataMember] public string current_field;
  [DataMember] public bool complete;
  [DataMember] public List<ObservedField> fields=new List<ObservedField>();
  public T Read<T>(string name, Func<T> read) {
   current_field=name; T value=read(); object raw=value;
   ObservedField f=new ObservedField {name=name};
   if(raw==null) f.kind="null";
   else if(raw is string) { f.kind="string"; f.text=(string)raw; }
   else if(raw is bool) { f.kind="bool"; f.boolean=(bool)raw; }
   else if(raw is int) { f.kind="int32"; f.integer=(int)raw; }
   else if(raw is long) { f.kind="int64"; f.integer=(long)raw; }
   else if(raw is string[]) { f.kind="strings"; f.strings=(string[])raw; }
   else throw new InvalidOperationException("unsupported observation value type");
   fields.Add(f); current_field=null; return value;
  }
 }
 [DataContract] public sealed class SourceFileState {
  [DataMember] public string volume_serial;
  [DataMember] public string file_id_128;
  [DataMember] public long size_bytes;
  [DataMember] public long creation_filetime;
  [DataMember] public long write_filetime;
  [DataMember] public long change_filetime;
  [DataMember] public uint attributes;
  [DataMember] public uint links;
  [DataMember] public bool delete_pending;
  [DataMember] public bool directory;
 }
 [DataContract] public sealed class SourceRead {
  [DataMember] public string phase;
  [DataMember] public string path;
  [DataMember] public string access="Read";
  [DataMember] public string share="ReadWrite (no Delete)";
  [DataMember] public SourceFileState before;
  [DataMember] public SourceFileState after;
  [DataMember] public SourceFileState path_after;
  [DataMember] public string sha256;
  [DataMember] public long bytes_read;
  [DataMember] public bool complete;
  [DataMember] public string error;
  [DataMember] public int? hresult;
  [DataMember] public int? win32_error;
 }
 [DataContract] public sealed class Receipt {
  [DataMember] public string schema = "swcli.typed-glb-helper.v1";
  [DataMember] public int helper_pid;
  [DataMember] public int python_worker_pid;
  [DataMember] public string pia_path;
  [DataMember] public string pia_sha256;
  [DataMember] public bool contract_accepted;
  [DataMember] public bool identity_accepted;
  [DataMember] public bool identity_only;
  [DataMember] public int save_attempts;
  [DataMember] public bool? api_saved;
  [DataMember] public int? save_errors;
  [DataMember] public int? save_warnings;
  [DataMember] public int errors_local = Int32.MinValue;
  [DataMember] public int warnings_local = Int32.MinValue;
  [DataMember] public string local_codes_meaning = "managed locals; native outputs accepted only after normal return";
  [DataMember] public int? hresult;
  [DataMember] public string hresult_kind;
  [DataMember] public string first_error;
  [DataMember] public string[] cleanup_errors = new string[0];
  [DataMember] public string[] consumed_roles = new string[0];
  [DataMember] public IdentityCheck[] identity_checks=new IdentityCheck[0];
  [DataMember] public NativeArguments arguments;
  [DataMember] public Observation[] observations=new Observation[0];
  [DataMember] public SourceRead[] source_reads=new SourceRead[0];
  [DataMember] public Snapshot before;
  [DataMember] public Snapshot after;
  [DataMember] public bool post_state_accepted;
  [DataMember] public string output;
  [DataMember] public string begin_utc;
  [DataMember] public string end_utc;
  [DataMember] public bool success;
  [DataMember] public bool ci_acceptance = false;
  [DataMember] public bool public_acceptance = false;
 }
 public static class Core {
  public const int MaxParcel = 1048576;
  public const int MaxFrame = 1500000;
  public static void Require(bool ok, string reason) { if (!ok) throw new InvalidOperationException(reason); }
  public static byte[] Encode<T>(T value) {
   using (MemoryStream s = new MemoryStream()) {
    new DataContractJsonSerializer(typeof(T)).WriteObject(s, value); return s.ToArray();
   }
  }
  public static T Decode<T>(byte[] data) {
   using (MemoryStream s = new MemoryStream(data)) {
    return (T)new DataContractJsonSerializer(typeof(T)).ReadObject(s);
   }
  }
  public static byte[] ReadExact(Stream stream, int count) {
   Require(count >= 0 && count <= MaxFrame, "frame length outside limit");
   byte[] data = new byte[count]; int offset = 0;
   while (offset < count) { int read = stream.Read(data, offset, count-offset); if (read == 0) throw new EndOfStreamException(); offset += read; }
   return data;
  }
  public static Message Receive(Stream stream, string nonce, string kind, string role) {
   byte[] header = ReadExact(stream, 4);
   int size = header[0] | header[1]<<8 | header[2]<<16 | header[3]<<24;
   Require(size > 0 && size <= MaxFrame, "invalid frame length");
   Message m = Decode<Message>(ReadExact(stream, size));
   Require(m != null && m.nonce == nonce && m.kind == kind && m.role == role, "frame kind/nonce/role mismatch");
   return m;
  }
  public static void Send(Stream stream, Message m) {
   byte[] data = Encode(m); Require(data.Length > 0 && data.Length <= MaxFrame, "frame too large");
   byte[] size = new byte[] { (byte)data.Length, (byte)(data.Length>>8), (byte)(data.Length>>16), (byte)(data.Length>>24) };
   stream.Write(size, 0, 4); stream.Write(data, 0, data.Length); stream.Flush();
  }
  public static byte[] Parcel(Message m) {
   Require(m.data != null && m.data.Length <= 1398104, "parcel encoding outside limit");
   byte[] data = Convert.FromBase64String(m.data);
   Require(data.Length > 0 && data.Length <= MaxParcel, "parcel outside limit"); return data;
  }
  public static void SameSnapshot(Snapshot a, Snapshot b) {
   Require(a != null && b != null, "missing identity snapshot");
   // Serialization uses this fixed data contract, so booleans/numbers/ordered configurations stay exact.
   Require(Encode(a).SequenceEqual(Encode(b)), "host/document/source snapshot differs");
  }
  public static void Fixture(Snapshot s, string output) {
   Require(s != null && s.pid > 0 && s.created_filetime > 0 && s.document_count == 1,
           "expected exactly one owned host document");
   Require(s.document_type == 1 && !s.modified && !s.read_only && !s.view_only && !s.active_sketch && s.foreground_same == 1,
           "expected saved writable clean foreground part outside sketch edit");
   Require(!s.visible && !String.IsNullOrEmpty(s.configuration) && s.configurations != null &&
           s.configurations.Contains(s.configuration), "hidden fixture configuration unreadable");
   Require(Path.IsPathRooted(s.path) && Path.GetExtension(s.path).Equals(".SLDPRT", StringComparison.OrdinalIgnoreCase) &&
           !String.IsNullOrEmpty(s.title) && s.source_sha256 != null && s.source_sha256.Length == 64,
           "source identity incomplete");
   Require(Path.IsPathRooted(output) && Path.GetDirectoryName(output) == Path.GetDirectoryName(s.path) &&
           System.Text.RegularExpressions.Regex.IsMatch(Path.GetFileName(output), @"^\.component-export\.[0-9a-f]{32}\.swcli\.GLB$"),
           "GLB staging string differs from pinned product convention");
   Require(!File.Exists(output), "staging output already exists");
  }
  public static FileStream OpenSourceReadOnly(string path) {
   // This grants our handle read access only; sharing does not grant us write access.
   return new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite);
  }
  public static void ValidSourceState(SourceFileState s) {
   Require(s!=null && s.volume_serial!=null && s.volume_serial.Length==16 && s.volume_serial!=new string('0',16) &&
           s.file_id_128!=null && s.file_id_128.Length==32 && s.file_id_128!=new string('0',32), "source file identity unavailable");
   Require(s.size_bytes>0 && s.creation_filetime>0 && s.write_filetime>0 && s.change_filetime>0 && s.links>0 &&
           !s.delete_pending && !s.directory && (s.attributes & 0x410)==0, "source is not a stable ordinary file");
  }
  public static string StableSourceHash(Stream stream, Func<SourceFileState> heldState, Func<SourceFileState> pathState, SourceRead evidence) {
   Require(stream.CanRead && !stream.CanWrite, "source observation stream must be read only");
   evidence.before=heldState(); ValidSourceState(evidence.before);
   long remaining=evidence.before.size_bytes; byte[] buffer=new byte[65536];
   using(SHA256 sha=SHA256.Create()) {
    while(remaining>0) {
     int read=stream.Read(buffer,0,(int)System.Math.Min((long)buffer.Length,remaining));
     if(read==0) throw new EndOfStreamException("source shortened during read");
     sha.TransformBlock(buffer,0,read,buffer,0); remaining-=read; evidence.bytes_read+=read;
    }
    Require(stream.ReadByte()==-1, "source grew during read");
    sha.TransformFinalBlock(new byte[0],0,0);
    evidence.sha256=BitConverter.ToString(sha.Hash).Replace("-", "").ToLowerInvariant();
   }
   evidence.after=heldState(); ValidSourceState(evidence.after);
   Require(Encode(evidence.before).SequenceEqual(Encode(evidence.after)), "held source identity/size/time changed");
   evidence.path_after=pathState(); ValidSourceState(evidence.path_after);
   Require(Encode(evidence.after).SequenceEqual(Encode(evidence.path_after)), "source path no longer identifies held file");
   evidence.complete=true; return evidence.sha256;
  }
  public static void SaveOnce(IModelDocExtension extension, string output, Receipt r) {
   Require(r.identity_accepted && r.contract_accepted && !r.identity_only && r.save_attempts == 0,
           "single SaveAs3 gate rejected");
   int errors = Int32.MinValue, warnings = Int32.MinValue;
   r.arguments=new NativeArguments { name=output };
   r.save_attempts = 1; r.begin_utc = DateTime.UtcNow.ToString("o");
   try {
    // Exact installed 33.5 PIA: Int32& [In,Out], not C# out-only parameters.
    bool saved = extension.SaveAs3(r.arguments.name, r.arguments.version, r.arguments.options, null, null, ref errors, ref warnings);
    r.api_saved = saved;
    if (errors != Int32.MinValue) r.save_errors = errors;
    if (warnings != Int32.MinValue) r.save_warnings = warnings;
    Require(errors != Int32.MinValue && warnings != Int32.MinValue, "SaveAs3 did not write both native codes");
    Require(saved && errors == 0, "SaveAs3 returned false or native save error");
   } catch (Exception ex) {
    r.first_error = ex.GetType().FullName + ": " + ex.Message;
    r.hresult = Marshal.GetHRForException(ex); r.hresult_kind=ex is COMException?"COMException":"managed-exception"; throw;
   } finally {
    r.errors_local = errors; r.warnings_local = warnings; r.end_utc = DateTime.UtcNow.ToString("o");
   }
  }
 }
}
