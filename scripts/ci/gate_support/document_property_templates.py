"""Choose only exact installed GB templates; never open/probe arbitrary templates."""
import argparse
import json
from pathlib import Path

NAMES = {'part': 'gb_part.prtdot', 'assembly': 'gb_assembly.asmdot', 'drawing': 'gb_a4.drwdot'}


def templates(program_data, installation):
    result = {}
    roots = (Path(installation) / 'data/templates', Path(program_data) / 'SOLIDWORKS')
    for kind, name in NAMES.items():
        # Installation ships gb.drwdot; the per-user folder calls it gb_a4.
        installed_name = 'gb.drwdot' if kind == 'drawing' else name
        explicit = roots[0] / installed_name
        if explicit.is_file() and not explicit.is_symlink():
            result[kind] = str(explicit.resolve())
            continue
        matches = sorted(p for p in roots[1].rglob('*') if p.is_file() and not p.is_symlink()
                         and p.name.casefold() == name and p.parent.name.casefold() == 'templates')
        if len(matches) != 1:
            raise RuntimeError(f'Expected one explicit installed GB {kind} template, found {len(matches)}; no arbitrary fallback')
        result[kind] = str(matches[0].resolve())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program-data', required=True)
    parser.add_argument('--installation', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    report = {'success': False, 'program_data': args.program_data, 'installation': args.installation}
    try:
        selected = templates(args.program_data, args.installation)
        report.update(success=True, selected=selected)
        print(json.dumps(selected))
    except BaseException as error:
        report['failure'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
