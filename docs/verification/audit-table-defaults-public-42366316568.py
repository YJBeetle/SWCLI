"""Exact original-evidence audit for the public native-guard run 42366316568."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('table_public_original_audit',
    Path(__file__).with_name('audit-table-defaults-public-42361458023.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
audit.PUBLIC = dict(run=42366316568, head='5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b',
                    artifact=13571309953, name='table-defaults-public-42366316568-1',
                    digest='337b23a2c96913725b3281a12325d918c539753e7a96fe6da4fabca6ed74f17b')

if __name__ == '__main__':
    audit.main()
