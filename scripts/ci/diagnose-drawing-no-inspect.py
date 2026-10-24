"""Diagnostic only: isolate structure traversal from same-path drawing reopen."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.entrypoints import modeling
if __name__ == "__main__":
    modeling("drawing-reopen-no-inspect")
