
# Version History

See current releases on [GitLab](https://gitlab.com/scmodding/tools/starfab/-/releases/)

## [0.4.3](https://gitlab.com/scmodding/tools/starfab/-/releases/0.4.3)

- Fixed texture conversion issue when exporting directly from the p4k
- Fixed issue displaying invalid entries in the datacore
- Added new update check on startup (can be disabled in settings)
- Updated scdatatools version to 1.0.1

## [0.4.2](https://gitlab.com/scmodding/tools/starfab/-/releases/0.4.2)

- Initial public release!

## [0.3.1](https://gitlab.com/scmodding/tools/starfab/-/releases/0.3.1)

### Fixes

- Windows MSI installer version now properly uses included `ww2ogg` and `revorb` for audio conversion

## [0.3.0](https://gitlab.com/scmodding/tools/starfab/-/releases/0.3.0)

### New Features

- Upgraded to scdatatools 0.1.9 which improves support for audio files
- Improved Audio Widget with better support for searching.

## [0.2.9](https://gitlab.com/scmodding/tools/starfab/-/releases/0.2.9)

### New Features

- Widgets do not automatically open when you open a Star Citizen directory which means opening a directory is much faster.  Widgets will load when you open them from the View menu.
- Added a recently opened menu option
- Initial release of the Ship Entity Extractor which will extract all associated files with a ship entity (or at least try to) (you must open the datacore before you can use the tool)
- Initial release of the Audio widget. First support is for GameAudio sounds. This allows you to browse, extract and listen to audio files from the game.
- Updated to scdatatools 0.1.8. `socpak` files (and other sub-archives) are merged into a unified view of `Data.p4k`. Now you can browse into and extract data from object containers.
- Chunked file view has been added. Initial support for displaying chunk data is limited, but most importantly human-readable data is displayed inline

## [0.2.5](https://gitlab.com/scmodding/tools/starfab/-/releases/0.2.5)

### New Features

- Calculated time modified and size for P4K directories
- Sorting by time/size now works properly
- texconv is now included by default in the MSI installer for Windows

### Fixes

- Fixed python console causing a crash on Windows

## [0.2.3](https://gitlab.com/scmodding/tools/starfab/-/releases/0.2.3)

### New Features

- Upgraded scdatatools, includes support for Datacore v5

## [0.2.2](https://gitlab.com/scmodding/tools/starfab/-/releases/0.2.2)

### New Features

- Improvements in dependencies
- Improved DDS texture handling

## [0.2.1](https://gitlab.com/scmodding/tools/starfab/-/releases/0.2.1)

### New Features

- Tested on Linux
- Now using compressonatorcli to convert/view DDS textures
- More UI enhancements

## [0.1.0](https://gitlab.com/scmodding/tools/starfab/-/releases/0.1.0)

### New Features

- Initial proof of concept!
