# DaVinci Resolve Scripting Gotchas

Critical reference for AI operators using MCP tools or the scripting API. Every item here represents a real failure mode.

---

## Table of Contents

1. [API Limitations](#api-limitations-things-you-cannot-do)
2. [Indexing Rules](#indexing-rules)
3. [Page Requirements](#page-requirements)
4. [Known MCP Tool Issues](#known-mcp-tool-issues)
5. [LUT Gotchas](#lut-gotchas)
6. [Save/Close Behavior](#saveclose-behavior)
7. [Return Value Patterns](#return-value-patterns)
8. [Platform Differences](#platform-differences)
9. [execute_script Constraints](#execute_script-constraints)
10. [Timing and Delays](#timing-and-delays)
11. [Startup Scripts](#startup-scripts)
12. [Data Type Quirks](#data-type-quirks)
13. [Render Settings Limitations](#render-settings-limitations)
14. [Media Pool Quirks](#media-pool-quirks)
15. [Recommended Defensive Patterns](#recommended-defensive-patterns)

---

## API Limitations (Things You CANNOT Do)

| Operation | Status | Workaround |
|---|---|---|
| Move clips in timeline | Not supported | Must append in correct order |
| Insert clips at arbitrary position | Not supported | Append-only via AppendToTimeline |
| Add color nodes programmatically | Limited (MCP add_node tool exists but may fail) | Use DRX templates for complex structures |
| Adjust primary color wheels directly | Via CDL only | Use SetCDL() with slope/offset/power |
| Edit color curves | Not supported | Use LUT files |
| Add power windows | Not supported | Include in DRX template |
| Add effects/plugins | Not supported | Include in DRX or manual |
| Get selected timeline items | Not supported | Use clip color as selection indicator |
| Reorder timeline clips | Not supported | Delete and re-append in order |
| Set arbitrary in/out on placed clips | Not supported | Use create_sub_clip before placement |

---

## Indexing Rules

**Everything is 1-based:**
- Timeline indices: `project.GetTimelineByIndex(1)` is the first
- Track indices: `timeline.GetItemListInTrack("video", 1)` is the first
- Node indices: `item.SetLUT(1, "lut.cube")` is the first node
- Comp indices: `item.GetFusionCompByIndex(1)` is the first
- Take indices: `item.GetTakeByIndex(1)` is the first

**Common mistake:** Using 0-based indexing will silently fail or return None.

---

## Page Requirements

Certain operations require being on the correct page. Always call `switch_page` before page-specific operations.

| Operation | Required Page |
|---|---|
| Color grading (CDL, LUT, nodes) | color |
| Render settings and queue | deliver |
| GetCurrentTimecode() | cut, edit, color, deliver |
| Fusion comp operations | fusion |
| Audio operations | fairlight |
| Media import | any (but media page preferred) |

---

## Known MCP Tool Issues

| Tool | Issue | Status |
|---|---|---|
| add_to_render_queue | May fail with "'NoneType' object is not callable" | Known bug |
| add_node | Fails with "Cannot access grade object" without proper clip selection | Requires color page + selected clip |
| set_color_wheel_param | Similar grade access issues | Requires color page + selected clip |
| create_timeline | Unclear error when name already exists | Check first with list_timelines_tool |
| create_bin | Unclear error when name already exists | Check first |
| transcribe_audio | Reports clip not found | May need specific clip reference |
| set_project_property | Parameter type issues | Try string conversion |

---

## LUT Gotchas

1. **Subdirectories not recognized** — LUTs in a `Custom/` subdirectory won't work. Must be placed directly in the master LUT directory.
2. **Must refresh after install** — Always call `project.RefreshLUTList()` via `execute_script` before the first `SetLUT()` call in a session.
3. **Filename only** — Use `"MyLook.cube"` not `"/path/to/MyLook.cube"` after placing the file in the master directory.
4. **1-based node index** — `SetLUT(0, "lut.cube")` is invalid; use `SetLUT(1, "lut.cube")`.

---

## Save/Close Behavior

- `close_project` does **NOT** save — always call `save_project` first.
- `quit_app` has a `save_project` parameter (default true) but test carefully.
- Auto-save may not be reliable for scripted changes.
- **Pattern:** Always call `save_project` before any project-switching operation.

---

## Return Value Patterns

Most API methods return:
- `True`/`False` for success/failure
- `None` for void operations or failures
- Object references for creation operations

**Always check return values.**

- A `None` return from `CreateProject()` means the name already exists.
- A `False` from `SetLUT()` means the LUT wasn't found or the node index was invalid.
- A `None` return from `GetItemListInTrack()` means the track is empty or doesn't exist — iterating it will throw.

---

## Platform Differences

### Paths

| Resource | macOS | Windows |
|---|---|---|
| API Scripts | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting` | `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting` |
| Script Library | `.../DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so` | `C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll` |
| LUT Directory | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT` | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT` |
| User Scripts | `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts` | `%APPDATA%\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts` |

### Behavior

- Linux is **NOT** supported by this MCP server.
- Windows paths use backslashes in Resolve settings.
- macOS is generally more stable for scripting.
- v19.1 removed UIManager from the free version — affects any script that uses UI elements.

---

## execute_script Constraints

**Blocked imports:** `os`, `subprocess`, `shutil`, `sys`, `pathlib`, `socket`, `http`, `urllib`, `ftplib`, `smtplib`, `ctypes`, `multiprocessing`, `signal`, `importlib`, `code`, `codeop`, `runpy`

**Blocked builtins:** `exit`, `quit`, `open` (file operations)

**Available modules:** `time`, `math`

**Limits:**
- Max timeout: 300 seconds
- Max output: 100KB

**Pre-loaded objects:** `resolve`, `project_manager`, `project`, `media_pool`, `timeline`

**Notes:**
- Runs in a separate thread with a restricted namespace.
- `print()` output is captured and returned in the `"output"` field.
- Use `time.sleep()` for operations that need the UI to update before proceeding.

---

## Timing and Delays

- Page switching may need a brief delay before subsequent operations succeed.
- Render monitoring requires polling via `IsRenderingInProgress()` — there is no callback.
- Don't call operations too rapidly — the API communicates with a live GUI application.
- If an operation returns an unexpected `None` or `False`, add a `time.sleep(0.5)` and retry before assuming failure.

---

## Startup Scripts

- `.scriptlib` startup scripts **cannot** access `GetCurrentProject()` — it returns `None` at startup.
- Use startup scripts only for environment setup, not project operations.

---

## Data Type Quirks

| API | Expected Type | Example |
|---|---|---|
| SetSetting() values | String | `SetSetting("timelineFrameRate", "24")` not `24` |
| CDL values | Space-separated string | `"1.05 0.98 0.95"` not `[1.05, 0.98, 0.95]` |
| CDL NodeIndex | String | `"1"` not `1` |
| Marker frameId keys | Float (dict key) | `{96.0: {...}}` |
| GetClipProperty() values | String (always) | Numeric properties still come back as strings |

---

## Render Settings Limitations

`SetRenderSettings()` only accepts these keys:

- `SelectAllFrames`, `MarkIn`, `MarkOut`, `TargetDir`, `CustomName`, `ExportVideo`, `ExportAudio`

For everything else, use separate calls:

- **Codec/format:** `SetCurrentRenderFormatAndCodec(format, codec)`
- **Presets:** `LoadRenderPreset(name)`
- **Discovery:** `GetRenderFormats()` and `GetRenderCodecs(format)`

---

## Media Pool Quirks

- `GetFileList()` may return consolidated entries — image sequences appear as a single entry.
- `DeleteClips()` takes a **list**, not a single clip object.
- `MoveClips()` takes a **list** of clips plus a target **folder object** (not a folder name string).
- There is no `GetFolderByName()` — you must traverse from `GetRootFolder()` to find a folder by name.

---

## Recommended Defensive Patterns

```python
# Always validate the chain before doing anything
if not resolve: print("No Resolve connection"); return
pm = resolve.GetProjectManager()
if not pm: print("No ProjectManager"); return
proj = pm.GetCurrentProject()
if not proj: print("No project open"); return

# Check for None before iterating track items
items = timeline.GetItemListInTrack("video", 1)
if items:
    for item in items:
        # process...

# Track batch results and report them
success = 0
fail = 0
for clip in clips:
    if clip.SetLUT(1, "look.cube"):
        success += 1
    else:
        fail += 1
print(f"Applied: {success}/{success+fail}")
```
