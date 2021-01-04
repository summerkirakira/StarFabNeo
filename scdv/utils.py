import os
import io
import sys
import typing
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
        self.texconv = shutil.which('texconv')

        self.converter = self.texconv if self.texconv else self.compressonatorcli

    def _check_bin(self):
        if not self.converter:
            qtw.QMessageBox.information(
                None, "Image Converter",
                f"Missing a DDS converter. If you're on Mac/Linux use compressonatorcli. You can install it from "
                f"<a href='https://gpuopen.com/compressonator/'>https://www.steamgriddb.com/manager</a>. If you're on"
                f"windows you can use texconv, download it from "
                f"<a href='https://github.com/microsoft/DirectXTex/releases'>"
                f"https://github.com/microsoft/DirectXTex/releases</a>. Ensure whichever tool is in your system PATH."
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
        # TODO: throw up a loading dialog?
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

        try:
            # Make sure we're preventing access to the in file
            tmpin.close()
            # TODO: logging...
            ft = outfile.suffix[1:]  # remove the '.'
            texconv_err = ''
            if self.texconv:
                cmd = f'{self.texconv} -ft {ft} -f rgba -nologo {tmpin.name}'
                try:
                    r = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
                                       cwd=outfile.parent)
                except subprocess.CalledProcessError as e:
                    texconv_err = e.output.decode('utf-8')

                shutil.move(outfile.parent / f'{Path(tmpin.name).stem}.{ft}', outfile.absolute())

            if not self.texconv or texconv_err:
                cmd = f'{self.compressonatorcli} -noprogress {tmpin.name} {outfile.absolute()}'
                try:
                    r = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
                except subprocess.CalledProcessError as e:
                    if texconv_err:
                        raise RuntimeError(f'Error converting with texconv: {texconv_err}')
                    raise RuntimeError(f'Error converting with compressonator: {e}')

        finally:
            if _delete:
                os.unlink(tmpin.name)

        return True, r.stdout.decode('utf-8', errors="ignore")


image_converter = ImageConverter()
