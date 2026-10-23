"""One platform-independent functional plan; restart only BETWEEN these sets."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    script: str
    kind: str
    args: tuple = ()


@dataclass(frozen=True)
class TestSet:
    name: str
    steps: tuple


def runtime_plan(suite):
    if suite not in ("core", "full"):
        raise ValueError("Unknown runtime suite")
    sets = [TestSet("native-model", (Step("verify-native-model.py", "modeling"),)),
            TestSet("assemblies", (Step("verify-assemblies.py", "modeling"),)),
            TestSet("exports", (Step("verify-exports.py", "modeling"),)),
            TestSet("drawing-save", (Step("verify-drawing-save.py", "modeling"),)),
            TestSet("drawing-save-as", (Step("verify-drawing-save-as.py", "modeling"),))]
    if suite == "full":
        sets += [TestSet("reverse-cut", (Step("verify-reverse-cut.py", "modeling"),)),
                 TestSet("feature-depth", (Step("verify-feature-depth.py", "modeling"),)),
                 TestSet("fillets", (Step("verify-fillets.py", "modeling"),)),
                 TestSet("drawings", (Step("verify-drawings.py", "modeling"),))]
    # Preserve cross-script host continuity without making unrelated CAD sets
    # inherit hours of graphics allocations. No restart between these two steps.
    sets.append(TestSet("continuation-front-diameter", (
        Step("verify-host-continuation.py", "modeling"),
        Step("verify-diameter-dimensions.py", "driving", ("--plane", "front", "--after-modeling")))))
    for plane in ("front", "top", "right"):
        if suite == "core" and plane != "front":
            sets.append(TestSet("geometry-" + plane, (
                Step("verify-plane-geometry.py", "driving", ("--plane", plane)),)))
            continue
        for aspect, script in (("diameter", "verify-diameter-dimensions.py"),
                               ("center", "verify-center-constraints.py"),
                               ("rectangle", "verify-rectangle-dimensions.py")):
            if plane == "front" and aspect == "diameter":
                continue  # Already covered in the required continuation set.
            sets.append(TestSet(aspect + "-" + plane, (Step(script, "driving", ("--plane", plane)),)))
    sets.append(TestSet("toolbox", (Step("verify-toolbox.py", "toolbox"),)))
    return tuple(sets)
