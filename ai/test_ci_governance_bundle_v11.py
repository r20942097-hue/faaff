import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from ai.ci_governance_bundle_v11 import build,collect,sha,CORE
from ai.ci_workflow_audit import EXPECTED_GROUP,EXPECTED_CANCEL

def make_tree(root):
    root=Path(root)
    workflow=root/".github/workflows/synthetic.yml"
    workflow.parent.mkdir(parents=True,exist_ok=True)
    workflow.write_text(
        "name: Synthetic CI\non:\n  pull_request:\n"
        "    paths: ['.github/workflows/synthetic.yml']\n"
        "permissions:\n  contents: read\n"
        "concurrency:\n  group: "+EXPECTED_GROUP+"\n"
        "  cancel-in-progress: "+EXPECTED_CANCEL+"\n"
        "jobs:\n  check:\n    runs-on: ubuntu-24.04\n"
        "    steps:\n      - uses: actions/checkout@"+"a"*40+"\n",encoding="utf-8")
    for name in CORE:
        file=root/name
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text("fixture: "+name)

class BundleTests(unittest.TestCase):
    def test_reject_missing_workflow_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"WORKFLOW_AUDIT_MUST_PASS"):
                collect(tmp)
    def test_deterministic_verified_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"repo"
            make_tree(root)
            first=Path(tmp)/"one.zip"
            second=Path(tmp)/"two.zip"
            a=build(root,first,Path(tmp)/"evidence.json")
            b=build(root,second)
            self.assertEqual(a["sha256"],b["sha256"])
            self.assertEqual(a["crc"],"PASS")
            self.assertEqual(a["release_readiness"],"NO_GO")
            self.assertEqual(json.loads((Path(tmp)/"evidence.json").read_text())["sha256"],a["sha256"])
            with zipfile.ZipFile(first) as z:
                self.assertIsNone(z.testzip())
                manifest=json.loads(z.read("MANIFEST_SHA256.json"))
                for row in manifest["files"]:
                    self.assertEqual(sha(z.read(row["path"])),row["sha256"])
    def test_unlisted_secret_never_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"repo"
            make_tree(root)
            (root/"secret.env").write_text("DO_NOT_UPLOAD_PRIVATE")
            output=Path(tmp)/"out.zip"
            build(root,output)
            with zipfile.ZipFile(output) as z:
                self.assertNotIn("secret.env",z.namelist())
                self.assertFalse(any(b"DO_NOT_UPLOAD_PRIVATE" in z.read(n) for n in z.namelist()))
    def test_symlinked_core_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"repo"
            make_tree(root)
            file=root/CORE[0]
            file.unlink()
            other=Path(tmp)/"outside"
            other.write_text("private")
            file.symlink_to(other)
            with self.assertRaisesRegex(ValueError,"UNSAFE_SOURCE"):
                collect(root)

if __name__=="__main__":
    unittest.main()
