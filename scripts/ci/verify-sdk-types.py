"""Check SDK generation, strict types, and real consumer typing acceptance/refusal."""

from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/dev/generate-sdk.py"), "--check"], check=True)
    with tempfile.TemporaryDirectory(prefix="swcli-sdk-mypy-") as cache:
        command = [sys.executable, "-m", "mypy", "--cache-dir", cache,
                   "--python-version", "3.9", "--follow-imports=silent", "--ignore-missing-imports", "--strict"]
        accepted = ROOT / "tests/typing_sdk/accepted.py"
        subprocess.run([*command, str(ROOT / "src/swcli/sdk"), str(accepted)], cwd=ROOT, check=True)
        rejected = ROOT / "tests/typing_sdk/rejected.py"
        result = subprocess.run([*command, "--no-error-summary", "--show-error-codes", str(rejected)],
                                cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 1:
            raise RuntimeError("Negative typing fixture did not produce ordinary type errors: " + result.stdout + result.stderr)
        expected = {index: re.search(r"# E: ([a-z-]+)", line).group(1)
                    for index, line in enumerate(rejected.read_text().splitlines(), 1) if "# E: " in line}
        actual = {}
        for line in result.stdout.splitlines():
            if ": note: " in line:
                continue
            match = re.search(r"rejected\.py:(\d+): error: .*\[([a-z-]+)\]$", line)
            if not match:
                raise RuntimeError("Unexpected typing diagnostic: " + line)
            actual[int(match.group(1))] = match.group(2)
        if actual != expected:
            raise RuntimeError(f"Typed consumer acceptance differs: {actual!r} != {expected!r}")
        print(f"SDK generator, strict implementation and {len(expected)} consumer typing refusals verified")


if __name__ == "__main__":
    main()
