import os
import shutil
import urllib.request
from sys import platform
from pathlib import Path
from subprocess import check_output

PLAT_BASH = {
    'win32': r"c:\Program Files\Git\bin\bash.exe"
}

PROJ_DIR = Path(__file__).parent.parent
BUILD_DIR = (PROJ_DIR / 'build').absolute()
BUILD_DIR.mkdir(exist_ok=True)

INCLUDED_PLUGINS = [
]


PLAT_EXCLUDES = {
    'win32': ['pyobjc']
}


def run():
    bash = Path(PLAT_BASH.get(platform, shutil.which('bash')))

    if not bash.is_file():
        raise Exception('Could not find bash')

    os.chdir(PROJ_DIR)
    reqs = check_output([bash.as_posix(), '-c', 'poetry export --without-hashes'], encoding='utf-8').split('\n')
    if 'Warning' in reqs[0]:
        reqs = reqs[1:]  # skip the warning
    reqs.extend(INCLUDED_PLUGINS)
    reqs = '\n'.join(r for r in reqs if not any(e in r for e in PLAT_EXCLUDES.get(platform, [])))

    with open(BUILD_DIR / 'requirements.txt', 'w') as r:
        r.write(reqs)

    if platform == 'win32':
        print('Fetching latest texconv')
        CONTRIB_DIR = (BUILD_DIR.parent / 'starfab' / 'contrib')
        urllib.request.urlretrieve('https://github.com/Microsoft/DirectXTex/releases/latest/download/texconv.exe',
                                   str(CONTRIB_DIR / 'texconv.exe'))


if __name__ == "__main__":
    run()
