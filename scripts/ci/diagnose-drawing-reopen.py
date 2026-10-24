"""Diagnostic only: close/reopen one private copy, without source open or save."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.entrypoints import modeling
if __name__ == "__main__":
    modeling("drawing-copy-reopen")
