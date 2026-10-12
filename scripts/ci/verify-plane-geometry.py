"""Daily non-front plane positive cylinder/rectangle geometry functional set."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.entrypoints import driving
if __name__ == "__main__":
    driving("geometry")
