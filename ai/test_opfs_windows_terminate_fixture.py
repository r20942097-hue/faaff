import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.opfs_windows_terminate_fixture import (
    template,run,main,await_child_marker,force_terminate_owned,KNOWN_CODES
)

class WindowsTerminationUnitTests(unittest.TestCase):
    def test_fail_closed_release_scope(self):
        r=template("firefox")
        self.assertEqual(r["release_readiness"],"NO_GO")
        self.assertEqual(r["product_e2e"],"NOT_RUN")
        self.assertEqual(r["physical_power_failure"],"NOT_RUN")
        self.assertEqual(r["status"],"BLOCKED")

    def test_windows_process_terminology_is_not_sigkill(self):
        import inspect
        from ai import opfs_windows_terminate_fixture as mod
        src=inspect.getsource(mod.force_terminate_owned)
        self.assertIn("target.kill()",src)
        self.assertIn("TerminateProcess",src)
        self.assertNotIn("os.killpg",src)

    def test_stop_missing_proc_is_safe(self):
        self.assertIsNone(force_terminate_owned(None))

    def test_known_codes_include_ownership_fail_closed(self):
        self.assertIn("OWNED_BROWSER_PROCESS_NOT_FOUND",KNOWN_CODES)
        self.assertIn("OWNED_DESCENDANTS_SURVIVED",KNOWN_CODES)
        self.assertIn("POSTCOMMIT_INVENTORY_MISMATCH",KNOWN_CODES)

    @patch("ai.opfs_windows_terminate_fixture.probe",
           side_effect=RuntimeError("private C:\\Users\\secret"))
    def test_exception_redacted(self,_unused):
        r=run("chromium")
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["failure_code"],"UNCLASSIFIED")
        self.assertNotIn("secret",json.dumps(r))

    @patch("ai.opfs_windows_terminate_fixture.probe",
           side_effect=RuntimeError("BROWSER_PROCESS_SURVIVED"))
    def test_known_code_only(self,_unused):
        self.assertEqual(run("firefox")["failure_code"],"BROWSER_PROCESS_SURVIVED")

    @patch("ai.opfs_windows_terminate_fixture.probe",
           side_effect=RuntimeError("unavailable"))
    def test_cli_fails_and_keeps_no_go(self,_unused):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"result.json"
            with patch("builtins.print"):
                code=main(["--browser","firefox","--output",str(path)])
            self.assertEqual(code,2)
            self.assertEqual(json.loads(path.read_text())["release_readiness"],"NO_GO")

    @unittest.skipUnless(os.name=="nt","native Windows assertion only")
    def test_native_process_group_flag_exists(self):
        import subprocess
        self.assertIsInstance(subprocess.CREATE_NEW_PROCESS_GROUP,int)

if __name__=="__main__":
    unittest.main()
