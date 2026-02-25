# DavinciMCP - Project Context

## What This Project Is

DavinciMCP is a Model Context Protocol (MCP) server that connects AI coding assistants (Cursor, Claude Desktop) to DaVinci Resolve, enabling natural language control and querying of video editing operations through MCP tools.

## Tech Stack

- **Language:** Python 3.6+
- **MCP Framework:** Model Context Protocol (FastMCP)
- **Integration:** DaVinci Resolve 18.5+ Python scripting API
- **Platforms:** macOS, Windows
- **Optional:** Node.js/npm for additional features

## Project Structure

```
DavinciMCP/
├── src/
│   ├── resolve_mcp_server.py     # Main MCP tool definitions (84+ tools)
│   ├── main.py                   # Entry point wrapper
│   ├── api/                      # Tool implementation modules
│   │   ├── media_operations.py
│   │   ├── timeline_operations.py
│   │   ├── color_operations.py
│   │   ├── delivery_operations.py
│   │   └── project_operations.py
│   └── utils/                    # Platform, inspection, cloud, etc.
├── config/                       # Configuration files
├── docs/                         # Documentation and features list
├── examples/                     # Example usage scripts
├── scripts/                      # Build and utility scripts
├── skills/davinci-resolve/       # Operator skill + reference docs
│   ├── SKILL.md
│   └── references/
│       ├── mcp-tools.md          # Complete tool reference (84 tools)
│       ├── gotchas.md            # Critical API limitations
│       ├── color-grading.md      # Color workflow guide
│       ├── scripting-api.md      # Full API docs
│       └── workflows.md          # Use case recipes
├── tests/                        # Test suite
├── resolve_mcp_server.py         # Main entry point
├── requirements.txt              # Python dependencies
├── INSTALL.md                    # Installation guide
└── README.md                     # User documentation
```

## Commands

```bash
# Installation (macOS)
./install.sh

# Installation (Windows)
install.bat

# Quick start (macOS)
./run-now.sh

# Quick start (Windows)
run-now.bat

# Manual server start
python resolve_mcp_server.py

# Run tests
pytest tests/
```

## Requirements

- DaVinci Resolve 18.5+ installed and running
- Python 3.6+
- macOS or Windows (Linux not supported)
- Optional: Node.js for advanced features

---

## Video Editing Task Protocol

**This is the most important section. Follow it for ALL video editing tasks.**

### Parallelism Is Mandatory

Video editing is inherently parallel work. When the user asks you to do a video editing task, you MUST decompose it and delegate to subagents. Never do video editing work inline when it can be delegated.

**Default behavior:** Spawn a subagent (usually background) for every video editing task. Use agent teams for complex multi-aspect edits. The user should never be blocked waiting for a single-threaded edit pipeline.

#### Independent Axes of Parallelism

These aspects of a video edit are independent and MUST be parallelized when multiple apply:

| Axis | Examples | Can run in parallel with |
|------|----------|--------------------------|
| **Color grading** | LUTs, color wheels, node trees, presets | Audio, transforms, delivery prep |
| **Audio** | Volume, pan, EQ, sync | Color, transforms, effects |
| **Transform/Crop** | Pan, tilt, zoom, rotation, crop | Color, audio, effects |
| **Effects** | Composite modes, opacity, retime, stabilization | Color, audio, transforms |
| **Media management** | Import, organize bins, create subclips | Everything (do this first if needed) |
| **Transcription** | Transcribe clips or folders | Everything |
| **Delivery/Render** | Queue, render, export | Nothing (runs last, after edits) |

#### What's Sequential (Don't Parallelize These)

- Operations on the same clip's same property (e.g., two color grade changes to the same clip)
- Import → then edit (media must exist before you can edit it)
- Edit → then render (edits must complete before queuing render)
- Operations requiring a specific page (color ops need color page — don't fight another agent for page focus)

### Agent Selection for Video Tasks

| Task complexity | Agent type | Model | Examples |
|----------------|-----------|-------|----------|
| Single MCP tool call | quick-task | Haiku | Apply a LUT, set volume, add marker, import one file |
| Multi-step workflow | standard-task | Sonnet | Color grade a sequence, organize media into bins, set up a timeline |
| Creative/complex decisions | general-purpose-opus | Opus | Debug Resolve API failures, plan complex edit pipelines, architect batch workflows |

### Background Agents by Default

Use `run_in_background: true` for video editing subagents unless:
- The result is needed before the next step (e.g., import before edit)
- The user is waiting for a specific answer (e.g., "what clips are in the timeline?")

**Always background:** Rendering, transcription, batch color grading, batch media import, batch export.

### Agent Teams for Complex Edits

When a task touches 3+ independent axes, spawn an agent team. Example: "Make this look cinematic" might need:
- Color agent: Apply cinematic LUT + adjust color wheels
- Audio agent: Adjust levels, add EQ
- Transform agent: Set letterbox crop, adjust framing
- Delivery agent: Wait for others, then queue render

The team lead coordinates dependencies and ensures page-switching doesn't conflict.

---

## State-First Workflow

**Always inspect before modifying.** The Resolve API has silent failures. Before any edit operation:

1. Check that DaVinci Resolve is running and connected
2. Verify the current project and timeline are what you expect
3. List clips/timelines to confirm targets exist
4. Save the project before destructive or multi-step operations

Use `list_timelines_tool`, `list_timeline_clips`, `list_media_pool_clips` to orient yourself before making changes.

---

## Critical API Gotchas

These WILL bite you if you forget them. Internalize these rules:

1. **1-based indexing everywhere** — Track 1 is `1`, not `0`. Node 1 is `1`. Using 0-based indexing silently fails or hits the wrong target.

2. **Page requirements** — Color operations require the color page (`switch_page("color")`). Render operations require the deliver page. Failing to switch pages causes silent failures.

3. **Append-only timeline** — You cannot insert or reorder clips. `add_clip_to_timeline` always appends. To reorder, you must delete and re-add clips.

4. **LUT constraints:**
   - Must be in the master LUT directory (not subdirectories)
   - Call `RefreshLUTList()` before first use in a session
   - Use filename only: `"MyLook.cube"` not the full path

5. **Grade access requires clip selection** — On the color page, the clip must be selected before you can modify its grade.

6. **Save before switching** — Always call `save_project` before switching projects or timelines. Unsaved changes can be lost.

7. **No direct curve editing** — Cannot adjust color curves via API. Use CDL values, color wheels, or LUT files instead.

8. **Render queue fragility** — May return NoneType errors in certain project states. Always verify queue state after adding jobs.

---

## Batch-First Mentality

When operating on multiple clips, prefer batch patterns over individual MCP tool calls:

- **Use `execute_script`** to iterate over clips in a single Python script, reducing round-trips
- **Use `transcribe_folder_audio`** instead of transcribing clips one at a time
- **Use `copy_grade`** to propagate a grade to similar clips after perfecting it on one
- **Use `export_all_powergrade_luts`** for bulk LUT export

The `execute_script` tool is sandboxed but gives you access to `resolve`, `project_manager`, `project`, `media_pool`, and `timeline` objects for complex batch operations.

---

## Save Checkpoints

Video editing is stateful and not easily undoable via the API. Protect the user's work:

- **Save before** any multi-step operation, destructive operation, or batch operation
- **Save after** completing a major phase of work (all color grading done, all audio adjusted, etc.)
- **Save before render** — always save before queuing and starting a render

---

## Reference Documentation

When you need to look up tool details, parameters, or workflow recipes, consult these files before guessing:

| Reference | Path | Contents |
|-----------|------|----------|
| Tool reference | `skills/davinci-resolve/references/mcp-tools.md` | All 84 tools with parameters and examples |
| API gotchas | `skills/davinci-resolve/references/gotchas.md` | Critical limitations and workarounds |
| Color grading | `skills/davinci-resolve/references/color-grading.md` | Color workflow patterns |
| Scripting API | `skills/davinci-resolve/references/scripting-api.md` | Full DaVinci Resolve Python API |
| Workflow recipes | `skills/davinci-resolve/references/workflows.md` | Common task patterns |

**Read the relevant reference doc before attempting an unfamiliar operation.** These docs contain hard-won knowledge about API behavior that isn't obvious from tool names alone.

---

## MCP Tool Categories (84 tools)

For quick orientation, the available MCP tools cover:

- **Project management** (6) — open, create, save, close, settings
- **Timeline operations** (7) — create, delete, switch, add clips, markers
- **Media pool** (15) — import, delete, bins, subclips, sync, proxy, relink
- **Transcription** (4) — transcribe clips/folders, clear transcriptions
- **Color grading** (11) — LUTs, color wheels, nodes, presets, grade copy
- **Delivery/Render** (3) — queue, render, clear
- **Timeline item properties** (6) — transform, crop, composite, retime, stabilization, audio
- **Keyframes** (5) — add, modify, delete, interpolation, enable
- **Cache & optimization** (7) — cache mode, optimized media, proxy settings
- **Color science & workspace** (6) — color science, color space, superscale, page switching
- **Layout presets** (5) — save, load, export, import, delete
- **Cloud operations** (6) — create, import, restore, export, collaborators
- **App control** (2) — quit, restart
- **Inspection & scripting** (3) — object_help, inspect, execute_script
