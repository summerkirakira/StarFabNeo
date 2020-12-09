# StarCitizen Data Viewer - SCDV

A UI on top of `scdatatools`.

### NOTE: scdv is considered pre-alpha. It's more of a proof of concept than a fully functional tool

If you have any problems or suggestions, create an [issue](https://gitlab.com/scmods/scdv/-/issues/new)!

# Installation

## Optional Dependencies

### View and Convert textures (dds)

To view or convert textures (.dds*) files, SCDV relies on [compressonator](https://gpuopen.com/compressonator/). Ensure that the `compressonatorcli` is installed and in your system `PATH`.

## Release

Check the [releases](https://gitlab.com/scmods/scdv/-/releases) for pre-built packages.


## From source

SCDV uses [poetry](https://python-poetry.org/) and Python >= 3.8

```
git clone --recursive git@gitlab.com:scmods/scdv.git
cd scdv
poetry install
poetry run python -m scdv
```
