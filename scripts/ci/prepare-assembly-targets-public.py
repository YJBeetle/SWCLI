"""Offline-only fixture/plan preparation. Never starts a daemon, COM, CAD or CI."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.assembly_target_public_plan import (
    durable, digest, execution_plan, extract_fixed, verify_metadata,
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-json',type=Path,required=True)
    parser.add_argument('--internal-zip',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    import json
    metadata=json.loads(args.metadata_json.read_text())
    verify_metadata(metadata)
    # Validation/extraction occurs in a new destination; original ZIP unchanged.
    root=args.output_dir.resolve();root.mkdir(parents=True,exist_ok=False)
    copied=extract_fixed(args.internal_zip,root/'fixtures')
    durable(root/'artifact-metadata.json',metadata)
    plan=execution_plan()
    plan.update(original_metadata_sha256=digest(args.metadata_json),prepared_metadata_sha256=digest(root/'artifact-metadata.json'),original_zip_path=str(args.internal_zip.resolve()),
                prepared_fixture_sha256=copied,preparer_sha256=digest(__file__),
                plan_module_sha256=digest(Path(__file__).parent/'gate_support/assembly_target_public_plan.py'))
    durable(root/'once-only-plan.json',plan)
    print(str(root/'once-only-plan.json'))


if __name__=='__main__':main()
