# StarCitizen Data Viewer - SCDV

A UI on top of `scdatatools`.

### NOTE: scdv is considered pre-alpha. It's more of a proof of concept than a fully functional tool

If you have any problems or suggestions, create an [issue](https://gitlab.com/scmodding/tools/scdv/-/issues/new)!

![SCDV Screenshot](docs/assets/SCDV_screenshot.png "SCDV Screenshot")

# Installation

## Optional Dependencies

### View and Convert textures (dds)

To view or convert textures (.dds*) files, SCDV relies on [texconv](https://github.com/microsoft/DirectXTex/releases) or [compressonator](https://gpuopen.com/compressonator/). Ensure that `texconv` or `compressonatorcli` is installed and in your system `PATH`.

## Releases

Check the [releases](https://gitlab.com/scmodding/tools/scdv/-/releases) for pre-built packages.


## From source

SCDV uses [poetry](https://python-poetry.org/) and Python >= 3.8

```
git clone --recursive git@gitlab.com:scmods/scdv.git
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
