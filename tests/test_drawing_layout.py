from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ci"))
from gate_support.drawing_checks import standard_layout


def snapshot(first):
    matrices = [[1,0,0,0,1,0,0,0,1], [1,0,0,0,0,1,0,-1,0],
                [0,0,-1,0,1,0,1,0,0] if first else [0,0,1,0,1,0,-1,0,0]]
    positions = [[.07,.16 if first else .08], [.07,.08 if first else .16], [.18,.16 if first else .08]]
    return {"sheet": {"properties": [6,12,2,1,int(first),.297,.21,1]},
            "views": [{"position": p, "outline": [p[0]-.02,p[1]-.02,p[0]+.02,p[1]+.02],
                       "scale": [2,1], "transform": m+[0,0,0,2,0,0,0]}
                      for m,p in zip(matrices, positions)]}


class DrawingLayoutTests(unittest.TestCase):
    def test_both_projections_ignore_array_order(self):
        for first in (True, False):
            value = snapshot(first)
            value["views"].reverse()
            result = standard_layout(value, "first-angle" if first else "third-angle")
            self.assertTrue(result["passed"])
            self.assertIn("left" if first else "right", result["roles"])

    def test_bad_direction_scale_extent_alignment_and_overlap_fail(self):
        mutations = [lambda s: s["views"][1]["transform"].__setitem__(0, 0),
                     lambda s: s["views"][1]["transform"].__setitem__(12, 1),
                     lambda s: s["views"][0]["outline"].__setitem__(0, -.01),
                     lambda s: s["views"][1]["position"].__setitem__(0, .09),
                     lambda s: s["views"][1].__setitem__("outline", [.04,.14,.1,.18]),
                     lambda s: s["views"][1]["transform"].__setitem__(0, float("nan"))]
        for mutate in mutations:
            s = deepcopy(snapshot(True))
            mutate(s)
            with self.assertRaises(RuntimeError):
                standard_layout(s, "first-angle")
