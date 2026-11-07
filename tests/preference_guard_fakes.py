from types import SimpleNamespace

def preference_peer():
    peer=SimpleNamespace(stamp=8, dirty=False, title='foreground', path='', extension=object(), configuration='Default')
    peer.GetType=lambda:1; peer.GetUpdateStamp=lambda:peer.stamp; peer.GetSaveFlag=lambda:peer.dirty
    peer.GetTitle=lambda:peer.title; peer.GetPathName=lambda:peer.path; peer.Extension=peer.extension
    peer.GetActiveConfiguration=lambda:SimpleNamespace(Name=peer.configuration)
    peer.IsOpenedReadOnly=lambda:False;peer.IsOpenedViewOnly=lambda:False
    peer.SketchManager=SimpleNamespace(ActiveSketch=None)
    return peer
