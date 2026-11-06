"""Select exactly one legal CI route before any private/native job can run."""
import os
from pathlib import Path
import sys

REPOSITORY = 'YJBeetle/SWCLI'
FONT_REF = 'refs/heads/codex/docprops-font-scopes'
FONT_PROFILES = ('internal', 'public-notes')


def select_profile(*, event, repository, ref, fonts, native_full, font_profile='internal'):
    if event == 'push':
        return 'standard'
    if event != 'workflow_dispatch':
        raise ValueError('this workflow accepts only push or explicit manual dispatch')
    if type(fonts) is not bool or type(native_full) is not bool:
        raise ValueError('manual CI selectors must be booleans')
    if font_profile not in FONT_PROFILES:
        raise ValueError('unknown font validation profile')
    if fonts and native_full:
        raise ValueError('font validation and native_full are mutually exclusive')
    if (fonts or native_full) and repository != REPOSITORY:
        raise ValueError('private native validation is restricted to the owning repository')
    if fonts:
        if ref != FONT_REF:
            raise ValueError('font validation requires the explicitly authorized font branch')
        return 'font-scopes'
    if font_profile != 'internal':
        raise ValueError('public-notes requires the explicit font validation selector')
    return 'standard'


def boolean(value):
    if value in ('', 'false'):
        return False
    if value == 'true':
        return True
    raise ValueError('invalid boolean CI selector')


def main():
    try:
        selected = select_profile(event=os.environ['GITHUB_EVENT_NAME'], repository=os.environ['GITHUB_REPOSITORY'],
            ref=os.environ['GITHUB_REF'], fonts=boolean(os.environ.get('SWCLI_FONT_VALIDATION', '')),
            native_full=boolean(os.environ.get('SWCLI_NATIVE_FULL', '')),
            font_profile=os.environ.get('SWCLI_FONT_PROFILE') or 'internal')
    except (KeyError, ValueError) as exc:
        print('CI dispatch rejected: ' + str(exc), file=sys.stderr)
        return 1
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as stream:
        stream.write('validation_profile=' + selected + '\n')
    print('Selected CI validation profile: ' + selected)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
