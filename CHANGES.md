
# Version History

See current releases on [GitLab](https://gitlab.com/scmodding/tools/starfab/-/releases/)

## [0.4.7](https://gitlab.com/scmodding/tools/starfab/-/releases/0.4.7)

* New material name normalization. All material names in `mtl` have spaces converted to underscores as the Blender
  DAE importer does not handle material names with spaces. This happens during any export as long as cryxml
  conversion is enabled
* Added export to the action map
* Tree views now sort folders before files by default

## [0.4.6](https://gitlab.com/scmodding/tools/starfab/-/releases/0.4.6)

- Added support for changes from SC 3.17.0 (lighting and chr changes)
- Fixed HardSurface shader normals and emission issues
- Fixed StarFab not launching when it had never been used before
- Fixed crash when trying to load an invalid SC folder
- Fixed crash when unloading (when attempting to open a different SC folder when one was already loaded)

## [0.4.5](https://gitlab.com/scmodding/tools/starfab/-/releases/0.4.5)

- Content view filtering fixes
- Settings refactor. Fixed settings not saving/persisting
- Export options refactor. Fixed export converters not running in certain instances
- General logging improvements

## [0.4.4](https://gitlab.com/scmodding/tools/starfab/-/releases/0.4.4)

- Added (optional) error reporting. The dialog can be disabled in settings.
- Added `Model Asset Extractor` "converter" that will automatically select the associated `mtl` and textures for each
  model in the extraction task. Not recommended while extracting the entire p4k as this will just increase the overhead
- Added initial object container view widget
- Numerous Blender importer shader/material/texture improvements and fixes
- Number of bug fixes throughout StarFab
- Fixed icons disappearing
- General logging improvements

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
