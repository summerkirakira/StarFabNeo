import os
import sys
import shutil
import requests
import subprocess
from pathlib import Path

STARFAB_TOKEN = os.environ.get('STARFAB_TOKEN')

API_URL = f'https://gitlab.com/api/v4/projects/22934039/packages/generic'


def run():
    if not STARFAB_TOKEN:
        print('Missing starfab token, set STARFAB_TOKEN')
        sys.exit(1)

    release = Path(sys.argv[1])
    if not release.is_file():
        print('Invalid release file: {release}')
        sys.exit()

    curl = shutil.which('curl')
    if not curl:
        raise RuntimeError('Could not find curl')

    name, version, *_ = release.stem.split('-')

    input(f'Uploading {release.name} as {version}. Press enter to continue.')
    print(subprocess.check_output(
        f'curl --header "PRIVATE-TOKEN: {STARFAB_TOKEN}" --upload-file "{release.absolute()}" '
        f'{API_URL}/{name}/{version}/{release.name}',
        shell=True
    ))


if __name__ == "__main__":
    run()
