import hashlib
import json
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.opfs_process_kill_fixture import (
    BROWSER_COMM, MARKER, parse_group_processes, template, stop_group, run, main
)
from ai.opfs_restart_fixture import HASH_A

class ProcessKillFixtureTests(unittest.TestCase):
    def test_group_parser_excludes_other_groups_and_zombies(self):
        listing=("101 500 S chrome\n"
                 "102 500 Sl chrome-headless\n"
                 "103 500 Z chromium\n"
                 "104 600 S firefox\n"
                 "105 500 S node\n"
                 "106 500 R firefox\n")
        self.assertEqual(parse_group_processes(listing,500,"chromium"),[101,102])
        self.assertEqual(parse_group_processes(listing,500,"firefox"),[106])

    def test_non_browser_process_cannot_confirm_kill(self):
        self.assertEqual(parse_group_processes("101 100 S python\n",100,"chromium"),[])

    def test_no_go_and_no_power_loss_claim(self):
        report=template("firefox")
        self.assertEqual(report["physical_power_failure"],"NOT_RUN")
        self.assertEqual(report["os_kernel_crash"],"NOT_RUN")
        self.assertEqual(report["product_e2e"],"NOT_RUN")
        self.assertEqual(report["release_readiness"],"NO_GO")

    def test_committed_hash_matches_existing_fixture(self):
        self.assertEqual(len(HASH_A),64)
        self.assertEqual(template("chromium")["committed_sha256"],HASH_A)

    def test_no_group_kill_on_missing_process(self):
        self.assertIsNone(stop_group(None))

    def test_ready_requires_explicit_marker(self):
        self.assertEqual(MARKER,"READY_STAGED_UNCOMMITTED")
        self.assertIn("firefox",BROWSER_COMM)

    @patch("ai.opfs_process_kill_fixture.probe",
           side_effect=RuntimeError("private /home/secret"))
    def test_failures_reveal_type_only(self,unused):
        report=run("chromium")
        self.assertEqual(report["status"],"BLOCKED")
        self.assertEqual(report["error_type"],"RuntimeError")
        self.assertNotIn("/home/secret",json.dumps(report))

    @patch("ai.opfs_process_kill_fixture.probe",
           side_effect=RuntimeError("unavailable"))
    def test_cli_error_never_exits_success(self,unused):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"failure.json"
            with patch("builtins.print"):
                code=main(["--browser","firefox","--output",str(out)])
            self.assertEqual(code,2)
            self.assertEqual(json.loads(out.read_text())["release_readiness"],"NO_GO")

if __name__=="__main__":
    unittest.main()
