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


def permission_issues(src: str, filename: str) -> list[str]:
    """Validate the narrow permissions mapping subset used by these workflows.

    Reject unusual scalar/flow permissions instead of assuming read-only.
    This deliberately is not a general-purpose YAML parser.
    """
    lines = src.splitlines()
    problems: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^( *)permissions:\s*(.*?)\s*(?:#.*)?$", line)
        if not match:
            continue
        indent = len(match.group(1))
        if match.group(2):
            problems.append("scalar_or_inline_permissions")
            continue
        entries = []
        for next_line in lines[index + 1:]:
            stripped = next_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            depth = len(next_line) - len(next_line.lstrip(" "))
            if depth <= indent:
                break
            if depth != indent + 2:
                problems.append("unexpected_permissions_nesting")
                continue
            grant = re.fullmatch(r"([a-z][a-z-]*):\s*(read|write|none)\s*(?:#.*)?", stripped)
            if not grant:
                problems.append("invalid_permission_grant")
                continue
            scope, access = grant.groups()
            entries.append((scope, access))
            if access == "write" and not (filename == "codeql.yml" and scope == "security-events"):
                problems.append("unexpected_write_permission:" + scope)
        if not entries:
            problems.append("missing_granular_permissions")
    if not re.search(r"(?m)^permissions:\s*\n  contents: read\s*(?:\n|$)", src):
        problems.append("missing_readonly_default")
    return problems


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
                self.assertEqual(permission_issues(src, path.name), [])

    def test_job_level_write_is_rejected(self):
        fixture = "permissions:\n  contents: read\njobs:\n  test:\n    permissions:\n      checks: write\n"
        self.assertIn("unexpected_write_permission:checks", permission_issues(fixture, "ci.yml"))

    def test_scalar_write_all_is_rejected(self):
        fixture = "permissions: write-all\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        self.assertIn("scalar_or_inline_permissions", permission_issues(fixture, "ci.yml"))

    def test_codeql_write_exception_is_scoped(self):
        fixture = "permissions:\n  contents: read\n  security-events: write\n"
        self.assertEqual(permission_issues(fixture, "codeql.yml"), [])
        self.assertIn("unexpected_write_permission:security-events",
                      permission_issues(fixture, "ci.yml"))

    def test_inline_permissions_are_not_ignored(self):
        fixture = "permissions:\n  contents: read\njobs:\n  test:\n    permissions: { issues: write }\n"
        self.assertIn("scalar_or_inline_permissions", permission_issues(fixture, "ci.yml"))

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
