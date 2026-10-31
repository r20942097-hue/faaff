"""Offline guard of CI dependency pins, token permissions and PR concurrency."""
from __future__ import annotations
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2] / ".github" / "workflows"
USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
CHECKOUT = re.compile(r"^(\s*)-\s*uses:\s*actions/checkout@[0-9a-f]{40}(?:\s*#.*)?$")
NO_CREDS = re.compile(r"^\s+persist-credentials:\s*false(?:\s*#.*)?$", re.MULTILINE)


class WorkflowSecurityTests(unittest.TestCase):
    def workflows(self):
        files = sorted(ROOT.glob("*.yml")) + sorted(ROOT.glob("*.yaml"))
        self.assertTrue(files)
        return [(p, p.read_text(encoding="utf-8")) for p in files]

    def test_actions_are_pinned(self):
        for path, src in self.workflows():
            for ref in USES.findall(src):
                with self.subTest(path=path.name, action=ref):
                    if not ref.startswith("./"):
                        self.assertRegex(ref, SHA)

    def test_checkout_does_not_persist_credentials(self):
        for path, src in self.workflows():
            lines = src.splitlines()
            for i, line in enumerate(lines):
                m = CHECKOUT.match(line)
                if not m:
                    continue
                indent = len(m.group(1))
                block = []
                for later in lines[i + 1:]:
                    if later.strip() and len(later) - len(later.lstrip(" ")) <= indent and not later.lstrip().startswith("#"):
                        break
                    block.append(later)
                with self.subTest(path=path.name, line=i+1):
                    self.assertRegex("\n".join(block), NO_CREDS)

    def test_workflows_use_least_privilege(self):
        for path, src in self.workflows():
            with self.subTest(path=path.name):
                self.assertNotIn("pull_request_target:", src)
                self.assertRegex(src, r"(?m)^permissions:\s*\n  contents: read\s*(?:\n|$)")
                self.assertNotRegex(src, r"(?m)^\s+(?:contents|actions|pull-requests|id-token):\s*write\s*$")

    def test_pr_concurrency_does_not_cancel_main(self):
        for path, src in self.workflows():
            if re.search(r"(?m)^  pull_request:\s*$", src):
                with self.subTest(path=path.name):
                    self.assertIn("group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}", src)
                    self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", src)

    def test_windows_integrity_checkout_order(self):
        src = (ROOT / "ai-hub.yml").read_text(encoding="utf-8")
        self.assertIn("  windows315-compat:", src)
        section = src.split("  windows315-compat:", 1)[1].split("\n  live-pr-evidence-smoke:", 1)[0]
        self.assertLess(section.index("git config --global core.autocrlf false"),
                        section.index("actions/checkout@"))


if __name__ == "__main__":
    unittest.main()
