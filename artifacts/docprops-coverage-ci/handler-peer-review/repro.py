"""Mock-only defect probes against one isolated exact-head source snapshot. Never uses CAD."""
import importlib,json,sys
from types import SimpleNamespace
from unittest.mock import Mock,patch

name=sys.argv[1]
configs={
'docprops-line-style':('document_line_font_set','set_document_line_font_windows','test_document_line_font','LineFontTests','Integer'),
'docprops-dimension-format':('document_dimension_format_set','set_dimension_format_windows','test_dimension_format','DimensionFormatTests','Toggle'),
'docprops-table-defaults':('document_table_option_set','set_document_table_option_windows','test_document_tables','DocumentTableTests','Integer'),
'docprops-units-expanded':('document_unit_profile_set','set_document_unit_profile_windows','test_document_unit_profile','UnitProfileTests','Integer'),
'docprops-export-options':('document_image_quality_set','set_document_image_quality_windows','test_document_image_quality','ImageQualityTests','Toggle')}
handler,setter,module,cls,family=configs[name]
ops=importlib.import_module('swcli.daemon.operations')
receipt=dict(ok=True,action='mock',changed=True,mutation=dict(attempted=True,may_have_changed=True))
changed=[]
def successful_adapter(**kwargs):
 changed.append('native setter simulated success');return receipt
registry=SimpleNamespace(describe=Mock(side_effect=RuntimeError('injected post-set document descriptor failure')))
context=SimpleNamespace(app=object(),entry=SimpleNamespace(document=object()),documents=registry,session_id='review')
values=dict(field='mock',value='mock',expected_snapshot={})
partial={}
with patch.object(ops,setter,side_effect=successful_adapter):
 try:
  returned=getattr(ops,handler)(context,values);partial=dict(returned=returned,exception=None)
 except Exception as error:partial=dict(returned=None,exception=dict(type=type(error).__name__,message=str(error)))
partial.update(adapter_called=len(changed),descriptor_called=registry.describe.call_count,adapter_receipt=receipt,mutation_reached_response=bool(partial['returned'] and partial['returned'].get('mutation')))
assert partial['adapter_called']==partial['descriptor_called']==1

fixture_cls=getattr(importlib.import_module(module),cls)
peer=[]
for member,new in [('GetUpdateStamp',99999),('GetSaveFlag',True),('GetTitle','Peer changed'),('GetPathName','C:\\peer-changed.SLDPRT')]:
 case=fixture_cls();case.setUp()
 try:
  fixture=case.fx if name=='docprops-line-style' else case
  foreground=fixture.foreground
  document=fixture.document
  extension=document.Extension
  native=getattr(extension,'SetUserPreference'+family)
  original=native.side_effect
  before=getattr(foreground,member)()
  def mutate(*args,**kwargs):
   result=original(*args,**kwargs)
   setattr(foreground,member,lambda:new)
   return result
  native.side_effect=mutate
  try:
   if name=='docprops-line-style':result=case.edit(_internal_calibration=True)
   elif name=='docprops-units-expanded':result=case.edit(calibration=True)
   else:result=case.edit()
   entry=dict(member=member,before=before,after=getattr(foreground,member)(),active_pointer_preserved=fixture.app.ActiveDoc is foreground,adapter_or_handler_returned=result)
  except Exception as error:entry=dict(member=member,before=before,after=getattr(foreground,member)(),active_pointer_preserved=fixture.app.ActiveDoc is foreground,exception=dict(type=type(error).__name__,message=str(error)))
  peer.append(entry)
 finally:case.doCleanups()
print(json.dumps(dict(scope='mock-only; not native acceptance',name=name,post_adapter_descriptor_fault=partial,foreground_peer_probes=peer),ensure_ascii=False))
