# DaVinci Resolve Color Grading Reference

Reference for programmatic color grading via MCP tools and `execute_script`. Covers CDL values, LUT workflows, DRX templates, color presets, and practical grading patterns.

## Table of Contents

1. [CDL (Color Decision List) Reference](#cdl-color-decision-list-reference)
2. [Color Wheel Operations via MCP](#color-wheel-operations-via-mcp)
3. [LUT Workflow](#lut-workflow)
4. [DRX Templates](#drx-templates)
5. [Color Version Management](#color-version-management)
6. [Color Presets via MCP](#color-presets-via-mcp)
7. [Color Science Setup](#color-science-setup)
8. [Batch Grading Patterns](#batch-grading-patterns)

---

## CDL (Color Decision List) Reference

CDL is the primary method for programmatic color adjustment. All parameters are applied per node on the active timeline item.

```python
item.SetCDL({
    "NodeIndex": "1",          # 1-based string
    "Slope": "R G B",          # Gain/highlights (space-separated)
    "Offset": "R G B",         # Lift/shadows
    "Power": "R G B",          # Gamma/midtones
    "Saturation": "value"      # Overall saturation
})
```

### CDL Parameter Ranges

| Parameter | Neutral | Range | Effect |
|---|---|---|---|
| Slope | 1.0 | 0.0 – ~4.0 | Gain/highlights. >1 = brighter, <1 = darker |
| Offset | 0.0 | -1.0 – 1.0 | Lift/shadows. Negative = darker shadows |
| Power | 1.0 | 0.0 – ~4.0 | Gamma/midtones. **INVERSE**: <1 = brighter, >1 = darker |
| Saturation | 1.0 | 0.0 – ~4.0 | 0 = monochrome, >1 = more saturated |

> **Power is inverse**: unlike Slope, a Power value below 1.0 lifts midtones (brighter), above 1.0 pulls them down (darker).

### Cinematic CDL Presets

#### Netflix Drama
```python
{"NodeIndex": "1", "Slope": "1.05 0.98 0.95", "Offset": "-0.03 -0.02 0.01", "Power": "0.95 0.97 1.0", "Saturation": "1.08"}
```
Slightly warm highlights, cool shadow lift, subtle desaturation of blues. Clean cinematic look suitable for scripted drama.

#### Teal & Orange
```python
{"NodeIndex": "1", "Slope": "1.1 0.98 0.92", "Offset": "0.02 0.0 0.05", "Power": "0.9 0.95 1.05", "Saturation": "1.2"}
```
Hollywood blockbuster look. Warm skin tones pushed against cool-teal backgrounds. High contrast with boosted saturation.

#### Bleach Bypass
```python
{"NodeIndex": "1", "Slope": "1.1 1.1 1.1", "Offset": "0.0 0.0 0.0", "Power": "0.85 0.85 0.85", "Saturation": "0.5"}
```
Desaturated, high-contrast, silvery look. Emulates the silver-retention film process. Suited to war films and gritty drama.

#### Vintage Film
```python
{"NodeIndex": "1", "Slope": "1.08 1.0 0.88", "Offset": "0.05 0.02 -0.02", "Power": "0.92 0.95 1.05", "Saturation": "0.85"}
```
Warm, slightly faded. Lifted shadows with reduced saturation and a slight yellow-green cast in highlights. Period and nostalgic looks.

#### Kodak 5219 (500T)
```python
{"NodeIndex": "1", "Slope": "1.06 1.0 0.94", "Offset": "0.01 0.0 0.02", "Power": "0.98 1.0 1.02", "Saturation": "0.95"}
```
Subtle warm tone emulating Kodak Vision3 500T film stock. Slightly warm highlights, mild blue in shadows. Closest to a neutral film emulation.

#### Music Video
```python
{"NodeIndex": "1", "Slope": "1.15 1.05 1.15", "Offset": "0.0 -0.02 0.02", "Power": "0.85 0.9 0.85", "Saturation": "1.3"}
```
High contrast, punchy colors, lifted highlights. Aggressive, commercial look with visible color punch.

#### Documentary
```python
{"NodeIndex": "1", "Slope": "1.02 1.0 0.98", "Offset": "0.01 0.0 -0.01", "Power": "0.98 1.0 1.0", "Saturation": "0.92"}
```
Natural, slightly warm, minimal intervention. Preserves realistic skin tones and environment colors. Slightly reduced saturation for authenticity.

#### ARRI ALEXA Emulation
```python
{"NodeIndex": "1", "Slope": "1.04 1.0 0.96", "Offset": "0.02 0.01 0.0", "Power": "0.96 0.98 1.0", "Saturation": "0.98"}
```
Clean, slightly warm, wide dynamic range feel. Emulates the ALEXA's characteristic gentle highlight rolloff and slightly warm base.

---

## Color Wheel Operations via MCP

Use the `set_color_wheel_param` MCP tool for direct wheel adjustments without scripting.

```
set_color_wheel_param(wheel="lift", param="red", value=0.05)
```

### Parameters

- `wheel`: `"lift"` (shadows), `"gamma"` (midtones), `"gain"` (highlights), `"offset"` (overall shift)
- `param`: `"red"`, `"green"`, `"blue"`, `"master"` (luminance only)
- `value`: float, typically -1.0 to 1.0 for color channels; wider range for master

### Common Adjustments

| Look | Tool Call |
|---|---|
| Warm shadows | `lift red +0.05`, `lift blue -0.05` |
| Cool highlights | `gain blue +0.03`, `gain red -0.02` |
| Increase contrast | `lift master -0.05`, `gain master +0.1` |
| Warm overall | `offset red +0.03`, `offset blue -0.02` |
| Desaturate shadows | Use CDL via `execute_script` (wheel has no saturation per-zone) |

> **Note**: Color wheel operations affect the currently selected clip and node in the Color page. Navigate to the Color page first if using `execute_script`.

---

## LUT Workflow

### Applying LUTs via MCP

```
apply_lut(lut_path="MyLook.cube", node_index=2)
```

### LUT Application Rules

1. Supported formats: `.cube`, `.3dl`, `.lut`, `.mga`
2. LUTs in subdirectories are **not** recognized — must be placed directly in the master LUT directory
3. Use **filename only** (no full path) after placing the file in the master directory
4. Always call `RefreshLUTList()` after installing new LUTs (requires `execute_script`)
5. Node index is 1-based

### Refreshing the LUT List After Installation

```python
resolve = bmd.scriptapp("Resolve")
projectManager = resolve.GetProjectManager()
project = projectManager.GetCurrentProject()
project.RefreshLUTList()
```

### Master LUT Directories

| Platform | Path |
|---|---|
| macOS | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT` |
| Windows | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT` |
| Linux | `/opt/resolve/LUT` |

### LUT Export

```
export_lut(lut_format="Cube", lut_size="33Point", export_path="/path/to/output.cube")
```

| Parameter | Options |
|---|---|
| `lut_format` | `Cube`, `Davinci`, `3dl`, `Panasonic` |
| `lut_size` | `17Point`, `33Point`, `65Point` |

Use 33Point for general delivery; 65Point for precision work; 17Point only when file size is a constraint.

---

## DRX Templates

DRX (DaVinci Resolve Exchange) files store complete node structures with grades. Because the API cannot add nodes programmatically in most contexts, DRX is the primary method for applying multi-node grade structures to clips.

### Creating DRX Templates (Manual Step)

1. Build the node structure in the Resolve Color page UI
2. Open the Gallery panel
3. Right-click a still → **Export as DRX**
4. Save to an accessible path

### Applying DRX via execute_script

```python
resolve.OpenPage("color")
timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
items = timeline.GetItemListInTrack("video", 1)

# Mode: 0=No keyframes, 1=Source Timecode aligned, 2=Start Frames aligned
success = timeline.ApplyGradeFromDRX("/path/to/template.drx", 0, items)
print(f"DRX applied: {success}")
```

### Inspecting Nodes After DRX Application

```python
# Use TimelineItem methods, NOT the graph object
item = items[0]
num_nodes = item.GetNumNodes()
for i in range(1, num_nodes + 1):
    label = item.GetNodeLabel(i)
    lut = item.GetLUT(i)
    print(f"Node {i}: {label} (LUT: {lut})")
```

### DRX Application Modes

| Mode | Value | Behavior |
|---|---|---|
| No keyframes | `0` | Grade applied flat, no temporal alignment |
| Source Timecode | `1` | Keyframes aligned to clip source timecode |
| Start Frames | `2` | Keyframes aligned to clip start frame |

---

## Color Version Management

Versions allow A/B comparison of different grades on the same clip without destructive switching.

```python
# Create versions
item.AddVersion("Warm Look", 0)       # 0 = local version, 1 = remote version
item.LoadVersionByName("Warm Look", 0)
# Apply grade to this version via SetCDL or wheel ops...

item.AddVersion("Cool Look", 0)
item.LoadVersionByName("Cool Look", 0)
# Apply a different grade...

# Switch between versions for comparison
item.LoadVersionByName("Warm Look", 0)
item.LoadVersionByName("Cool Look", 0)

# List all versions on a clip
versions = item.GetVersionNameList(0)
print(versions)

# Remove a version
item.DeleteVersionByName("Cool Look", 0)
```

> Version type `0` = local (clip-level), `1` = remote (shared across clips with the same source). Use local versions for per-clip A/B work.

---

## Color Presets via MCP

Presets store the current node structure and grade for reuse across projects.

### Save and Apply

```
save_color_preset(preset_name="My Look", album_name="Project Grades")
apply_color_preset(preset_name="My Look", album_name="Project Grades")
```

### Managing Albums

```
create_color_preset_album(album_name="Project Grades")
delete_color_preset_album(album_name="Project Grades")
```

### Batch LUT Export from Presets

```
export_all_powergrade_luts(export_dir="/path/to/luts")
```

Exports all PowerGrades in the current album as LUT files to the specified directory.

---

## Color Science Setup

### Via MCP Tools

```
set_color_science_mode_tool(mode="YRGB Color Managed")
set_color_space_tool(color_space="Rec.709", gamma="Gamma 2.4")
```

### Common Configurations

| Use Case | Color Science | Color Space | Gamma | Notes |
|---|---|---|---|---|
| Standard HD | YRGB | Rec.709 | Gamma 2.4 | Default for most broadcast work |
| HDR | YRGB Color Managed | Rec.2020 | ST.2084 | Requires HDR monitoring |
| Film Workflow | ACEScct | ACEScct | ACEScct | For film-originated content |
| Digital Cinema | YRGB Color Managed | DCI-P3 D65 | Gamma 2.6 | Digital cinema mastering |

> Set color science **before** applying grades. Changing it afterward shifts the look of all existing CDL and LUT work.

---

## Batch Grading Patterns

### Copy Grade to All Clips in Track

```python
resolve.OpenPage("color")
timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()

clips = timeline.GetItemListInTrack("video", 1)
source = clips[0]
targets = clips[1:]

success = source.CopyGrades(targets)
print(f"Grade copied to {len(targets)} clips: {success}")
```

### Apply CDL by Clip Color Tag

Use clip color tags set in the Edit page to target specific clips for grading.

```python
resolve.OpenPage("color")
timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()

video_tracks = timeline.GetTrackCount("video")
graded = 0

for track in range(1, video_tracks + 1):
    items = timeline.GetItemListInTrack("video", track) or []
    for item in items:
        if item.GetClipColor() == "Orange":
            item.SetCDL({
                "NodeIndex": "1",
                "Slope": "1.05 1.0 0.95",
                "Offset": "0 0 0",
                "Power": "1 1 1",
                "Saturation": "1.1"
            })
            graded += 1
            print(f"Graded: {item.GetName()}")

print(f"Total graded: {graded}")
```

**Available clip colors**: `Orange`, `Apricot`, `Yellow`, `Lime`, `Olive`, `Green`, `Teal`, `Navy`, `Blue`, `Purple`, `Violet`, `Pink`, `Tan`, `Beige`, `Brown`, `Chocolate`

### Apply a LUT to Every Clip on a Track

```python
resolve.OpenPage("color")
timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()

items = timeline.GetItemListInTrack("video", 1) or []
for item in items:
    item.SetLUT(1, "MyLook.cube")   # node_index=1, filename only
    print(f"LUT applied: {item.GetName()}")
```

### Multi-Pass Grade (CDL then LUT)

Apply a CDL correction on node 1, then a LUT on node 2 using a DRX with the correct node structure.

```python
# After applying DRX to establish node structure:
for item in timeline.GetItemListInTrack("video", 1):
    # Node 1: CDL correction
    item.SetCDL({
        "NodeIndex": "1",
        "Slope": "1.02 1.0 0.98",
        "Offset": "0.01 0.0 -0.01",
        "Power": "1.0 1.0 1.0",
        "Saturation": "0.95"
    })
    # Node 2: LUT creative look
    item.SetLUT(2, "CreativeLook.cube")
```

> The DRX must pre-establish at least 2 nodes. The API cannot create nodes without a DRX or manual setup.
