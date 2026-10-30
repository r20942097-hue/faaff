import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from ai.package_dev_env_v10 import FILES, collect, build, digest

class PackageDevEnvV10Tests(unittest.TestCase):
    @staticmethod
    def fixture(root):
        for name in FILES:
            target=Path(root)/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text("fixture "+name,encoding="utf-8")

    def test_no_missing_inputs_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"MISSING_OR_UNSAFE_SOURCE"):
                collect(tmp)

    def test_deterministic_zip_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"src"
            root.mkdir()
            self.fixture(root)
            one=Path(tmp)/"one.zip"
            two=Path(tmp)/"two.zip"
            first=build(root,one,Path(tmp)/"evidence.json")
            second=build(root,two)
            self.assertEqual(first["archive_sha256"],second["archive_sha256"])
            self.assertEqual(first["zip_crc"],"PASS")
            self.assertEqual(first["sha256_integrity"],"PASS")
            self.assertEqual(first["release_readiness"],"NO_GO")
            self.assertEqual(first["product_e2e"],"NOT_RUN")
            self.assertEqual(json.loads((Path(tmp)/"evidence.json").read_text())["members"],len(FILES)+2)
            with zipfile.ZipFile(one) as zipfile_:
                self.assertIsNone(zipfile_.testzip())
                manifest=json.loads(zipfile_.read("MANIFEST_SHA256.json"))
                self.assertEqual(len(manifest["files"]),len(FILES)+1)
                for entry in manifest["files"]:
                    self.assertEqual(digest(zipfile_.read(entry["path"])),entry["sha256"])

    def test_never_pack_unlisted_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"src"
            root.mkdir()
            self.fixture(root)
            (root/"secret.env").write_text("PRIVATE_SECRET_SHOULD_NOT_EXPORT")
            out=Path(tmp)/"pkg.zip"
            build(root,out)
            with zipfile.ZipFile(out) as z:
                self.assertNotIn("secret.env",z.namelist())
                for name in z.namelist():
                    self.assertNotIn(b"PRIVATE_SECRET_SHOULD_NOT_EXPORT",z.read(name))

    def test_symlink_cannot_leave_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"src"
            root.mkdir()
            self.fixture(root)
            path=root/FILES[0]
            path.unlink()
            external=Path(tmp)/"outside"
            external.write_text("PRIVATE")
            path.symlink_to(external)
            with self.assertRaisesRegex(ValueError,"MISSING_OR_UNSAFE_SOURCE"):
                collect(root)

    def test_empty_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"src"
            root.mkdir()
            self.fixture(root)
            (root/FILES[0]).write_bytes(b"")
            with self.assertRaisesRegex(ValueError,"INVALID_SOURCE_SIZE"):
                collect(root)

if __name__=="__main__":
    unittest.main()
