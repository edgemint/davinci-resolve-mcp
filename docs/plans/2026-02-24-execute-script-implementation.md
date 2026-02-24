# `execute_script` Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an MCP tool that lets LLMs execute arbitrary Python code inside DaVinci Resolve's scripting environment with live object context, import restrictions, and timeout.

**Architecture:** Single `@mcp.tool()` function using in-process `exec()` with a prepared namespace. A helper builds the restricted namespace and a thread wrapper enforces the timeout. All code lives in `src/resolve_mcp_server.py`.

**Tech Stack:** Python stdlib (`threading`, `io`, `traceback`, `builtins`), FastMCP decorators, existing Resolve connection globals.

**Security note:** Import restrictions are a *convenience guardrail*, not a security boundary. The MCP server runs locally with the user's own permissions. The restrictions prevent accidental filesystem/network operations, not a determined attacker.

---

### Task 1: Write the unit test file for execute_script

**Files:**
- Create: `tests/test_execute_script.py`

**Step 1: Create test file with mock-based unit tests**

```python
#!/usr/bin/env python3
"""Unit tests for the execute_script tool.

These tests mock the DaVinci Resolve connection so they can run
without Resolve being installed or running.
"""

import unittest
from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def make_mock_resolve():
    """Create a mock resolve object hierarchy."""
    resolve = MagicMock()
    project_manager = MagicMock()
    project = MagicMock()
    media_pool = MagicMock()
    timeline = MagicMock()

    resolve.GetProjectManager.return_value = project_manager
    project_manager.GetCurrentProject.return_value = project
    project.GetMediaPool.return_value = media_pool
    project.GetCurrentTimeline.return_value = timeline

    return resolve, project_manager, project, media_pool, timeline


class TestExecuteScript(unittest.TestCase):
    """Tests for execute_script tool."""

    def setUp(self):
        """Patch resolve global before importing."""
        self.resolve, self.pm, self.project, self.media_pool, self.timeline = make_mock_resolve()

        import src.resolve_mcp_server as server_module
        self._original_resolve = server_module.resolve
        server_module.resolve = self.resolve
        from src.resolve_mcp_server import execute_script
        self.execute_script = execute_script

    def tearDown(self):
        import src.resolve_mcp_server as server_module
        server_module.resolve = self._original_resolve

    # --- Basic execution ---

    def test_simple_expression(self):
        """Script that sets result to a simple value."""
        res = self.execute_script(code="result = 1 + 2")
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], 3)
        self.assertIsNone(res["error"])

    def test_print_capture(self):
        """Print output is captured in 'output' field."""
        res = self.execute_script(code="print('hello world')")
        self.assertTrue(res["success"])
        self.assertIn("hello world", res["output"])

    def test_print_and_result(self):
        """Both print and result work together."""
        res = self.execute_script(code="print('log'); result = 42")
        self.assertTrue(res["success"])
        self.assertIn("log", res["output"])
        self.assertEqual(res["result"], 42)

    def test_print_with_sep_and_end(self):
        """Print with custom sep and end arguments works."""
        res = self.execute_script(code="print('a', 'b', sep='-', end='!')")
        self.assertTrue(res["success"])
        self.assertEqual(res["output"], "a-b!")

    # --- Pre-loaded namespace ---

    def test_resolve_object_available(self):
        res = self.execute_script(code="result = resolve is not None")
        self.assertTrue(res["success"])
        self.assertTrue(res["result"])

    def test_project_available(self):
        res = self.execute_script(code="result = project is not None")
        self.assertTrue(res["success"])
        self.assertTrue(res["result"])

    def test_timeline_available(self):
        res = self.execute_script(code="result = timeline is not None")
        self.assertTrue(res["success"])
        self.assertTrue(res["result"])

    def test_media_pool_available(self):
        res = self.execute_script(code="result = media_pool is not None")
        self.assertTrue(res["success"])
        self.assertTrue(res["result"])

    def test_project_manager_available(self):
        res = self.execute_script(code="result = project_manager is not None")
        self.assertTrue(res["success"])
        self.assertTrue(res["result"])

    # --- Import restrictions ---

    def test_blocked_import_os(self):
        res = self.execute_script(code="import os")
        self.assertFalse(res["success"])
        self.assertIn("blocked", res["error"].lower())

    def test_blocked_import_subprocess(self):
        res = self.execute_script(code="import subprocess")
        self.assertFalse(res["success"])
        self.assertIn("blocked", res["error"].lower())

    def test_blocked_import_shutil(self):
        res = self.execute_script(code="import shutil")
        self.assertFalse(res["success"])
        self.assertIn("blocked", res["error"].lower())

    def test_blocked_from_import(self):
        """from X import Y is also blocked for dangerous modules."""
        res = self.execute_script(code="from os import path")
        self.assertFalse(res["success"])
        self.assertIn("blocked", res["error"].lower())

    def test_blocked_dotted_import(self):
        """import os.path is blocked via root module check."""
        res = self.execute_script(code="import os.path")
        self.assertFalse(res["success"])
        self.assertIn("blocked", res["error"].lower())

    def test_blocked_nested_exec_import(self):
        """exec('import os') inside script is still blocked."""
        res = self.execute_script(code="exec('import os')")
        self.assertFalse(res["success"])
        self.assertIn("blocked", res["error"].lower())

    def test_allowed_import_json(self):
        res = self.execute_script(code="import json; result = json.dumps({'a': 1})")
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], '{"a": 1}')

    def test_allowed_import_math(self):
        res = self.execute_script(code="import math; result = math.pi")
        self.assertTrue(res["success"])
        self.assertAlmostEqual(res["result"], 3.14159, places=4)

    def test_allowed_import_re(self):
        res = self.execute_script(code="import re; result = bool(re.match(r'\\d+', '123'))")
        self.assertTrue(res["success"])
        self.assertTrue(res["result"])

    # --- Error handling ---

    def test_syntax_error(self):
        res = self.execute_script(code="def foo(")
        self.assertFalse(res["success"])
        self.assertIn("SyntaxError", res["error"])

    def test_runtime_error(self):
        res = self.execute_script(code="x = 1 / 0")
        self.assertFalse(res["success"])
        self.assertIn("ZeroDivisionError", res["error"])

    def test_name_error(self):
        res = self.execute_script(code="result = undefined_var")
        self.assertFalse(res["success"])
        self.assertIn("NameError", res["error"])

    def test_system_exit_caught(self):
        """SystemExit does not crash the server."""
        res = self.execute_script(code="raise SystemExit(0)")
        self.assertFalse(res["success"])
        self.assertIn("SystemExit", res["error"])

    def test_keyboard_interrupt_caught(self):
        """KeyboardInterrupt does not crash the server."""
        res = self.execute_script(code="raise KeyboardInterrupt()")
        self.assertFalse(res["success"])
        self.assertIn("KeyboardInterrupt", res["error"])

    # --- Timeout ---

    def test_timeout_enforced(self):
        """Scripts that run too long return a timeout error."""
        res = self.execute_script(
            code="import time; time.sleep(10)",
            timeout=1
        )
        self.assertFalse(res["success"])
        self.assertIn("timed out", res["error"].lower())

    def test_invalid_timeout_too_low(self):
        res = self.execute_script(code="result = 1", timeout=0)
        self.assertFalse(res["success"])
        self.assertIn("timeout", res["error"].lower())

    def test_invalid_timeout_too_high(self):
        res = self.execute_script(code="result = 1", timeout=999)
        self.assertFalse(res["success"])
        self.assertIn("timeout", res["error"].lower())

    # --- No connection ---

    def test_no_resolve_connection(self):
        """Returns error when resolve is None."""
        import src.resolve_mcp_server as server_module
        server_module.resolve = None
        try:
            res = self.execute_script(code="result = 1")
            self.assertFalse(res["success"])
            self.assertIn("Not connected", res["error"])
        finally:
            server_module.resolve = self.resolve

    # --- Result handling ---

    def test_dict_result(self):
        res = self.execute_script(code="result = {'key': 'value', 'num': 42}")
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], {'key': 'value', 'num': 42})

    def test_list_result(self):
        res = self.execute_script(code="result = [1, 2, 3]")
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], [1, 2, 3])

    def test_no_result_variable(self):
        """When no result variable is set, result is None."""
        res = self.execute_script(code="x = 42")
        self.assertTrue(res["success"])
        self.assertIsNone(res["result"])

    def test_multiline_script(self):
        code = """
items = []
for i in range(5):
    items.append(i * 2)
result = items
"""
        res = self.execute_script(code=code)
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], [0, 2, 4, 6, 8])

    def test_non_serializable_result_converted(self):
        """Non-serializable result is converted to string."""
        res = self.execute_script(code="result = resolve")
        self.assertTrue(res["success"])
        # Should be str representation, not crash
        self.assertIsNotNone(res["result"])

    def test_output_truncated_when_large(self):
        """Very large output is truncated."""
        res = self.execute_script(code="print('x' * 200000)")
        self.assertTrue(res["success"])
        self.assertLessEqual(len(res["output"]), 102400 + 100)  # 100KB + truncation msg


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `cd C:/Projects/DavinciMCP && python -m pytest tests/test_execute_script.py -v`
Expected: FAIL — `ImportError` or `AttributeError` because `execute_script` doesn't exist yet.

**Step 3: Commit the test file**

```bash
git add tests/test_execute_script.py
git commit -m "Add unit tests for execute_script MCP tool"
```

---

### Task 2: Implement the execute_script tool

**Files:**
- Modify: `src/resolve_mcp_server.py` (add imports near top ~line 12, add tool before `if __name__` block ~line 4627)

**Step 1: Add required imports at the top of resolve_mcp_server.py**

After the existing `from typing import ...` line (line 12), add:

```python
import io
import threading
import traceback
import builtins
import json as _json
```

**Step 2: Add the execute_script tool before the `if __name__` block**

Insert above line 4628 (`# Start the server`):

```python
# -----------------------
# Script Execution
# -----------------------

# Modules blocked from import inside execute_script.
# This is a convenience guardrail, not a security boundary.
_BLOCKED_MODULES = frozenset({
    'os', 'subprocess', 'shutil', 'sys', 'pathlib',
    'socket', 'http', 'urllib', 'ftplib', 'smtplib',
    'ctypes', 'multiprocessing', 'signal', 'importlib',
    'code', 'codeop', 'runpy',
})

_original_import = builtins.__import__


def _restricted_import(name, *args, **kwargs):
    """Import hook that blocks dangerous modules."""
    top_level = name.split('.')[0]
    if top_level in _BLOCKED_MODULES:
        raise ImportError(
            f"Import of '{name}' is blocked for security. "
            f"Allowed: standard library data/math modules and DaVinci Resolve modules."
        )
    return _original_import(name, *args, **kwargs)


_MAX_OUTPUT_BYTES = 102400  # 100 KB


def _safe_result(value):
    """Convert result to a JSON-safe type. Non-serializable values become their str()."""
    if value is None:
        return None
    try:
        _json.dumps(value)
        return value
    except (TypeError, ValueError, OverflowError):
        return str(value)


@mcp.tool()
def execute_script(code: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute a Python script with access to DaVinci Resolve objects.

    Runs arbitrary Python code in-process with pre-loaded Resolve context.
    Set a 'result' variable in your script to return structured data.
    Use print() for text output.

    Pre-loaded variables: resolve, project_manager, project, media_pool, timeline.

    Blocked imports (always enforced): os, subprocess, shutil, sys, pathlib,
    socket, http, urllib, ftplib, smtplib, ctypes, multiprocessing, signal,
    importlib, code, codeop, runpy.

    Note: timeout returns an error but cannot guarantee the script thread stops.

    Args:
        code: Python source code to execute.
        timeout: Maximum execution time in seconds (1-300). Default: 30.
    """
    # Validate timeout
    if not isinstance(timeout, int) or not (1 <= timeout <= 300):
        return {
            "success": False,
            "output": "",
            "result": None,
            "error": f"Timeout must be between 1 and 300 seconds, got {timeout}",
        }

    # Check connection
    if resolve is None:
        return {
            "success": False,
            "output": "",
            "result": None,
            "error": "Not connected to DaVinci Resolve",
        }

    # Refresh live context
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject() if project_manager else None
    media_pool = project.GetMediaPool() if project else None
    timeline = project.GetCurrentTimeline() if project else None

    # Build restricted builtins — remove exit/quit to prevent server shutdown
    safe_builtins = {k: v for k, v in builtins.__dict__.items()
                     if k not in ('exit', 'quit')}
    safe_builtins['__import__'] = _restricted_import

    # Build execution namespace (fresh dict each call)
    stdout_buffer = io.StringIO()

    def _capture_print(*args, sep=' ', end='\n', **_kwargs):
        stdout_buffer.write(sep.join(str(a) for a in args) + end)

    namespace = {
        '__builtins__': safe_builtins,
        'resolve': resolve,
        'project_manager': project_manager,
        'project': project,
        'media_pool': media_pool,
        'timeline': timeline,
        'print': _capture_print,
    }

    # Check syntax before executing
    try:
        compiled = compile(code, '<execute_script>', 'exec')
    except SyntaxError as e:
        return {
            "success": False,
            "output": "",
            "result": None,
            "error": f"SyntaxError: {e}",
        }

    # Run in thread with timeout
    exec_error = [None]

    def run():
        try:
            exec(compiled, namespace)
        except BaseException:
            exec_error[0] = traceback.format_exc()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    # Collect output, truncate if too large
    output = stdout_buffer.getvalue()
    if len(output) > _MAX_OUTPUT_BYTES:
        output = output[:_MAX_OUTPUT_BYTES] + "\n... (output truncated at 100KB)"

    if thread.is_alive():
        return {
            "success": False,
            "output": output,
            "result": None,
            "error": f"Script execution timed out after {timeout} seconds",
        }

    if exec_error[0] is not None:
        return {
            "success": False,
            "output": output,
            "result": None,
            "error": exec_error[0],
        }

    return {
        "success": True,
        "output": output,
        "result": _safe_result(namespace.get('result')),
        "error": None,
    }
```

**Step 3: Run the tests**

Run: `cd C:/Projects/DavinciMCP && python -m pytest tests/test_execute_script.py -v`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add src/resolve_mcp_server.py
git commit -m "Add execute_script MCP tool for arbitrary Python execution"
```

---

### Task 3: Update documentation

**Files:**
- Modify: `docs/FEATURES.md` (add script execution entry)
- Modify: `docs/TOOLS_README.md` (add tool documentation)

**Step 1: Add entry to FEATURES.md**

Add a new row to the features table under a "Script Execution" section:

```markdown
| Execute Script | execute_script | Execute arbitrary Python code with live Resolve context | ✅ | ⬜ | |
```

**Step 2: Add tool docs to TOOLS_README.md**

Add a section documenting the `execute_script` tool with:
- Description
- Parameters (`code`, `timeout`)
- Return value schema
- Pre-loaded namespace variables
- Blocked imports list
- Example usage showing print + result
- Known limitations (timeout doesn't kill thread, import restrictions are convenience not security boundary)

**Step 3: Commit**

```bash
git add docs/FEATURES.md docs/TOOLS_README.md
git commit -m "Document execute_script tool in feature matrix and tool reference"
```
