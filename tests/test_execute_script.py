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
