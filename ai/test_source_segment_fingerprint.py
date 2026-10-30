import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from ai.source_segment_fingerprint import PATHS,KNOWN_BAD,ordering_hint,audit,main

class SourceFingerprintTests(unittest.TestCase):
    def create_zip(self,path,omit=None,diverge=False):
        with zipfile.ZipFile(path,"w") as z:
            for i,name in enumerate(PATHS):
                if name!=omit:
                    z.writestr(name,b"synthetic"+(bytes([i]) if diverge else b""))

    def test_known_source_digest_pinned(self):
        self.assertEqual(len(KNOWN_BAD),64)
        self.assertTrue(KNOWN_BAD.startswith("3f1a00b8"))

    def test_ordering_is_advisory_only(self):
        self.assertEqual(ordering_hint(b"const evicted=await evict(d,id,3,1);w=await fh.createWritable()"),"EVICT_BEFORE_NEW_WRITE")
        self.assertEqual(ordering_hint(b"no matching code"),"UNRESOLVED_MANUAL_REVIEW")

    def test_changed_zip_is_not_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/"input.zip"
            self.create_zip(z)
            r=audit(z)
            self.assertEqual(r["source_consistency"],"MATCH")
            self.assertEqual(r["risk"],"CHANGED_BUT_UNREVIEWED_SOURCE")
            self.assertEqual(r["release_readiness"],"NO_GO")
            self.assertEqual(r["status"],"AUDIT_COMPLETED_NO_GO")

    def test_divergent_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/"input.zip"
            self.create_zip(z,diverge=True)
            r=audit(z)
            self.assertEqual(r["source_consistency"],"DIVERGENT")
            self.assertEqual(r["risk"],"DIVERGENT_SOURCES_MANUAL_REVIEW")

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/"input.zip"
            self.create_zip(z,omit=PATHS[0])
            self.assertEqual(audit(z)["risk"],"REQUIRED_SOURCE_MISSING")

    def test_traversal_fails_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/"input.zip"
            with zipfile.ZipFile(z,"w") as f:
                f.writestr("../escape",b"x")
            self.assertEqual(audit(z)["risk"],"UNSAFE_OR_BROKEN_ARCHIVE")

    def test_empty_zip_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/"input.zip"
            with zipfile.ZipFile(z,"w"):
                pass
            self.assertEqual(audit(z)["status"],"BLOCKED")

    @patch("builtins.print")
    def test_cli_never_returns_success_for_unreviewed(self,_unused):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/"input.zip"
            self.create_zip(z)
            evidence=Path(tmp)/"evidence.json"
            self.assertEqual(main([str(z),"--output",str(evidence)]),2)
            self.assertEqual(json.loads(evidence.read_text())["reports"][0]["product_e2e"],"NOT_RUN")

if __name__=="__main__":
    unittest.main()
