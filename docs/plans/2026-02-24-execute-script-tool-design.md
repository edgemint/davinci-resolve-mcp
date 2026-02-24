# Design: `execute_script` MCP Tool

**Date:** 2026-02-24
**Status:** Approved

## Purpose

Add an MCP tool that lets LLMs send arbitrary Python code to be executed inside DaVinci Resolve's scripting environment. This fills the gap when the 150+ pre-defined tools don't cover a specific operation.

## Approach

In-process `exec()` with a prepared namespace containing live Resolve objects, import restrictions, stdout capture, and a timeout.

## Tool Interface

```python
@mcp.tool()
def execute_script(code: str, timeout: int = 30) -> dict:
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | `str` | Yes | — | Python source code to execute |
| `timeout` | `int` | No | `30` | Max execution time in seconds (1–300) |

**Returns:**

```python
{
    "success": bool,
    "output": str,       # Captured stdout
    "result": Any,       # Value of `result` variable if set by script
    "error": str | None  # Traceback or error message if failed
}
```

## Pre-loaded Namespace

Each execution refreshes these from live Resolve state:

| Variable | Source | Description |
|----------|--------|-------------|
| `resolve` | Global server state | Live Resolve application object |
| `project_manager` | `resolve.GetProjectManager()` | Project manager |
| `project` | `project_manager.GetCurrentProject()` | Current project |
| `media_pool` | `project.GetMediaPool()` | Current media pool |
| `timeline` | `project.GetCurrentTimeline()` | Current timeline |

Variables that can't be obtained (e.g., no project open) are set to `None`.

## Import Restrictions

A custom `__import__` override in the exec namespace blocks dangerous modules:

**Blocked:** `os`, `subprocess`, `shutil`, `sys`, `pathlib`, `socket`, `http`, `urllib`, `ftplib`, `smtplib`, `ctypes`, `multiprocessing`, `signal`, `importlib`

**Allowed:** All other stdlib modules (`json`, `math`, `re`, `datetime`, `collections`, `itertools`, `copy`, `time`, `io`, `functools`, etc.) and DaVinci Resolve modules.

No override mechanism — restrictions are always enforced.

## Execution Flow

1. Validate `timeout` is within 1–300 seconds
2. Refresh `project`, `timeline`, `media_pool` from live Resolve state
3. Build namespace dict with pre-loaded variables + restricted `__import__`
4. Redirect `stdout` to a `StringIO` buffer
5. Run `exec(code, namespace)` inside a `threading.Thread`
6. Join with timeout — if exceeded, return timeout error
7. Capture `result` variable from namespace if set
8. Return structured response dict

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Blocked import | `ImportError: "Import of '{module}' is blocked for security"` |
| Syntax error | Caught before exec, returned in `error` field |
| Runtime exception | Full traceback in `error` field |
| Timeout | `"Script execution timed out after {n} seconds"` |
| No Resolve connection | `"Not connected to DaVinci Resolve"` |

## File Placement

Added directly in `src/resolve_mcp_server.py` alongside existing `@mcp.tool()` definitions. Self-contained (~80-100 lines), no separate module needed.
