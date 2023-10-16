import os
import sys
from subprocess import check_output, check_call
from pathlib import Path

import toml

WIX_VERSION_TEMPLATE = """<Include>
  <?define ProductVersion={version}?>
</Include>"""


def run():
    pyproject_file = (Path(__file__).parent.parent / 'pyproject.toml').absolute()
    msi_version_file = (Path(__file__).parent.parent / 'windows' / 'msi' / 'StarFab' / 'ProductVersion.wxi').absolute()

    # this must go here
    import starfab
    version = starfab.__version__
    print(f'Syncing StarFab version to {version}')
    tag = check_output('git tag --points-at HEAD', shell=True, encoding='utf-8').strip()

    with pyproject_file.open('r') as p:
        pyproject = toml.load(p)

    pyproject['tool']['briefcase']['version'] = version.split('+')[0]
    pyproject['tool']['poetry']['version'] = version

    with pyproject_file.open('w') as p:
        toml.dump(pyproject, p)

    if msi_version_file.is_file():
        with msi_version_file.open('w') as f:
            f.write(WIX_VERSION_TEMPLATE.format(version=pyproject['tool']['briefcase']['version']))

    if tag and tag == version:
        if 'y' not in input('Update tag? [y/n] ').lower():
            return

        print(check_output(f'git tag -d {tag}', shell=True, encoding='utf-8'))
        check_changed = check_output('git status -s',
                                     shell=True, encoding='utf-8').strip().replace('M pyproject.toml', '')
        if check_changed:
            print(repr(check_changed))
            print('Unexpected modified files... bailing')
            sys.exit(1)
        check_output(f'git add pyproject.toml')
        print(check_output(f'git commit -m "{tag}"', shell=True, encoding='utf-8'))
        print(check_output(f'git tag {tag}', shell=True, encoding='utf-8'))
        print(check_output('git tag --points-at HEAD', shell=True, encoding='utf-8').strip())


if __name__ == "__main__":
    run()
