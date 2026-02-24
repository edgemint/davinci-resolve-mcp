# DaVinci Resolve MCP Tools Reference

84 tools across 12 categories.

## Table of Contents

1. [Project Management](#project-management) (6 tools)
2. [Timeline Operations](#timeline-operations) (7 tools)
3. [Media Pool Operations](#media-pool-operations) (15 tools)
4. [Color Grading](#color-grading) (11 tools)
5. [Delivery / Render](#delivery--render) (3 tools)
6. [Timeline Item Properties](#timeline-item-properties) (6 tools)
7. [Keyframes](#keyframes) (5 tools)
8. [Cache & Optimization](#cache--optimization) (7 tools)
9. [Color Science & Workspace](#color-science--workspace) (6 tools)
10. [Layout Presets](#layout-presets) (5 tools)
11. [Cloud Operations](#cloud-operations) (6 tools)
12. [Application Control](#application-control) (2 tools)
13. [Inspection & Scripting](#inspection--scripting) (3 tools)

---

## Project Management

### `open_project`

Opens a project by name.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | yes | Must match existing project name exactly |

API: `project_manager.LoadProject(name)`

---

### `create_project`

Creates a new project.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | yes | |

API: `project_manager.CreateProject(name)`

---

### `save_project`

Saves the current project. No parameters. Uses multiple fallback approaches internally.

---

### `close_project`

Closes the current project **without saving**. No parameters. Always call `save_project` first.

---

### `set_project_setting`

Sets a project-level setting. Values are auto-converted to the appropriate type.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `setting_name` | string | yes | See common settings below |
| `setting_value` | any | yes | Auto-converted to appropriate type |

**Common settings:**

| Setting Name | Description |
|---|---|
| `timelineFrameRate` | Frame rate |
| `timelineResolutionWidth` | Width in pixels |
| `timelineResolutionHeight` | Height in pixels |
| `colorScienceMode` | Color science mode |
| `superScale` | Super scale setting |

---

### `set_project_property_tool`

Sets a property on the current project.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `property_name` | string | yes | |
| `property_value` | any | yes | |

---

### `set_timeline_format_tool`

Sets the timeline format (resolution, frame rate, interlacing).

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `width` | int | yes | | Width in pixels |
| `height` | int | yes | | Height in pixels |
| `frame_rate` | float | yes | | |
| `interlaced` | bool | no | `false` | |

---

## Timeline Operations

### `create_timeline`

Creates a new timeline. Checks for duplicate names before creating.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | yes | |

---

### `create_empty_timeline`

Creates a new empty timeline with optional format settings.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | yes | |
| `frame_rate` | float | no | |
| `resolution_width` | int | no | |
| `resolution_height` | int | no | |
| `start_timecode` | string | no | e.g. `"01:00:00:00"` |
| `video_tracks` | int | no | |
| `audio_tracks` | int | no | |

---

### `delete_timeline`

Deletes a timeline by name.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | yes | |

---

### `set_current_timeline`

Switches the active timeline.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | yes | Must match an existing timeline name |

---

### `list_timelines_tool`

Returns a list of all timeline names in the current project. No parameters.

---

### `add_clip_to_timeline`

Appends a clip to the end of a timeline. Append-only — no repositioning after insert.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | Must exist in media pool |
| `timeline_name` | string | no | Defaults to current timeline |

---

### `add_marker`

Adds a marker to the current timeline.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `frame` | int | no | Defaults to current playhead position |
| `color` | string | yes | See valid colors below |
| `note` | string | yes | Marker label/note text |

**Valid colors:** Blue, Cyan, Green, Yellow, Red, Pink, Purple, Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream

---

## Media Pool Operations

### `import_media`

Imports a media file into the media pool. Validates file existence and format before import.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `file_path` | string | yes | Absolute path to the file |

---

### `delete_media`

Deletes a clip from the media pool by name.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | |

---

### `move_media_to_bin`

Moves a clip to a named bin.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | |
| `bin_name` | string | yes | Bin must already exist |

---

### `create_bin`

Creates a new bin in the media pool. Checks for duplicate names.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | yes | |

---

### `create_sub_clip`

Creates a sub-clip from a source clip.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | Source clip |
| `start_frame` | int | yes | |
| `end_frame` | int | yes | |
| `sub_clip_name` | string | no | |
| `bin_name` | string | no | |

---

### `auto_sync_audio`

Auto-syncs audio for a set of clips.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_names` | list[string] | yes | |
| `sync_method` | string | yes | `'waveform'` or `'timecode'` |
| `append_mode` | bool | yes | |
| `target_bin` | string | no | |

---

### `unlink_clips`

Unlinks audio/video for a set of clips.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_names` | list[string] | yes | |

---

### `relink_clips`

Relinks clips to their source media.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_names` | list[string] | yes | |
| `media_paths` | list[string] | no | Explicit file paths |
| `folder_path` | string | no | Search folder |
| `recursive` | bool | yes | Search subfolders |

---

### `link_proxy_media`

Links a proxy file to a clip. Validates file existence before linking.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | |
| `proxy_file_path` | string | yes | Absolute path to proxy file |

---

### `unlink_proxy_media`

Unlinks proxy media from a clip.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | |

---

### `replace_clip`

Replaces a clip with a different media file.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | |
| `replacement_path` | string | yes | Absolute path |

---

### `export_folder`

Exports a media pool folder.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `folder_name` | string | yes | | |
| `export_path` | string | yes | | Destination directory |
| `export_type` | string | no | `'DRB'` | |

---

### `transcribe_audio`

Transcribes audio for a single clip.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `clip_name` | string | yes | | |
| `language` | string | no | `'en-US'` | BCP-47 language tag |

---

### `clear_transcription`

Clears the transcription for a single clip.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_name` | string | yes | |

---

### `transcribe_folder_audio`

Transcribes audio for all clips in a folder.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `folder_name` | string | yes | | |
| `language` | string | no | `'en-US'` | BCP-47 language tag |

---

### `clear_folder_transcription`

Clears transcriptions for all clips in a folder.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `folder_name` | string | yes | |

---

## Color Grading

### `apply_lut`

Applies a LUT to the current clip's node.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `lut_path` | string | yes | Use filename only after placing file in master LUT directory |
| `node_index` | int | no | Defaults to current node |

**Supported formats:** `.cube`, `.3dl`, `.lut`, `.mga`

---

### `set_color_wheel_param`

Sets a color wheel parameter on a node.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `wheel` | string | yes | `'lift'`, `'gamma'`, `'gain'`, or `'offset'` |
| `param` | string | yes | `'red'`, `'green'`, `'blue'`, or `'master'` |
| `value` | float | yes | |
| `node_index` | int | no | Defaults to current node |

---

### `add_node`

Adds a node to the current clip's grade.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `node_type` | string | yes | `'serial'`, `'parallel'`, or `'layer'` |
| `label` | string | no | |

---

### `copy_grade`

Copies a grade between clips.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `source_clip_name` | string | no | Defaults to current clip |
| `target_clip_name` | string | no | Defaults to current clip |
| `mode` | string | yes | `'full'`, `'current_node'`, or `'all_nodes'` |

---

### `save_color_preset`

Saves the current grade as a color preset.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `clip_name` | string | no | Current clip | |
| `preset_name` | string | no | | |
| `album_name` | string | no | `'DaVinci Resolve'` | |

---

### `apply_color_preset`

Applies a saved color preset to a clip.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `preset_id` | string | no | Use `preset_id` or `preset_name` |
| `preset_name` | string | no | |
| `clip_name` | string | no | Defaults to current clip |
| `album_name` | string | yes | |

---

### `delete_color_preset`

Deletes a color preset.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `preset_id` | string | no | Use `preset_id` or `preset_name` |
| `preset_name` | string | no | |
| `album_name` | string | yes | |

---

### `create_color_preset_album`

Creates a new color preset album.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `album_name` | string | yes | |

---

### `delete_color_preset_album`

Deletes a color preset album.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `album_name` | string | yes | |

---

### `export_lut`

Exports a LUT from the current clip's grade.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `clip_name` | string | no | Current clip | |
| `export_path` | string | no | | Destination file path |
| `lut_format` | string | no | `'Cube'` | `'Cube'`, `'Davinci'`, `'3dl'`, or `'Panasonic'` |
| `lut_size` | string | no | `'33Point'` | `'17Point'`, `'33Point'`, or `'65Point'` |

---

### `export_all_powergrade_luts`

Exports LUTs for all PowerGrades in the album.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `export_dir` | string | yes | Destination directory |

---

## Delivery / Render

### `add_to_render_queue`

Adds a timeline to the render queue using a named preset.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `preset_name` | string | yes | Must match a saved render preset |
| `timeline_name` | string | no | Defaults to current timeline |
| `use_in_out_range` | bool | yes | Render only in/out range if true |

> **Known issue:** May fail with a NoneType error depending on project state.

---

### `start_render`

Starts rendering all jobs in the render queue. No parameters.

---

### `clear_render_queue`

Clears all jobs from the render queue. No parameters.

---

## Timeline Item Properties

All tools in this section require a `timeline_item_id` string to identify the target item.

### `set_timeline_item_transform`

Sets a transform property on a timeline item.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `property_name` | string | yes | See valid properties below |
| `property_value` | float | yes | |

**Valid properties:** Pan, Tilt, ZoomX, ZoomY, Rotation, AnchorPointX, AnchorPointY, Pitch, Yaw

---

### `set_timeline_item_crop`

Sets a crop value on a timeline item.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `crop_type` | string | yes | `'Left'`, `'Right'`, `'Top'`, or `'Bottom'` |
| `crop_value` | float | yes | |

---

### `set_timeline_item_composite`

Sets composite mode or opacity on a timeline item.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `composite_mode` | string | no | See valid modes below |
| `opacity` | float | no | |

**Valid modes:** Normal, Add, Subtract, Difference, Multiply, Screen, Overlay, Hardlight, Softlight, Darken, Lighten, ColorDodge, ColorBurn, Exclusion, Hue, Saturation, Color, Luminosity

---

### `set_timeline_item_retime`

Sets retime (speed) settings on a timeline item.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `speed` | float | no | e.g. `50.0` for half speed, `200.0` for double |
| `process` | string | no | `'NearestFrame'`, `'FrameBlend'`, or `'OpticalFlow'` |

---

### `set_timeline_item_stabilization`

Sets stabilization settings on a timeline item.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `enabled` | bool | no | |
| `method` | string | no | `'Perspective'`, `'Similarity'`, or `'Translation'` |
| `strength` | float | no | |

---

### `set_timeline_item_audio`

Sets audio properties on a timeline item.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `volume` | float | no | |
| `pan` | float | no | |
| `eq_enabled` | bool | no | |

---

## Keyframes

All keyframe tools require `timeline_item_id` and `property_name` to target the correct property.

### `add_keyframe`

Adds a keyframe at the specified frame.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `property_name` | string | yes | |
| `frame` | int | yes | Timeline frame number |
| `value` | float | yes | |

---

### `modify_keyframe`

Modifies an existing keyframe's value or position.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `property_name` | string | yes | |
| `frame` | int | yes | Current frame of the keyframe |
| `new_value` | float | no | |
| `new_frame` | int | no | Move keyframe to this frame |

---

### `delete_keyframe`

Deletes a keyframe at the specified frame.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `property_name` | string | yes | |
| `frame` | int | yes | |

---

### `set_keyframe_interpolation`

Sets the interpolation type for a keyframe.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `timeline_item_id` | string | yes | |
| `property_name` | string | yes | |
| `frame` | int | yes | |
| `interpolation_type` | string | yes | `'Linear'`, `'Bezier'`, `'Ease-In'`, or `'Ease-Out'` |

---

### `enable_keyframes`

Enables keyframe mode for a timeline item.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `timeline_item_id` | string | yes | | |
| `keyframe_mode` | string | no | `'All'` | `'All'`, `'Color'`, or `'Sizing'` |

---

## Cache & Optimization

### `set_cache_mode`

Sets the render cache mode.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `mode` | string | yes | `'auto'`, `'on'`, or `'off'` |

---

### `set_cache_path`

Sets the cache path for local or network cache.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `path_type` | string | yes | `'local'` or `'network'` |
| `path` | string | yes | Absolute directory path |

---

### `set_optimized_media_mode`

Sets the optimized media mode.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `mode` | string | yes | `'auto'`, `'on'`, or `'off'` |

---

### `generate_optimized_media`

Generates optimized media for clips.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_names` | list | no | Omit to generate for all clips |

---

### `delete_optimized_media`

Deletes optimized media for clips.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `clip_names` | list | no | Omit to delete for all clips |

---

### `set_proxy_mode`

Sets the proxy playback mode.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `mode` | string | yes | `'auto'`, `'on'`, or `'off'` |

---

### `set_proxy_quality`

Sets the proxy playback quality.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `quality` | string | yes | `'quarter'`, `'half'`, `'threeQuarter'`, or `'full'` |

---

## Color Science & Workspace

### `set_color_science_mode_tool`

Sets the project color science mode.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `mode` | string | yes | `'YRGB'`, `'YRGB Color Managed'`, or `'ACEScct'` |

---

### `set_color_space_tool`

Sets the project color space and optional gamma.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `color_space` | string | yes | `'Rec.709'`, `'DCI-P3 D65'`, or `'Rec.2020'` |
| `gamma` | string | no | |

---

### `set_superscale_settings_tool`

Configures the Super Scale upscaling feature.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `enabled` | bool | yes | |
| `quality` | int | yes | `0` = Auto, `1` = Better Quality, `2` = Smoother |

---

### `switch_page`

Switches to a DaVinci Resolve page.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `page` | string | yes | `'media'`, `'cut'`, `'edit'`, `'fusion'`, `'color'`, `'fairlight'`, or `'deliver'` |

---

### `open_settings`

Opens the project settings dialog. No parameters.

---

### `open_app_preferences`

Opens the application preferences dialog. No parameters.

---

## Layout Presets

### `save_layout_preset_tool`

Saves the current UI layout as a named preset.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `preset_name` | string | yes | |

---

### `load_layout_preset_tool`

Loads a saved UI layout preset.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `preset_name` | string | yes | |

---

### `export_layout_preset_tool`

Exports a layout preset to a file.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `preset_name` | string | yes | |
| `export_path` | string | yes | Destination file path |

---

### `import_layout_preset_tool`

Imports a layout preset from a file.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `import_path` | string | yes | Source file path |
| `preset_name` | string | no | Override the preset name on import |

---

### `delete_layout_preset_tool`

Deletes a saved layout preset.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `preset_name` | string | yes | |

---

## Cloud Operations

### `create_cloud_project_tool`

Creates a new cloud project.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `project_name` | string | yes | |
| `folder_path` | string | no | Cloud folder path |

---

### `import_cloud_project_tool`

Imports an existing cloud project by ID.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `cloud_id` | string | yes | |
| `project_name` | string | no | Override local project name |

---

### `restore_cloud_project_tool`

Restores a cloud project by ID.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `cloud_id` | string | yes | |
| `project_name` | string | no | Override local project name |

---

### `export_project_to_cloud_tool`

Exports the current project to the cloud.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `project_name` | string | no | Defaults to current project |

---

### `add_user_to_cloud_project_tool`

Adds a collaborator to a cloud project.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `cloud_id` | string | yes | | |
| `user_email` | string | yes | | |
| `permissions` | string | no | `'viewer'` | `'viewer'`, `'editor'`, or `'admin'` |

---

### `remove_user_from_cloud_project_tool`

Removes a collaborator from a cloud project.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `cloud_id` | string | yes | |
| `user_email` | string | yes | |

---

## Application Control

### `quit_app`

Quits DaVinci Resolve.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `force` | bool | no | `false` | Force quit without prompts |
| `save_project` | bool | no | `true` | Save before quitting |

---

### `restart_app`

Restarts DaVinci Resolve.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `wait_seconds` | int | no | `5` | Seconds to wait before relaunch |

---

## Inspection & Scripting

### `object_help`

Returns available attributes and methods for a Resolve API object.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `object_type` | string | yes | `'resolve'`, `'project_manager'`, `'project'`, `'media_pool'`, or `'timeline'` |

---

### `inspect_custom_object`

Inspects an arbitrary Resolve API object by evaluating an expression.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `object_path` | string | yes | Python expression, e.g. `'resolve.GetMediaStorage()'` |

---

### `execute_script`

Executes arbitrary Python code in a sandboxed environment with access to Resolve API objects.

| Parameter | Type | Required | Default | Max | Notes |
|-----------|------|----------|---------|-----|-------|
| `code` | string | yes | | | Python source code |
| `timeout` | int | no | `30` | `300` | Seconds before timeout |

**Pre-loaded variables:**

| Variable | Object |
|---|---|
| `resolve` | Resolve app instance |
| `project_manager` | ProjectManager |
| `project` | Current project |
| `media_pool` | MediaPool |
| `timeline` | Current timeline |

**Blocked imports:** `os`, `subprocess`, `sys`, `pathlib`, `socket`, `http`, `shutil`, `ctypes`, `multiprocessing`, `signal`, `importlib`, `code`, `codeop`, `runpy`

**Blocked builtins:** `exit`, `quit`, `open`

**Return value:**

```json
{
  "success": true,
  "output": "stdout/stderr captured",
  "result": "return value of last expression",
  "error": "error message if failed"
}
```

Max output: 100 KB.
