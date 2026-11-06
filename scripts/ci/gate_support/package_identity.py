"""Verify installed wheel Python bytes against the exact checkout commit."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys


def verify_installed_package(checkout_root, *, installed_root=None, expected_commit=None):
    import swcli
    checkout=Path(checkout_root).resolve()
    installed=Path(installed_root or Path(swcli.__file__).parent).resolve()
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=checkout,timeout=60)
    head=git('rev-parse','HEAD').decode().strip()
    expected=expected_commit if expected_commit is not None else os.environ.get('GITHUB_SHA')
    if expected is not None and head!=expected:
        raise RuntimeError('checkout HEAD differs from the requested native CI commit')
    if installed==(checkout/'src/swcli').resolve():
        raise RuntimeError('native gate requires an installed wheel, not the editable checkout')
    tracked=git('ls-tree','-rz','--name-only',head,'--','src/swcli').decode().split('\0')
    names=sorted(name[len('src/swcli/'):] for name in tracked if name.endswith('.py'))
    if not names:raise RuntimeError('source commit has no SWCLI Python package')
    actual_names=sorted(path.relative_to(installed).as_posix() for path in installed.rglob('*.py'))
    if actual_names!=names:raise RuntimeError('installed wheel Python file set differs from source commit')
    files={}
    for name in names:
        expected_bytes=git('show',head+':src/swcli/'+name)
        payload=(installed/name).read_bytes()
        if payload!=expected_bytes:
            raise RuntimeError('installed wheel source differs from commit: '+name)
        files[name]=hashlib.sha256(payload).hexdigest()
    return dict(source_commit=head,package_version=swcli.__version__,python=sys.version,
                installed_package_root=str(installed),verified_python_files=len(files),files_sha256=files,
                matches_source_commit=True)
