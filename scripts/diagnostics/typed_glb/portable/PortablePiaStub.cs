// PORTABLE TESTS ONLY. Never deployed, never a substitute for the installed PIA.
using System;
using System.Runtime.InteropServices;
namespace SolidWorks.Interop.sldworks {
 // Installed PIA also exports these names; importing its namespace must not shadow System.
 public sealed class Attribute { }
 public sealed class Environment { }
 public interface IModelDocExtension {
  bool SaveAs3([In,MarshalAs(UnmanagedType.BStr)] string name, [In] int version, [In] int options,
   [In,MarshalAs(UnmanagedType.IDispatch)] object exportData, [In,MarshalAs(UnmanagedType.IDispatch)] object advanced,
   [In,Out] ref int errors, [In,Out] ref int warnings);
 }
 public interface ISldWorks {
  object ActiveDoc {get;} int IsSame(object a,object b); int GetProcessID(); string RevisionNumber(); int GetDocumentCount();
  bool Visible {get;} bool CommandInProgress {get;} bool UserControl {get;} bool UserControlBackground {get;}
 }
 public interface IModelDoc2 {
  object Extension {get;} string GetPathName(); string GetTitle(); int GetType(); int GetUpdateStamp(); bool GetSaveFlag();
  object ConfigurationManager {get;} object GetConfigurationNames(); bool IsOpenedReadOnly(); bool IsOpenedViewOnly(); object SketchManager {get;}
 }
 public interface IConfigurationManager { object ActiveConfiguration {get;} }
 public interface IConfiguration { string Name {get;} }
 public interface ISketchManager { object ActiveSketch {get;} }
}
