import sys
import subprocess


def show_file_in_filemanager(path):
    if sys.platform == "win32":
        subprocess.Popen(['explorer', str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
