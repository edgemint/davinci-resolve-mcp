# DaVinci Resolve Workflow Recipes

Practical recipes for operating DaVinci Resolve via MCP tools and `execute_script`. Each recipe shows the MCP tool sequence and/or the equivalent Python code.

**Convention:** MCP tool calls are shown as `tool_name(param=value)`. Python code runs via `execute_script` and assumes `resolve`, `project`, `media_pool`, and `timeline` are already bound (the server injects these automatically).

---

## Table of Contents

1. [Project Setup from Scratch](#1-project-setup-from-scratch)
2. [Media Import and Organization](#2-media-import-and-organization)
3. [Timeline Assembly](#3-timeline-assembly)
4. [Color Grading Pipeline](#4-color-grading-pipeline)
5. [Render Pipeline](#5-render-pipeline)
6. [Batch Operations](#6-batch-operations)
7. [Media Pool Traversal (Recursive)](#7-media-pool-traversal-recursive)
8. [Marker Workflows](#8-marker-workflows)
9. [Audio Sync Workflow](#9-audio-sync-workflow)
10. [Proxy Workflow](#10-proxy-workflow)
11. [Multi-Timeline Render](#11-multi-timeline-render)
12. [DRX Grade Application](#12-drx-grade-application)
13. [Clip Metadata Inspection](#13-clip-metadata-inspection)
14. [Color Version A/B Testing](#14-color-version-ab-testing)
15. [LUT Installation and Application](#15-lut-installation-and-application)

---

## 1. Project Setup from Scratch

**When to use:** Starting a new project and configuring it to match a specific delivery spec before any media is imported.

### MCP Tool Sequence

```
create_project(name="ProjectName")
set_project_setting(setting_name="timelineFrameRate", setting_value="24")
set_project_setting(setting_name="timelineResolutionWidth", setting_value="1920")
set_project_setting(setting_name="timelineResolutionHeight", setting_value="1080")
```

### execute_script Equivalent

```python
pm = resolve.GetProjectManager()
proj = pm.CreateProject("ProjectName")
proj.SetSetting("timelineFrameRate", "24")
proj.SetSetting("timelineResolutionWidth", "1920")
proj.SetSetting("timelineResolutionHeight", "1080")
```

### Notes

- All `SetSetting` values are strings, even numeric ones.
- Common frame rates: `"23.976"`, `"24"`, `"25"`, `"29.97"`, `"30"`, `"59.94"`, `"60"`.
- Resolution settings must be set together — setting width without height can produce unexpected results.
- `set_project_setting` via MCP operates on the currently open project. Call `create_project` first, which also opens the new project.

---

## 2. Media Import and Organization

**When to use:** Bringing footage into a project and keeping the Media Pool organized by clip type, shoot day, or scene.

### MCP Tool Sequence

```
import_media(file_path="/path/to/clip.mp4")
create_bin(name="A-Cam")
create_bin(name="Audio")
move_media_to_bin(clip_name="clip.mp4", bin_name="A-Cam")
```

### execute_script for Bulk Import

```python
import os

media_storage = resolve.GetMediaStorage()
folder_path = "/footage/day01"

# Import all files in a folder
clips = media_storage.AddItemListToMediaPool([folder_path])
print(f"Imported {len(clips)} clips")
```

### execute_script: Build a Clip Index for Lookup by Name

```python
root = media_pool.GetRootFolder()

def index_clips(folder, index=None):
    if index is None:
        index = {}
    for clip in (folder.GetClipList() or []):
        name = clip.GetClipProperty("File Name") or clip.GetName()
        index[name] = clip
    for sub in (folder.GetSubFolderList() or []):
        index_clips(sub, index)
    return index

clip_index = index_clips(root)
# Access any clip by filename: clip_index["interview_01.mp4"]
```

### Notes

- `import_media` imports one file at a time. For large ingest jobs, use `execute_script` with `AddItemListToMediaPool`.
- `AddItemListToMediaPool` accepts a list of file paths or folder paths. Folder paths import all recognized media files within.
- `move_media_to_bin` matches by clip name, not file path. If two clips share a name, the first match wins.
- Create bins before moving clips to them.

---

## 3. Timeline Assembly

**When to use:** Building an edit from imported media, either from scratch or by appending clips in sequence.

### MCP Tool Sequence

```
create_timeline(name="Main Edit")
# -- or, for custom format --
create_empty_timeline(name="Main Edit", fps="24", width="1920", height="1080")

add_clip_to_timeline(clip_name="clip_01.mp4")
add_clip_to_timeline(clip_name="clip_02.mp4")
add_clip_to_timeline(clip_name="clip_03.mp4")
```

### execute_script for Subclip Insertion

```python
clip = clip_index["interview_01.mp4"]

clip_info = {
    "mediaPoolItem": clip,
    "startFrame": 0,
    "endFrame": 240,     # frame number, not timecode
    "trackIndex": 1,
    "recordFrame": 0
}

timeline.AppendToTimeline([clip_info])
```

### execute_script: Append Multiple Clips with In/Out Points

```python
clips_to_add = [
    {"mediaPoolItem": clip_index["A001.mp4"], "startFrame": 48,  "endFrame": 192},
    {"mediaPoolItem": clip_index["A002.mp4"], "startFrame": 0,   "endFrame": 300},
    {"mediaPoolItem": clip_index["A003.mp4"], "startFrame": 120, "endFrame": 480},
]

timeline.AppendToTimeline(clips_to_add)
```

### Notes

- `add_clip_to_timeline` appends to the end of the timeline. Order of calls is order of edit.
- There is no MCP tool to reposition clips after insertion. If order is wrong, rebuild the timeline.
- `create_empty_timeline` gives full control over format and does not inherit project settings. `create_timeline` inherits the current project settings.
- `AppendToTimeline` accepts a list, so a full assembly can be done in one call.
- `startFrame` and `endFrame` in `AppendToTimeline` are source clip frame numbers (0-indexed), not timecode values.

---

## 4. Color Grading Pipeline

**When to use:** Applying primary corrections, creative looks, and propagating grades across a timeline.

### MCP Tool Sequence

```
switch_page(page="color")
set_current_timeline(timeline_name="Main Edit")
add_node(node_type="serial")          # Node 1: Primary correction
set_color_wheel_param(wheel="lift", param="master", value=-0.03)
set_color_wheel_param(wheel="gain", param="master", value=1.05)
add_node(node_type="serial")          # Node 2: Creative LUT
apply_lut(lut_name="FilmLook.cube")
copy_grade(source_clip_index=1)       # Propagate to all clips
save_color_preset(preset_name="MyLook")
```

### execute_script: CDL-Based Grading Across All Clips

```python
items = timeline.GetItemListInTrack("video", 1)
for item in items:
    item.SetCDL({
        "NodeIndex": "1",
        "Slope":      "1.05 0.98 0.95",
        "Offset":     "-0.03 -0.02 0.01",
        "Power":      "0.95 0.97 1.0",
        "Saturation": "1.08"
    })
```

### Notes

- Nodes must be added before parameters can be set. `add_node` creates the node; subsequent `set_color_wheel_param` and `apply_lut` calls target the currently selected node.
- `SetCDL` values are space-separated strings for R, G, B channels. Single values apply to all channels.
- `copy_grade` copies from a source clip index (1-based) to all other clips. Use it after finishing the grade on clip 1.
- `save_color_preset` saves the current clip's grade as a reusable preset in the Color Presets gallery.
- LUT filenames passed to `apply_lut` must match exactly what appears in Resolve's LUT list — filename only, no path.

---

## 5. Render Pipeline

**When to use:** Exporting a finished timeline to a deliverable file.

### MCP Tool Sequence

```
switch_page(page="deliver")
add_to_render_queue(preset_name="H.264 Master")
start_render()
```

### execute_script for Full Control

```python
resolve.OpenPage("deliver")
project.LoadRenderPreset("YouTube 1080p")
project.SetCurrentRenderFormatAndCodec("mp4", "H264")
project.SetRenderSettings({
    "SelectAllFrames": True,
    "TargetDir":       "/output/path",
    "CustomName":      "final_render"
})
project.AddRenderJob()
project.StartRendering()

import time
while project.IsRenderingInProgress():
    time.sleep(1)
print("Render complete!")
```

### Notes

- `add_to_render_queue` via MCP uses a named preset. The preset must already exist in Resolve.
- `SetCurrentRenderFormatAndCodec` overrides the preset's format/codec. Call it after `LoadRenderPreset`.
- `TargetDir` must be an absolute path that already exists. Resolve will not create the directory.
- `CustomName` sets the output filename (without extension). If omitted, Resolve uses the timeline name.
- `IsRenderingInProgress()` returns `True` while rendering. Poll with a sleep interval to avoid busy-waiting.
- `execute_script` calls are non-blocking — the polling loop is essential if you need to take action after render completes.

---

## 6. Batch Operations

**When to use:** Applying the same operation to every clip in a timeline — grades, markers, clip colors, metadata.

### execute_script: Iterate All Clips Across All Video Tracks

```python
video_track_count = timeline.GetTrackCount("video")
all_clips = []

for track in range(1, video_track_count + 1):
    items = timeline.GetItemListInTrack("video", track)
    if items:
        all_clips.extend(items)

for clip in all_clips:
    print(f"{clip.GetName()}: {clip.GetStart()}-{clip.GetEnd()}")
```

### execute_script: Set Clip Color for All Clips

```python
for clip in all_clips:
    clip.SetClipColor("Orange")
```

### execute_script: Add Marker at Regular Intervals (Every 24 Frames)

```python
duration = timeline.GetEndFrame() - timeline.GetStartFrame()
interval = 24  # frames

for frame_offset in range(0, duration, interval):
    timeline.AddMarker(
        frame_offset,
        "Blue",
        "beat",
        "",
        1
    )
```

### MCP Tool Equivalent for Individual Markers

```
add_marker(frame_id=0, color="Blue", name="beat", note="", duration=1)
add_marker(frame_id=24, color="Blue", name="beat", note="", duration=1)
```

### Notes

- Track indices are 1-based. `range(1, count + 1)` is the correct iteration pattern.
- `GetItemListInTrack` returns `None` (not an empty list) if the track is empty. Always guard with `if items:`.
- `GetStart()` and `GetEnd()` return timeline frame numbers, not source clip frame numbers.
- Valid clip colors: `"Orange"`, `"Apricot"`, `"Yellow"`, `"Lime"`, `"Olive"`, `"Green"`, `"Teal"`, `"Navy"`, `"Blue"`, `"Purple"`, `"Violet"`, `"Pink"`, `"Tan"`, `"Beige"`, `"Brown"`, `"Chocolate"`.

---

## 7. Media Pool Traversal (Recursive)

**When to use:** Auditing all clips in a project, building a clip index, or applying operations to every clip regardless of bin structure.

### execute_script

```python
def process_folder(folder, indent=0):
    print(" " * indent + folder.GetName())
    for clip in (folder.GetClipList() or []):
        name = clip.GetClipProperty("File Name") or clip.GetName()
        print(" " * (indent + 2) + name)
    for sub in (folder.GetSubFolderList() or []):
        process_folder(sub, indent + 2)

process_folder(media_pool.GetRootFolder())
```

### execute_script: Collect All Clips into a Flat List

```python
def collect_all_clips(folder, result=None):
    if result is None:
        result = []
    for clip in (folder.GetClipList() or []):
        result.append(clip)
    for sub in (folder.GetSubFolderList() or []):
        collect_all_clips(sub, result)
    return result

all_media_clips = collect_all_clips(media_pool.GetRootFolder())
print(f"Total clips in project: {len(all_media_clips)}")
```

### Notes

- Both `GetClipList()` and `GetSubFolderList()` can return `None` on empty folders. Always use `or []` to avoid iteration errors.
- The root folder's `GetName()` returns `"Master"` by default.
- This is the correct pattern for building a project-wide clip index when clips are spread across multiple bins.

---

## 8. Marker Workflows

**When to use:** Marking scene changes, flagging review points, adding notes, or creating chapter markers for export.

### MCP Tool Sequence: Individual Markers

```
add_marker(frame_id=0,   color="Red",    name="Scene 1 Start", note="",          duration=1)
add_marker(frame_id=240, color="Yellow", name="Review",        note="Check cut", duration=1)
add_marker(frame_id=480, color="Green",  name="Scene 2 Start", note="",          duration=1)
```

### execute_script: Markers at Scene Changes from Clip Boundaries

```python
items = timeline.GetItemListInTrack("video", 1)
for item in items:
    start = item.GetStart()
    timeline.AddMarker(start, "Blue", item.GetName(), "", 1)
```

### execute_script: Markers Based on Clip Metadata (Flagged Clips)

```python
items = timeline.GetItemListInTrack("video", 1)
for item in items:
    clip = item.GetMediaPoolItem()
    if clip and clip.GetClipProperty("Good Take") == "true":
        timeline.AddMarker(item.GetStart(), "Green", "Good Take", "", 1)
```

### Notes

- `AddMarker(frameId, color, name, note, duration)` — all parameters required.
- `frameId` is a timeline frame number (not source frame, not timecode).
- Valid marker colors: `"Blue"`, `"Cyan"`, `"Green"`, `"Yellow"`, `"Red"`, `"Pink"`, `"Purple"`, `"Fuchsia"`, `"Rose"`, `"Lavender"`, `"Sky"`, `"Mint"`, `"Lemon"`, `"Sand"`, `"Cocoa"`, `"Cream"`.
- Adding a marker at a frame that already has one will fail silently. Delete existing markers with `timeline.DeleteMarkerAtFrame(frameId)` before re-adding if needed.

---

## 9. Audio Sync Workflow

**When to use:** Syncing dual-system audio (separate recorder) to video clips using waveform matching or timecode.

### MCP Tool Sequence

```
import_media(file_path="/footage/A001.mp4")
import_media(file_path="/audio/A001.wav")
create_bin(name="Synced")
auto_sync_audio(clip_name="A001.mp4", audio_clip_name="A001.wav", method="waveform")
move_media_to_bin(clip_name="A001.mp4", bin_name="Synced")
```

### Sync Methods

| Method | When to use |
|--------|-------------|
| `"waveform"` | Camera and recorder both captured audio; waveform correlation finds sync point |
| `"timecode"` | Both devices were jammed to the same timecode source |

### Notes

- `auto_sync_audio` modifies the video clip in the Media Pool, embedding a reference to the synced audio track.
- The resulting synced clip in the timeline will play the external audio instead of (or in addition to) the camera audio.
- Waveform sync requires some overlap of audio on both the video clip and the audio file — it will not work if the camera recorded no sound.
- For multi-clip sync jobs, consider using Resolve's built-in "Auto Sync Audio" in the Media Pool directly (right-click selection), which processes multiple clips at once.
- After syncing, organize into a dedicated bin to distinguish synced clips from raw originals.

---

## 10. Proxy Workflow

**When to use:** Editing with large/high-bitrate formats (8K RAW, ProRes 4444) on a system that cannot play them back smoothly in real time.

### MCP Tool Sequence: Enable Proxies

```
set_proxy_mode(mode="proxy")
set_proxy_quality(quality="Half")
link_proxy_media(clip_name="A001.mp4", proxy_path="/proxies/A001_proxy.mp4")
```

### MCP Tool Sequence: Finalize (Switch Back to Original)

```
set_proxy_mode(mode="off")
```

### Proxy Quality Options

| Value | Resolution |
|-------|-----------|
| `"Quarter"` | 1/4 of original |
| `"Half"` | 1/2 of original |
| `"ThreeQuarter"` | 3/4 of original |
| `"Original"` | Full resolution (defeats purpose of proxy) |

### Workflow Pattern

1. Ingest original media.
2. Generate proxy files externally (e.g., via DaVinci Resolve's own "Generate Proxy Media" or a transcoding tool), saving to a known folder.
3. `set_proxy_mode(mode="proxy")` to tell Resolve to use proxy files.
4. `set_proxy_quality` to set the resolution tier.
5. `link_proxy_media` for each clip to associate the proxy file.
6. Edit normally — Resolve plays the proxy files.
7. Before final render, `set_proxy_mode(mode="off")` to revert to originals.

### Notes

- Proxy files must match the source clip's frame count and frame rate exactly.
- `link_proxy_media` accepts an absolute path to the proxy file.
- The proxy mode setting is project-level, not clip-level.
- DaVinci Resolve can also generate optimized media (DNxHR/ProRes intermediates) via `generate_optimized_media` — a different workflow for the same goal of smooth playback.

---

## 11. Multi-Timeline Render

**When to use:** Exporting every timeline in a project to separate files in one operation (e.g., multiple episodes, multiple deliverable versions).

### execute_script

```python
resolve.OpenPage("deliver")
count = project.GetTimelineCount()

for i in range(1, count + 1):
    tl = project.GetTimelineByIndex(i)
    project.SetCurrentTimeline(tl)
    project.LoadRenderPreset("YouTube 1080p")
    project.SetRenderSettings({
        "SelectAllFrames": True,
        "TargetDir":       "/output",
        "CustomName":      tl.GetName()
    })
    project.AddRenderJob()

project.StartRendering()

import time
while project.IsRenderingInProgress():
    time.sleep(1)
print(f"Rendered {count} timelines.")
```

### Notes

- `GetTimelineByIndex` is 1-based.
- `AddRenderJob` queues one job per call. All jobs are submitted before `StartRendering()` is called.
- Each job uses `tl.GetName()` as the output filename, so ensure timeline names are unique and filesystem-safe (no slashes, colons, or other invalid characters).
- `TargetDir` must exist. Pre-create it with `os.makedirs` if needed (standard `os` module is available in `execute_script`).
- `SetCurrentTimeline` must be called before `AddRenderJob` so that Resolve knows which timeline the job refers to.

---

## 12. DRX Grade Application

**When to use:** Applying a saved DaVinci Resolve grade (`.drx` file) exported from one project to clips in another.

### execute_script

```python
resolve.OpenPage("color")
items = timeline.GetItemListInTrack("video", 1)

# Mode 0 = no keyframes (apply grade as-is)
# Mode 1 = use source timecode to match frames
# Mode 2 = use start frames
timeline.ApplyGradeFromDRX("/path/to/grade.drx", 0, items)
```

### DRX Application Modes

| Mode | Behavior |
|------|----------|
| `0` | Apply grade without keyframes — the entire grade is applied flat to each clip |
| `1` | Match by source timecode — keyframes align to the original source timecode |
| `2` | Match by start frames — keyframes align to the clip's start frame |

### Notes

- The `.drx` file is exported from Resolve's Color page via the Stills gallery or by right-clicking a grade.
- `ApplyGradeFromDRX` can accept a single clip or a list of clips as the third argument.
- The grade is applied to the clips' node graph, replacing any existing grade.
- Must be on the Color page (`resolve.OpenPage("color")`) for grade operations to work correctly.
- The path to the `.drx` file must be an absolute path accessible to the machine running Resolve.

---

## 13. Clip Metadata Inspection

**When to use:** Auditing footage before an edit — verifying codecs, resolutions, frame rates, and durations across all clips in a project.

### execute_script

```python
root = media_pool.GetRootFolder()

for clip in (root.GetClipList() or []):
    props = clip.GetClipProperty()
    print(f"{props.get('File Name', 'unknown')}")
    print(f"  Codec:      {props.get('Video Codec', 'N/A')}")
    print(f"  Resolution: {props.get('Resolution', 'N/A')}")
    print(f"  FPS:        {props.get('FPS', 'N/A')}")
    print(f"  Duration:   {props.get('Duration', 'N/A')}")
```

### execute_script: Full Project Audit with Recursive Traversal

```python
def audit_clips(folder, results=None):
    if results is None:
        results = []
    for clip in (folder.GetClipList() or []):
        props = clip.GetClipProperty()
        results.append({
            "name":       props.get("File Name", clip.GetName()),
            "codec":      props.get("Video Codec", "N/A"),
            "resolution": props.get("Resolution", "N/A"),
            "fps":        props.get("FPS", "N/A"),
            "duration":   props.get("Duration", "N/A"),
        })
    for sub in (folder.GetSubFolderList() or []):
        audit_clips(sub, results)
    return results

audit = audit_clips(media_pool.GetRootFolder())
for entry in audit:
    print(f"{entry['name']}: {entry['resolution']} @ {entry['fps']} fps, {entry['codec']}, {entry['duration']}")
```

### Common Property Keys

| Key | Description |
|-----|-------------|
| `"File Name"` | Filename without path |
| `"File Path"` | Absolute file path |
| `"Video Codec"` | Codec name (e.g., `"H.264"`, `"BRAW"`) |
| `"Resolution"` | `"1920x1080"` format |
| `"FPS"` | Frame rate as string |
| `"Duration"` | Duration in `HH:MM:SS:FF` format |
| `"Bit Depth"` | `"8"`, `"10"`, `"12"` |
| `"Start TC"` | Start timecode |

### Notes

- `GetClipProperty()` with no argument returns a dict of all available properties.
- `GetClipProperty("key")` with a key returns just that value as a string.
- Properties vary by clip type (video, audio, still). Always use `.get()` with a fallback.
- Audio-only clips will not have video codec or resolution properties.

---

## 14. Color Version A/B Testing

**When to use:** Creating and comparing multiple color treatments on the same clip without losing any version.

### execute_script

```python
item = timeline.GetItemListInTrack("video", 1)[0]

# Create and set up Look A
item.AddVersion("Look_A", 0)             # 0 = local version
item.LoadVersionByName("Look_A", 0)
item.SetCDL({
    "NodeIndex":  "1",
    "Slope":      "1.1 1.0 0.9",
    "Offset":     "0 0 0",
    "Power":      "1 1 1",
    "Saturation": "1.1"
})

# Create and set up Look B
item.AddVersion("Look_B", 0)
item.LoadVersionByName("Look_B", 0)
item.SetLUT(1, "FilmLook.cube")

# Switch between versions for comparison
item.LoadVersionByName("Look_A", 0)
item.LoadVersionByName("Look_B", 0)
```

### Version Type Parameter

| Value | Type |
|-------|------|
| `0` | Local (per-clip, stored in the project) |
| `1` | Remote (shared across timelines) |

### Notes

- `AddVersion` creates a new, empty grade version. Any subsequent grade operations apply to the currently loaded version.
- `LoadVersionByName` switches the active grade version on the clip. The clip immediately displays that version on the Viewer.
- Version names must be unique per clip per type (local/remote).
- Versions persist in the project — switching back and forth does not alter the stored grades.
- `SetLUT(nodeIndex, lutName)` — node index is 1-based; `lutName` is the filename only (no path), matching what appears in Resolve's LUT list.
- This pattern is the programmatic equivalent of the Color page's "Versions" panel.

---

## 15. LUT Installation and Application

**When to use:** Adding new `.cube` or `.3dl` LUT files to Resolve's LUT library and applying them to clips.

### LUT Master Directories

| Platform | Path |
|----------|------|
| macOS | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/` |
| Windows | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\` |
| Linux | `/home/resolve/LUT/` |

### execute_script: Apply After Manual Installation

```python
# Step 1: Copy the LUT file to the master directory OUTSIDE of Resolve
# (shutil is blocked in execute_script — do this via OS file manager or separate script)

# Step 2: Refresh Resolve's LUT list
project.RefreshLUTList()

# Step 3: Apply by filename only (no path)
item = timeline.GetItemListInTrack("video", 1)[0]
item.SetLUT(1, "MyLook.cube")
```

### execute_script: Apply LUT to All Clips on Track 1

```python
project.RefreshLUTList()
items = timeline.GetItemListInTrack("video", 1)
for item in items:
    item.SetLUT(1, "MyLook.cube")
```

### Notes

- `shutil` is blocked in `execute_script`. LUT files must be copied to the master directory using an external tool, script, or OS file manager — not from within Resolve's Python environment.
- After copying, `project.RefreshLUTList()` is required before the new LUT name becomes available to `SetLUT`.
- `SetLUT(nodeIndex, lutName)` — the `lutName` is the filename only (e.g., `"MyLook.cube"`), not the full path. Resolve resolves it against the LUT search paths.
- Subdirectories within the LUT folder are supported. If the LUT is in a subfolder, use a relative path from the LUT root: `item.SetLUT(1, "Creative/MyLook.cube")`.
- The node at `nodeIndex` must exist before `SetLUT` can target it. Add nodes first with `add_node` (MCP) or by scripting node graph operations.
- LUT changes take effect immediately on the Color page viewer but require a render to appear in the exported file.
