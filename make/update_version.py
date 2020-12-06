import os
import sys
from subprocess import check_output, check_call
from pathlib import Path

import toml


def run():
    pyproject_file = (Path(__file__).parent.parent / 'pyproject.toml').absolute()
    version_file = (Path(__file__).parent.parent / 'src' / 'scdv' / '_version.py').absolute()

    if version_file.is_file():
        os.unlink(version_file)

    # this must go here
    import scdv
    version = scdv.__version__
    tag = check_output('git tag --points-at HEAD', shell=True, encoding='utf-8').strip()

    with pyproject_file.open('r') as p:
        pyproject = toml.load(p)

    pyproject['tool']['briefcase']['version'] = version.split('+')[0]
    pyproject['tool']['poetry']['version'] = version

    with pyproject_file.open('w') as p:
        toml.dump(pyproject, p)

    with version_file.open('w') as v:
        v.write(f'version = "{version}"\n')

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
