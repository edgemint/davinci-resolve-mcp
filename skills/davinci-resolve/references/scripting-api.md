# DaVinci Resolve Python Scripting API Reference

Based on official API v20.3 (Oct 2025).

---

## Table of Contents

- [Preamble](#preamble)
- [Object Hierarchy](#object-hierarchy)
- [Pre-loaded Variables (execute_script)](#pre-loaded-variables-execute_script)
- [Resolve](#resolve)
- [ProjectManager](#projectmanager)
- [Project](#project)
  - [Render Settings Keys](#render-settings-keys)
  - [Common Project Settings](#common-project-settings)
- [MediaStorage](#mediastorage)
- [MediaPool](#mediapool)
  - [clipInfo Dictionary](#clipinfo-dictionary)
- [Folder](#folder)
- [MediaPoolItem](#mediapoolitem)
- [Timeline](#timeline)
  - [Grade Modes](#grade-modes-for-applygraderfromdrx)
  - [Marker Format](#marker-format)
- [TimelineItem](#timelineitem)
  - [CDL Map Format](#cdl-map-format)
  - [TimelineItem Properties](#timelineitem-properties-setpropertygetproperty)
- [Gallery](#gallery)
- [GalleryStillAlbum](#gallerystillalbum)
- [Enumerated Values](#enumerated-values)

---

## Preamble

- API version: v20.3 (Oct 2025)
- Python >= 3.6 64-bit and Lua 5.1 are supported
- From v16.2.0+, `nodeIndex` parameters in `SetLUT()` / `SetCDL()` are **1-based** (`1 <= nodeIndex <= total nodes`)
- Most methods return `False` or `None` on failure; check return values

---

## Object Hierarchy

```
Resolve (root)
  ├── Fusion
  ├── MediaStorage
  └── ProjectManager
        └── Project
              ├── MediaPool
              │     ├── Folder
              │     │     ├── MediaPoolItem
              │     │     └── Folder (recursive)
              │     └── Timeline
              │           └── TimelineItem
              │                 └── MediaPoolItem
              ├── Gallery
              │     └── GalleryStillAlbum
              │           └── GalleryStill
              └── ColorGroup
```

---

## Pre-loaded Variables (execute_script)

When using the `execute_script` MCP tool, these objects are available without any initialization:

| Variable | Type | Description |
|---|---|---|
| `resolve` | Resolve | Root application object |
| `project_manager` | ProjectManager | Current database project manager |
| `project` | Project | Currently open project |
| `media_pool` | MediaPool | Media pool of current project |
| `timeline` | Timeline | Currently active timeline |

---

## Resolve

| Method | Return | Description |
|---|---|---|
| `Fusion()` | Fusion | Returns the Fusion object |
| `GetMediaStorage()` | MediaStorage | Returns the media storage object |
| `GetProjectManager()` | ProjectManager | Returns project manager for current database |
| `OpenPage(pageName)` | Bool | Switch to page: `"media"`, `"cut"`, `"edit"`, `"fusion"`, `"color"`, `"fairlight"`, `"deliver"` |
| `GetCurrentPage()` | string | Returns current page name |
| `GetProductName()` | string | Returns product name (e.g., `"DaVinci Resolve"`) |
| `GetVersion()` | [int] | Returns `[major, minor, patch, build, suffix]` |
| `GetVersionString()` | string | Returns version as human-readable string |
| `LoadLayoutPreset(presetName)` | Bool | Load a saved UI layout preset |
| `UpdateLayoutPreset(presetName)` | Bool | Overwrite existing preset with current layout |
| `ExportLayoutPreset(presetName, path)` | Bool | Export preset to file at `path` |
| `DeleteLayoutPreset(presetName)` | Bool | Delete a UI layout preset |
| `SaveLayoutPreset(presetName)` | Bool | Save current UI layout as a named preset |
| `ImportLayoutPreset(path, presetName)` | Bool | Import layout preset from file |
| `ImportRenderPreset(path)` | Bool | Import render preset from file |
| `ExportRenderPreset(presetName, path)` | Bool | Export named render preset to file |
| `ImportBurnInPreset(path)` | Bool | Import burn-in preset from file |
| `ExportBurnInPreset(presetName, path)` | Bool | Export named burn-in preset to file |
| `Quit()` | None | Quit DaVinci Resolve |

---

## ProjectManager

| Method | Return | Description |
|---|---|---|
| `CreateProject(name)` | Project | Create a new project; `name` must be unique in the current folder |
| `DeleteProject(name)` | Bool | Delete project by name; must not be the currently open project |
| `LoadProject(name)` | Project | Load and return a project by name |
| `GetCurrentProject()` | Project | Returns the currently open project |
| `SaveProject()` | Bool | Save current project |
| `CloseProject(project)` | Bool | Close project **without** saving |
| `CreateFolder(name)` | Bool | Create a folder in the current database location |
| `GetProjectListInCurrentFolder()` | [string] | List project names in the current folder |
| `GetFolderListInCurrentFolder()` | [string] | List subfolder names in the current folder |
| `GotoRootFolder()` | Bool | Navigate to the root database folder |
| `GotoParentFolder()` | Bool | Navigate up one folder level |
| `OpenFolder(name)` | Bool | Open named subfolder |
| `ImportProject(filePath)` | Bool | Import a project from file |
| `ExportProject(name, filePath)` | Bool | Export named project to file |
| `RestoreProject(filePath)` | Bool | Restore project from a backup file |

---

## Project

| Method | Return | Description |
|---|---|---|
| `GetMediaPool()` | MediaPool | Returns the media pool |
| `GetTimelineCount()` | int | Number of timelines in project |
| `GetTimelineByIndex(idx)` | Timeline | Get timeline by 1-based index |
| `GetCurrentTimeline()` | Timeline | Returns the active timeline |
| `SetCurrentTimeline(timeline)` | Bool | Set the active timeline |
| `GetGallery()` | Gallery | Returns the gallery object |
| `GetName()` | string | Project name |
| `SetName(name)` | Bool | Rename the project |
| `GetPresetList()` | [dict] | List available presets |
| `SetPreset(name)` | Bool | Apply a named preset |
| `GetRenderJobList()` | [dict] | List all render jobs |
| `GetRenderPresetList()` | [dict] | List available render presets |
| `StartRendering(idx1, idx2, ...)` | Bool | Start rendering specific job indices |
| `StartRendering([idxs], isInteractiveMode=False)` | Bool | Start rendering a list of job indices |
| `StartRendering(isInteractiveMode=False)` | Bool | Start all queued render jobs |
| `StopRendering()` | None | Stop all active rendering |
| `IsRenderingInProgress()` | Bool | Returns `True` if rendering is active |
| `AddRenderJob()` | string | Add current settings as a render job; returns job ID |
| `DeleteRenderJob(jobId)` | Bool | Delete a render job by ID |
| `DeleteAllRenderJobs()` | Bool | Clear the entire render queue |
| `LoadRenderPreset(name)` | Bool | Load a render preset by name |
| `SaveAsNewRenderPreset(name)` | Bool | Save current render settings as a new preset |
| `SetRenderSettings(settings)` | Bool | Apply render settings from a dict (see keys below) |
| `GetRenderJobStatus(idx)` | dict | Returns job status and completion percentage |
| `GetSetting(name)` | string | Get a project setting value; call with no args to get all settings as dict |
| `SetSetting(name, value)` | Bool | Set a project setting |
| `GetRenderFormats()` | dict | Available render formats as `{format: extension}` |
| `GetRenderCodecs(format)` | dict | Available codecs for a given format |
| `GetCurrentRenderFormatAndCodec()` | dict | Current render format and codec |
| `SetCurrentRenderFormatAndCodec(format, codec)` | Bool | Set the render format and codec |
| `GetColorGroupsList()` | [ColorGroup] | List all color groups |
| `AddColorGroup(name)` | ColorGroup | Create a new color group |
| `DeleteColorGroup(group)` | Bool | Delete a color group |
| `RefreshLUTList()` | Bool | Refresh the list of available LUTs |

### Render Settings Keys

| Key | Type | Description |
|---|---|---|
| `SelectAllFrames` | bool | Render all frames when `True` |
| `MarkIn` | int | Start frame for render range |
| `MarkOut` | int | End frame for render range |
| `TargetDir` | string | Output directory path |
| `CustomName` | string | Output filename |
| `ExportVideo` | bool | Include video in output |
| `ExportAudio` | bool | Include audio in output |

### Common Project Settings

Call `project.GetSetting()` with no arguments to discover all available settings.

| Setting | Values | Description |
|---|---|---|
| `timelineFrameRate` | `"23.976"`, `"24"`, `"25"`, `"29.97"`, `"30"`, `"48"`, `"50"`, `"59.94"`, `"60"` (append `"DF"` for drop frame) | Timeline frame rate |
| `timelineResolutionWidth` | string integer | Width in pixels |
| `timelineResolutionHeight` | string integer | Height in pixels |
| `colorScienceMode` | `"davinciYRGB"`, `"davinciYRGBColorManaged"`, `"acescct"` | Color pipeline mode |
| `superScale` | `0`-`4` (0=Auto, 1=None, 2=2x, 3=3x, 4=4x) | Super Scale upscaling multiplier |

---

## MediaStorage

| Method | Return | Description |
|---|---|---|
| `GetMountedVolumeList()` | [string] | List paths of all mounted volumes |
| `GetSubFolderList(path)` | [string] | List subfolders at `path` |
| `GetFileList(path)` | [string] | List files at `path` (may be consolidated) |
| `RevealInStorage(path)` | None | Show `path` in the Media Storage panel |
| `AddItemListToMediaPool(item1, ...)` | [MediaPoolItem] | Import files to the media pool |
| `AddItemListToMediaPool([items])` | [MediaPoolItem] | Import a list of file paths to the media pool |

---

## MediaPool

| Method | Return | Description |
|---|---|---|
| `GetRootFolder()` | Folder | Returns the root media pool folder |
| `AddSubFolder(folder, name)` | Folder | Create a subfolder inside `folder` |
| `CreateEmptyTimeline(name)` | Timeline | Create a new empty timeline |
| `AppendToTimeline(clip1, ...)` | [TimelineItem] | Append clips to the current timeline |
| `AppendToTimeline([clips])` | [TimelineItem] | Append a list of `MediaPoolItem` objects |
| `AppendToTimeline([{clipInfo}])` | [TimelineItem] | Append clips with explicit in/out points |
| `CreateTimelineFromClips(name, clip1, ...)` | Timeline | Create a timeline from clips |
| `CreateTimelineFromClips(name, [clips])` | Timeline | Array variant |
| `CreateTimelineFromClips(name, [{clipInfo}])` | Timeline | With explicit in/out points |
| `ImportTimelineFromFile(path)` | Timeline | Import timeline from AAF, EDL, or XML |
| `GetCurrentFolder()` | Folder | Returns the currently selected folder |
| `SetCurrentFolder(folder)` | Bool | Set the currently selected folder |
| `DeleteClips([clips])` | Bool | Delete a list of clips |
| `DeleteFolders([folders])` | Bool | Delete a list of folders |
| `MoveClips([clips], targetFolder)` | Bool | Move clips to a target folder |
| `MoveFolders([folders], targetFolder)` | Bool | Move folders to a target folder |

### clipInfo Dictionary

Used with `AppendToTimeline` and `CreateTimelineFromClips`:

```python
{
    "mediaPoolItem": <MediaPoolItem>,
    "startFrame": int,
    "endFrame": int
}
```

---

## Folder

| Method | Return | Description |
|---|---|---|
| `GetClipList()` | [MediaPoolItem] | All clips in this folder |
| `GetName()` | string | Folder name |
| `GetSubFolderList()` | [Folder] | All direct subfolders |

---

## MediaPoolItem

| Method | Return | Description |
|---|---|---|
| `GetMetadata(type)` | dict / string | Get a metadata field; call with no args to get all metadata as dict |
| `SetMetadata(type, value)` | Bool | Set a metadata field |
| `SetMetadata({type: value, ...})` | Bool | Set multiple metadata fields at once |
| `GetMediaId()` | string | Unique media ID |
| `AddMarker(frameId, color, name, note, duration)` | Bool | Add a marker |
| `GetMarkers()` | dict | All markers keyed by frame position |
| `DeleteMarkersByColor(color)` | Bool | Delete markers by color; use `"All"` to delete all |
| `DeleteMarkerAtFrame(frame)` | Bool | Delete marker at specific frame |
| `AddFlag(color)` | Bool | Add a flag with the given color |
| `GetFlagList()` | [string] | List of flag colors on this item |
| `ClearFlags(color)` | Bool | Clear flags by color; use `"All"` to clear all |
| `GetClipColor()` | string | Current clip color |
| `SetClipColor(color)` | Bool | Set clip color |
| `ClearClipColor()` | Bool | Remove clip color |
| `GetClipProperty(name)` | dict / string | Get a clip property; call with no args to get all as dict |
| `SetClipProperty(name, value)` | Bool | Set a clip property |
| `LinkProxyMedia(path)` | Bool | Link a proxy media file |
| `UnlinkProxyMedia()` | Bool | Remove linked proxy media |
| `ReplaceClip(path)` | Bool | Replace the clip's source media |
| `TranscribeAudio()` | string | Transcribe clip audio to text |
| `ClearTranscription()` | Bool | Clear existing audio transcription |
| `GetUniqueId()` | string | Unique identifier for this item |

---

## Timeline

| Method | Return | Description |
|---|---|---|
| `GetName()` | string | Timeline name |
| `SetName(name)` | Bool | Rename the timeline |
| `GetStartFrame()` | int | First frame number of the timeline |
| `GetEndFrame()` | int | Last frame number of the timeline |
| `GetTrackCount(trackType)` | int | Number of tracks of given type (`"video"`, `"audio"`, `"subtitle"`) |
| `GetItemListInTrack(trackType, idx)` | [TimelineItem] | All items on the given track (1-based index) |
| `AddMarker(frameId, color, name, note, duration)` | Bool | Add a timeline marker |
| `GetMarkers()` | dict | All markers keyed by frame position |
| `DeleteMarkersByColor(color)` | Bool | Delete markers by color |
| `DeleteMarkerAtFrame(frame)` | Bool | Delete marker at specific frame |
| `DeleteMarkerByCustomData(customData)` | Bool | Delete marker matching custom data string |
| `GetMarkerByCustomData(customData)` | dict | Find marker by custom data string |
| `ApplyGradeFromDRX(path, gradeMode, item1, ...)` | Bool | Apply DRX grade to items |
| `ApplyGradeFromDRX(path, gradeMode, [items])` | Bool | Array variant |
| `GetCurrentTimecode()` | string | Playhead timecode (Cut/Edit/Color/Deliver pages only) |
| `GetCurrentVideoItem()` | TimelineItem | Item under the playhead |
| `GetCurrentClipThumbnailImage()` | dict | Thumbnail as `{width, height, format, data}` where `data` is base64-encoded |
| `GetTrackName(trackType, idx)` | string | Name of a track (1-based index) |
| `SetTrackName(trackType, idx, name)` | Bool | Rename a track |
| `SetTrackEnable(trackType, idx, enabled)` | Bool | Enable or disable a track |
| `GetIsTrackEnabled(trackType, idx)` | Bool | Returns `True` if track is enabled |
| `SetTrackLock(trackType, idx, locked)` | Bool | Lock or unlock a track |
| `GetIsTrackLocked(trackType, idx)` | Bool | Returns `True` if track is locked |
| `InsertGeneratorIntoTimeline(name)` | TimelineItem | Insert a named generator at playhead |
| `InsertFusionGeneratorIntoTimeline(name)` | TimelineItem | Insert a Fusion generator at playhead |
| `InsertTitleIntoTimeline(name)` | TimelineItem | Insert a named title at playhead |
| `InsertFusionTitleIntoTimeline(name)` | TimelineItem | Insert a Fusion title at playhead |
| `GrabStill()` | GalleryStill | Capture a still from the current frame |
| `GrabAllStills(stillFrameSource)` | [GalleryStill] | Capture stills from all clips |
| `GetUniqueId()` | string | Unique ID for this timeline |
| `CreateCompoundClip([timelineItems], {clipInfo})` | TimelineItem | Create a compound clip from items |
| `CreateFusionClip([timelineItems])` | TimelineItem | Create a Fusion clip from items |
| `ImportIntoTimeline(filePath, {importOptions})` | Bool | Import AAF/EDL/XML into this timeline |
| `Export(filePath, exportType, exportSubType)` | Bool | Export timeline (see export types below) |

### Grade Modes for ApplyGradeFromDRX

| Value | Alignment |
|---|---|
| `0` | No keyframes |
| `1` | Source Timecode aligned |
| `2` | Start Frames aligned |

### Marker Format

Markers are returned as a dict keyed by frame position (float):

```python
{
    96.0: {
        "color": "Green",
        "duration": 1.0,
        "note": "",
        "name": "Marker 1",
        "customData": ""
    }
}
```

---

## TimelineItem

| Method | Return | Description |
|---|---|---|
| `GetName()` | string | Item name |
| `GetDuration()` | int | Duration in frames |
| `GetStart()` | int | Start frame position in the timeline |
| `GetEnd()` | int | End frame position in the timeline |
| `GetLeftOffset()` | int | Maximum left extension (handles) |
| `GetRightOffset()` | int | Maximum right extension (handles) |
| `SetProperty(key, value)` | Bool | Set an item property |
| `GetProperty(key)` | value | Get a property value; call with no args for all as dict |
| `GetFusionCompCount()` | int | Number of Fusion compositions |
| `GetFusionCompByIndex(idx)` | fusionComp | Get Fusion comp by 1-based index |
| `GetFusionCompNameList()` | [string] | Names of all Fusion comps |
| `GetFusionCompByName(name)` | fusionComp | Get Fusion comp by name |
| `AddFusionComp()` | fusionComp | Add a new Fusion composition |
| `ImportFusionComp(path)` | fusionComp | Import a Fusion comp from file |
| `ExportFusionComp(path, idx)` | Bool | Export Fusion comp by index to file |
| `DeleteFusionCompByName(name)` | Bool | Delete a Fusion comp by name |
| `LoadFusionCompByName(name)` | fusionComp | Load (activate) a Fusion comp by name |
| `RenameFusionCompByName(old, new)` | Bool | Rename a Fusion comp |
| `AddMarker(frameId, color, name, note, duration)` | Bool | Add a marker to this item |
| `GetMarkers()` | dict | All markers on this item |
| `DeleteMarkersByColor(color)` | Bool | Delete markers by color |
| `DeleteMarkerAtFrame(frame)` | Bool | Delete marker at frame |
| `AddFlag(color)` | Bool | Add a flag |
| `GetFlagList()` | [string] | Flag colors on this item |
| `ClearFlags(color)` | Bool | Clear flags; use `"All"` for all |
| `GetClipColor()` | string | Clip color |
| `SetClipColor(color)` | Bool | Set clip color |
| `ClearClipColor()` | Bool | Remove clip color |
| `AddVersion(name, type)` | Bool | Add a version (`type`: `0`=local, `1`=remote) |
| `DeleteVersionByName(name, type)` | Bool | Delete a version by name |
| `LoadVersionByName(name, type)` | Bool | Load (activate) a version by name |
| `RenameVersionByName(old, new, type)` | Bool | Rename a version |
| `GetVersionNameList(type)` | [string] | List version names |
| `GetMediaPoolItem()` | MediaPoolItem | Source `MediaPoolItem` for this clip |
| `SetLUT(nodeIndex, lutPath)` | Bool | Apply LUT to node (1-based index) |
| `GetLUT(idx)` | string | Get LUT path on node (1-based index) |
| `SetCDL(cdlMap)` | Bool | Set CDL values (see format below) |
| `GetNodeGraph()` | Graph | Get the color node graph |
| `GetNumNodes()` | int | Number of color nodes |
| `GetNodeLabel(idx)` | string | Label of a node (1-based index) |
| `AddTake(mediaPoolItem, start, end)` | Bool | Add a take to this item |
| `GetSelectedTakeIndex()` | int | Index of current take; `0` if not in take selector mode |
| `GetTakesCount()` | int | Total number of takes |
| `GetTakeByIndex(idx)` | dict | Take info by 1-based index |
| `DeleteTakeByIndex(idx)` | Bool | Delete take by index |
| `SelectTakeByIndex(idx)` | Bool | Select a take |
| `FinalizeTake()` | Bool | Finalize the current take selection |
| `CopyGrades([targets])` | Bool | Copy this item's grade to target `TimelineItem` list |
| `GetStereoConvergenceValues()` | dict | Stereo convergence keyframes |
| `UpdateSidecar()` | Bool | Update the sidecar file for this item |

### CDL Map Format

```python
{
    "NodeIndex": "1",
    "Slope": "0.5 0.4 0.2",
    "Offset": "0.4 0.3 0.2",
    "Power": "0.6 0.7 0.8",
    "Saturation": "0.65"
}
```

### TimelineItem Properties (SetProperty/GetProperty)

| Property | Type | Description |
|---|---|---|
| `Pan` | float | Horizontal position |
| `Tilt` | float | Vertical position |
| `ZoomX` | float | Horizontal zoom |
| `ZoomY` | float | Vertical zoom |
| `ZoomGang` | bool | Gang X and Y zoom together |
| `Rotation` | float | Rotation angle in degrees |
| `AnchorPointX` | float | Anchor point X |
| `AnchorPointY` | float | Anchor point Y |
| `Pitch` | float | 3D pitch |
| `Yaw` | float | 3D yaw |
| `FlipX` | bool | Horizontal flip |
| `FlipY` | bool | Vertical flip |
| `CropLeft` | float | Left crop amount |
| `CropRight` | float | Right crop amount |
| `CropTop` | float | Top crop amount |
| `CropBottom` | float | Bottom crop amount |
| `CropSoftness` | float | Crop edge softness |
| `CropRetain` | bool | Retain crop on resize |
| `Opacity` | float | Opacity (0-100) |
| `CompositeMode` | string | Blend/composite mode name |
| `Speed` | float | Playback speed percentage |
| `RetimeProcess` | int | `0`=NearestFrame, `1`=FrameBlend, `2`=OpticalFlow |

---

## Gallery

| Method | Return | Description |
|---|---|---|
| `GetAlbumName(album)` | string | Name of a `GalleryStillAlbum` |
| `SetAlbumName(album, name)` | Bool | Rename an album |
| `GetCurrentStillAlbum()` | GalleryStillAlbum | Currently active album |
| `SetCurrentStillAlbum(album)` | Bool | Set the active album |
| `GetGalleryStillAlbums()` | [GalleryStillAlbum] | All albums in the gallery |

---

## GalleryStillAlbum

| Method | Return | Description |
|---|---|---|
| `GetStills()` | [GalleryStill] | All stills in this album |
| `GetLabel(still)` | string | Label of a `GalleryStill` |
| `SetLabel(still, label)` | Bool | Set label on a `GalleryStill` |
| `ExportStills([stills], path, prefix, format)` | Bool | Export stills to a directory |
| `DeleteStills([stills])` | Bool | Delete stills from album |

---

## Enumerated Values

### Page Names

| Value |
|---|
| `"media"` |
| `"cut"` |
| `"edit"` |
| `"fusion"` |
| `"color"` |
| `"fairlight"` |
| `"deliver"` |

### Track Types

| Value | Description |
|---|---|
| `"video"` | Video tracks |
| `"audio"` | Audio tracks |
| `"subtitle"` | Subtitle tracks |

### Marker, Flag, and Clip Colors

`Blue`, `Cyan`, `Green`, `Yellow`, `Red`, `Pink`, `Purple`, `Fuchsia`, `Rose`, `Lavender`, `Sky`, `Mint`, `Lemon`, `Sand`, `Cocoa`, `Cream`

Use `"All"` in `DeleteMarkersByColor()` and `ClearFlags()` to target all colors.

### Composite Modes

`Normal`, `Add`, `Subtract`, `Difference`, `Multiply`, `Screen`, `Overlay`, `Hardlight`, `Softlight`, `Darken`, `Lighten`, `ColorDodge`, `ColorBurn`, `Exclusion`, `Hue`, `Saturation`, `Color`, `Luminosity`

### Timeline Export Types

| Type | Notes |
|---|---|
| `AAF` | Advanced Authoring Format |
| `EDL` | Edit Decision List |
| `XML` | FCP 7 XML |
| `FCPXML` | Final Cut Pro X XML |
