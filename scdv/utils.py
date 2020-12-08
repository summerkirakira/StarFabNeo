import os
import io
import sys
import typing
import subprocess
import shutil
import tempfile
import subprocess
from pathlib import Path

from scdv.ui import qtw


def show_file_in_filemanager(path):
    if sys.platform == "win32":
        subprocess.Popen(['explorer', str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class NamedBytesIO(io.BytesIO):
    def __init__(self, content: bytes, name: str) -> None:
        super().__init__(content)
        self._name = name

    @property
    def name(self):
        return self._name


class ImageConverter:
    def __init__(self):
        self.compressonatorcli = shutil.which('compressonatorcli')

    def _check_bin(self):
        if not self.compressonatorcli:
            qtw.QMessageBox.information(
                None, "Image Converter",
                f"Missing compressonatorcli. Please install it from <a href='https://gpuopen.com/compressonator/'>"
                f"https://www.steamgriddb.com/manager</a> and ensure it is in your system PATH."
            )
            raise RuntimeError(f'Cannot find compressonatorcli')

    def convert_buffer(self, inbuf, in_format, out_format='tif') -> bytes:
        """ Converts a buffer `inbuf` to the output format `out_format` """
        self._check_bin()

        _ = tempfile.NamedTemporaryFile(suffix=f'.{out_format.lstrip(".")}')
        tmpout = Path(_.name)
        _.close()

        success, msg = self.convert(NamedBytesIO(inbuf, name=f'tmp.{in_format}'), tmpout)

        if not success:
            raise RuntimeError(f'Failed to convert buffer: {msg}')

        with tmpout.open('rb') as f:
            buf = f.read()
        os.unlink(tmpout)
        return buf

    def convert(self, infile: typing.Union[str, Path, io.BufferedIOBase, io.RawIOBase],
                outfile: typing.Union[str, Path]) -> (bool, str):
        """ Convert the file, provided by `infile` to `outfile`

        :param infile:  A string or Path object - or a file-like object (with a correct .name attribute)
        :param outfile:  The output file path
        :returns (bool, msg): Whether or not the conversion was successful as well as the output from the conversion
            utility
        """
        self._check_bin()

        if isinstance(outfile, str):
            outfile = Path(outfile)
        if outfile.exists():
            raise ValueError(f'outfile "{outfile}" already exists')

        _delete = True

        if isinstance(infile, (str, Path)):
            tmpin = open(infile, 'rb')
            _delete = False
        else:
            infile.seek(0)
            tmpin = tempfile.NamedTemporaryFile(suffix=Path(infile.name).suffix, delete=False)
            tmpin.write(infile.read())

        # Make sure we're preventing access to the in file
        tmpin.close()
        # TODO: logging...
        cmd = f'{self.compressonatorcli} {tmpin.name} {outfile.absolute()}'
        try:
            r = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as e:
            return False, e.output.decode('utf-8')

        if _delete:
            os.unlink(tmpin.name)

        return True, r.stdout.decode('utf-8')


image_converter = ImageConverter()
