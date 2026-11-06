"""Public acceptance oracles reject wrong saved content; no CAD is started."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_revolve_public_gate',ROOT/'scripts/ci/verify-revolve-public.py')
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
IDENTITY=[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]


def profile():
    corners=[dict(x=0,y=-5,z=0),dict(x=10,y=-5,z=0),dict(x=10,y=15,z=0),dict(x=0,y=15,z=0)]
    segments=[dict(construction=False,geometry=dict(kind='line',start_mm=corners[i],end_mm=corners[(i+1)%4])) for i in range(4)]
    segments += [dict(construction=True,geometry=None),dict(construction=True,geometry=None)]
    return dict(geometry_complete=True,editing=False,profile_segment_count=4,segment_count=6,
                segments=segments,model_to_sketch_transform=IDENTITY[:])


class SavedProfileOracleTests(unittest.TestCase):
    def test_saved_rectangle_requires_same_four_sides_and_plane(self):
        saved=profile()
        gate.verify_saved_profile(saved,[0,-5,10,15],IDENTITY)
        saved['segments'].reverse()
        gate.verify_saved_profile(saved,[0,-5,10,15],IDENTITY)
        for edit in (
            lambda x:x.update(editing=True),
            lambda x:x.update(geometry_complete=False),
            lambda x:x['segments'][0]['geometry'].update(end_mm=dict(x=9,y=-5,z=0)),
            lambda x:x['segments'][1].update(geometry=deepcopy(x['segments'][0]['geometry'])),
            lambda x:x['model_to_sketch_transform'].__setitem__(4,-1),
            lambda x:x.update(model_to_sketch_transform=IDENTITY[:3])):
            changed=profile();edit(changed)
            with self.subTest(edit=edit),self.assertRaises(RuntimeError):
                gate.verify_saved_profile(changed,[0,-5,10,15],IDENTITY)

    def test_shutdown_failure_preserves_the_first_group_error(self):
        first=RuntimeError('first startup failure')
        second=RuntimeError('secondary shutdown failure')
        runner=SimpleNamespace(record={},start=mock.Mock(side_effect=first),
                               stop=mock.Mock(side_effect=second),checkpoint=mock.Mock())
        runtime=SimpleNamespace(Runner=mock.Mock(return_value=runner))
        with mock.patch.object(gate,'load',return_value=runtime),mock.patch.dict(gate.os.environ,{},clear=True):
            with self.assertRaises(RuntimeError) as caught:gate.worker(Path('/unused-oracle-output'))
        self.assertIs(caught.exception,first)
        self.assertEqual(runner.record['error']['message'],'first startup failure')
        self.assertEqual(runner.record['shutdown_error']['message'],'secondary shutdown failure')
        runner.start.assert_called_once()

    def test_public_acceptance_is_only_marked_after_successful_owned_shutdown(self):
        for shutdown_error in (None,RuntimeError('shutdown failed')):
            with self.subTest(shutdown_error=shutdown_error),tempfile.TemporaryDirectory() as directory:
                runner=SimpleNamespace(record={},start=mock.Mock(),stop=mock.Mock(side_effect=shutdown_error),checkpoint=mock.Mock())
                runtime=SimpleNamespace(Runner=mock.Mock(return_value=runner))
                smoke=SimpleNamespace(record=dict(success=False,cleanup_errors=[],public_acceptance=False),
                                      cleanup=mock.Mock(),checkpoint=mock.Mock(),checkpoint_error=None)
                def completed(g):g.record.update(success=True,state='completed')
                with mock.patch.object(gate,'load',return_value=runtime), \
                     mock.patch.object(gate.modeling,'ModelingSmoke',return_value=smoke), \
                     mock.patch.object(gate,'run',side_effect=completed), \
                     mock.patch.dict(gate.os.environ,{},clear=True):
                    if shutdown_error is not None:
                        with self.assertRaises(RuntimeError) as caught:gate.worker(Path(directory))
                        self.assertIs(caught.exception,shutdown_error)
                        self.assertFalse(smoke.record['public_acceptance'])
                    else:
                        gate.worker(Path(directory))
                        self.assertTrue(smoke.record['public_acceptance'])
                runner.start.assert_called_once();runner.stop.assert_called_once()

    def test_public_gate_has_no_com_import_and_explicit_budget(self):
        import ast
        script=(ROOT/'scripts/ci/verify-revolve-public.py').read_text()
        tree=ast.parse(script)
        imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
            if isinstance(node,ast.ImportFrom):imports.append(node.module or '')
        self.assertFalse(any('win32' in x or 'pythoncom' in x or x.startswith('swcli.hosts') for x in imports))
        self.assertIn('child.wait(timeout=1800)',script)
        self.assertIn('request_timeout_seconds=600',script)
        self.assertEqual(script.count('runner.start(item)'),1)
        self.assertIn('public_acceptance=False',script)
        self.assertIn("gate.record['public_acceptance']=True",script)


if __name__=='__main__':unittest.main()
