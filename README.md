# StarCitizen Data Viewer - SCDV

A GUI built on top of [scdatatools](https://gitlab.com/scmodding/frameworks/scdatatools).

### NOTE: scdv is considered pre-alpha. It's more of a proof of concept than a fully functional tool

If you have any problems or suggestions, create an [issue](https://gitlab.com/scmodding/tools/scdv/-/issues/new)!

![SCDV Screenshot](docs/assets/SCDV_screenshot.png "SCDV Screenshot")

# Features

- Browse and export files from `Data.p4k`
- Automatically converts `CryXmlB` files
- File viewer for human readable files
- Image viewer with support for Star Citizen `.dds` textures
- Integrated Python console for scripted access to the `p4k` and `datacore`
- Game audio explorer with auto-conversion

# Installation

## Optional Dependencies

### View and Convert textures (dds)

To view or convert textures (.dds*) files, SCDV relies on [texconv](https://github.com/microsoft/DirectXTex/releases) or [compressonator](https://gpuopen.com/compressonator/). Ensure that `texconv` or `compressonatorcli` is installed and in your system `PATH`.

### Convert Audio Files (wem)

To convert wem files, you must have [ww2ogg](https://github.com/hcs64/ww2ogg) and [revorb](https://cloudflare-ipfs.com/ipfs/QmVgjfU7qgPEtANatrfh7VQJby9t1ojrTbN7X8Ei4djF4e/revorb.exe) in your path. **Both are included in the MSI installer for Windows.**

> **Note for Windows: you must have the Vorbis codecs installed to listen to audio in SCDV. You can download them on [Xiph.org](https://xiph.org/dshow/downloads/)**


## Releases

Check the [releases](https://gitlab.com/scmodding/tools/scdv/-/releases) for pre-built packages.


## From source

SCDV uses [poetry](https://python-poetry.org/) and Python >= 3.8

```
git clone --recursive git@gitlab.com:scmodding/tools/scdv.git
cd scdv
poetry install
poetry run python -m scdv
```

###

![MadeByTheCommunity](docs/assets/MadeByTheCommunity_Black.png "Made By The Community")

This project is not endorsed by or affiliated with the Cloud Imperium or Roberts Space Industries group of companies.
All game content and materials are copyright Cloud Imperium Rights LLC and Cloud Imperium Rights Ltd..  Star Citizen®,
Squadron 42®, Roberts Space Industries®, and Cloud Imperium® are registered trademarks of Cloud Imperium Rights LLC.
All rights reserved.
