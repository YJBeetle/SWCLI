"""Small named functional entrypoints; CAD assertions stay in shared case classes."""
import importlib.util
from pathlib import Path
import sys


def invoke(script, case_set):
    path = Path(__file__).resolve().parents[1] / script
    spec = importlib.util.spec_from_file_location("shared_" + script.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main([*sys.argv[1:], "--case-set", case_set])


def modeling(case_set):
    return invoke("verify-modeling.py", case_set)


def driving(case_set):
    return invoke("verify-driving-dimensions.py", case_set)
