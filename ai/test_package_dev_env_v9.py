import tempfile
import unittest
import zipfile
import json
from pathlib import Path

from ai.package_dev_env_v9 import FILES, make_zip, read_inputs

class PackageV9Tests(unittest.TestCase):
    def fixtures(self,root):
        root=Path(root)
        for name in FILES:
            file=root/name
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes(("source:"+name).encode("utf-8"))

    def test_required_source_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"MISSING_OR_UNSAFE"):
                read_inputs(tmp)

    def test_deterministic_zip_sha256_and_crc(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"root"
            root.mkdir()
            self.fixtures(root)
            a,b=Path(tmp)/"a.zip",Path(tmp)/"b.zip"
            evidence=make_zip(root,a,Path(tmp)/"evidence.json")
            self.assertEqual(make_zip(root,b)["archive_sha256"],evidence["archive_sha256"])
            self.assertEqual(evidence["crc"],"PASS")
            self.assertEqual(evidence["file_sha256"],"PASS")
            self.assertEqual(evidence["release_readiness"],"NO_GO")
            self.assertEqual(evidence["real_product_e2e"],"NOT_RUN")
            self.assertEqual(json.loads((Path(tmp)/"evidence.json").read_text())["archive_sha256"],
                             evidence["archive_sha256"])
            with zipfile.ZipFile(a) as z:
                self.assertIsNone(z.testzip())
                manifest=json.loads(z.read("MANIFEST_SHA256.json"))
                self.assertEqual(len(manifest["files"]),len(FILES)+1)

    def test_does_not_include_arbitrary_unsafe_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"root"
            root.mkdir()
            self.fixtures(root)
            (root/"secrets.env").write_text("SECRET=never-export")
            output=Path(tmp)/"bundle.zip"
            make_zip(root,output)
            with zipfile.ZipFile(output) as z:
                self.assertNotIn("secrets.env",z.namelist())
                self.assertNotIn(b"SECRET=never-export",b"".join(z.read(n) for n in z.namelist()))

    def test_suspicious_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"root"
            root.mkdir()
            self.fixtures(root)
            file=root/FILES[0]
            file.unlink()
            outside=Path(tmp)/"secret"
            outside.write_text("not allowed")
            file.symlink_to(outside)
            with self.assertRaisesRegex(ValueError,"MISSING_OR_UNSAFE"):
                read_inputs(root)

if __name__=="__main__":
    unittest.main()
