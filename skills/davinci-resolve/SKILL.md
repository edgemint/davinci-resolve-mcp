---
name: davinci-resolve
description: >
  Operator guide for controlling DaVinci Resolve via MCP tools and the Python scripting API.
  Use when orchestrating video editing workflows: importing media, building timelines, color grading,
  rendering, managing projects, or executing custom Python scripts against the Resolve API.
  Triggers on any DaVinci Resolve task including: timeline assembly, clip management, color correction,
  LUT application, render queue management, media pool organization, marker placement, keyframe animation,
  project settings, and batch automation via execute_script.
---

# DaVinci Resolve MCP Operator Guide

## Object Hierarchy

All operations flow through this chain — each level requires the previous:

```
Resolve → ProjectManager → Project → MediaPool → Folder → MediaPoolItem
                                   → Timeline → TimelineItem
```

Pre-loaded in `execute_script`: `resolve`, `project_manager`, `project`, `media_pool`, `timeline`.

## Tool Inventory (84 Tools)

### Project Management
`open_project`, `create_project`, `save_project`, `close_project`, `set_project_setting`, `set_project_property_tool`, `set_timeline_format_tool`

### Timeline Operations
`create_timeline`, `create_empty_timeline`, `delete_timeline`, `set_current_timeline`, `list_timelines_tool`, `add_clip_to_timeline`, `add_marker`

### Media Pool
`import_media`, `delete_media`, `move_media_to_bin`, `create_bin`, `create_sub_clip`, `auto_sync_audio`, `unlink_clips`, `relink_clips`, `link_proxy_media`, `unlink_proxy_media`, `replace_clip`, `export_folder`

### Transcription
`transcribe_audio`, `clear_transcription`, `transcribe_folder_audio`, `clear_folder_transcription`

### Color Grading
`apply_lut`, `set_color_wheel_param`, `add_node`, `copy_grade`, `save_color_preset`, `apply_color_preset`, `delete_color_preset`, `create_color_preset_album`, `delete_color_preset_album`, `export_lut`, `export_all_powergrade_luts`

### Delivery / Render
`add_to_render_queue`, `start_render`, `clear_render_queue`

### Timeline Item Properties
`set_timeline_item_transform`, `set_timeline_item_crop`, `set_timeline_item_composite`, `set_timeline_item_retime`, `set_timeline_item_stabilization`, `set_timeline_item_audio`

### Keyframes
`add_keyframe`, `modify_keyframe`, `delete_keyframe`, `set_keyframe_interpolation`, `enable_keyframes`

### Cache & Optimization
`set_cache_mode`, `set_cache_path`, `set_optimized_media_mode`, `generate_optimized_media`, `delete_optimized_media`, `set_proxy_mode`, `set_proxy_quality`

### Color Science & Workspace
`set_color_science_mode_tool`, `set_color_space_tool`, `set_superscale_settings_tool`, `switch_page`, `open_settings`, `open_app_preferences`

### Layout Presets
`save_layout_preset_tool`, `load_layout_preset_tool`, `export_layout_preset_tool`, `import_layout_preset_tool`, `delete_layout_preset_tool`

### Cloud Operations
`create_cloud_project_tool`, `import_cloud_project_tool`, `restore_cloud_project_tool`, `export_project_to_cloud_tool`, `add_user_to_cloud_project_tool`, `remove_user_from_cloud_project_tool`

### App Control
`quit_app`, `restart_app`

### Inspection & Scripting
`object_help`, `inspect_custom_object`, `execute_script`

## Core Workflow Patterns

### 1. Import Media → Build Timeline → Render

```
1. create_project(name="MyProject")
2. set_project_setting(setting_name="timelineFrameRate", setting_value="24")
3. import_media(file_path="/path/to/clip.mp4")        # repeat per file
4. create_bin(name="Footage")
5. move_media_to_bin(clip_name="clip.mp4", bin_name="Footage")
6. create_timeline(name="Main Edit")
7. add_clip_to_timeline(clip_name="clip.mp4")          # appends in order called
8. switch_page(page="deliver")
9. add_to_render_queue(preset_name="H.264 Master")
10. start_render()
```

### 2. Color Grading Pipeline

```
1. switch_page(page="color")
2. set_current_timeline(name="Main Edit")
3. add_node(node_type="serial", label="Primary")
4. set_color_wheel_param(wheel="lift", param="master", value=-0.05)
5. set_color_wheel_param(wheel="gain", param="master", value=1.1)
6. apply_lut(lut_path="/path/to/look.cube", node_index=2)
7. save_color_preset(preset_name="My Look")
8. copy_grade(source_clip_name="clip01", target_clip_name="clip02", mode="full")
```

### 3. Batch Processing via execute_script

When MCP tools don't cover a use case, use `execute_script` for direct API access:

```python
# Pre-loaded: resolve, project_manager, project, media_pool, timeline
video_tracks = timeline.GetTrackCount("video")
for track in range(1, video_tracks + 1):
    items = timeline.GetItemListInTrack("video", track)
    for item in items:
        item.SetClipColor("Orange")
        print(f"Colored: {item.GetName()}")
```

Blocked imports: `os`, `subprocess`, `sys`, `pathlib`, `socket`, `http`, `shutil`, `ctypes`. Max timeout: 300s.

## When to Use execute_script vs MCP Tools

| Use MCP tools when | Use execute_script when |
|---|---|
| A dedicated tool exists for the operation | No tool covers your need |
| Simple single-step operations | Multi-step logic with conditionals/loops |
| You need clear error messages | You need to chain API calls programmatically |
| Standard workflows | Reading bulk metadata or properties |
| | Iterating all clips/items with custom logic |
| | Operations needing the full Resolve API surface |

## Critical Rules

1. **All indices are 1-based** — timelines, tracks, nodes, takes, comp indices
2. **AppendToTimeline is append-only** — clips cannot be repositioned after placement; append in correct order
3. **CloseProject does NOT save** — always `save_project` first
4. **Page matters** — switch to correct page before operations (color page for grading, deliver for rendering)
5. **No GetSelectedItems API** — use clip color as selection indicator, or iterate all clips
6. **LUT paths** — use filename only (not full path) after placing LUTs in the master LUT directory
7. **RefreshLUTList** — call after installing new LUTs before applying them (via execute_script)
8. **Marker colors** — valid: Blue, Cyan, Green, Yellow, Red, Pink, Purple, Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream

## Reference Files

- **[MCP Tools Reference](references/mcp-tools.md)** — complete parameter docs for all 84 tools
- **[Python Scripting API](references/scripting-api.md)** — full Resolve API reference for execute_script usage
- **[Workflow Recipes](references/workflows.md)** — step-by-step guides for common tasks
- **[Color Grading Guide](references/color-grading.md)** — CDL presets, LUT workflow, DRX templates, color versions
- **[Gotchas & Workarounds](references/gotchas.md)** — API limitations, known bugs, platform differences
