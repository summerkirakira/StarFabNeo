import os
import sys
import requests
import subprocess
from pathlib import Path

ORIGINS_TOKEN = os.environ.get('ORIGINS_TOKEN')

API_URL = f'https://gitlab.com/api/v4/projects/22161441/packages/generic'


def run():
    if not ORIGINS_TOKEN:
        print('Missing origins token, set ORIGINS_TOKEN')
        sys.exit(1)

    release = Path(sys.argv[1])
    if not release.is_file():
        print('Invalid release file: {release}')
        sys.exit()

    name, version = release.stem.split('-')

    input(f'Uploading {release.name} as {version}. Press enter to continue.')
    print(subprocess.check_output(
        f'curl --header "PRIVATE-TOKEN: {ORIGINS_TOKEN}" --upload-file "{release.absolute()}" '
        f'{API_URL}/{name}/{version}/{release.name}'
    ))


if __name__ == "__main__":
    run()
