from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from phase3_security.dependency_inventory import scan_archive


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Phase3DependencyInventoryTests(unittest.TestCase):
    def make_archive(self, root: Path, files: dict[str, bytes], *, symlink: str | None = None) -> tuple[Path, Path]:
        archive = root / "phase2.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, body in files.items():
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.create_system = 3
                zf.writestr(info, body)
            if symlink:
                info = zipfile.ZipInfo(symlink)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                info.create_system = 3
                zf.writestr(info, b"target")
        checksum = root / "SOURCE-ARCHIVE-SHA256.txt"
        checksum.write_text(f"{digest(archive.read_bytes())}  {archive.name}\n", encoding="utf-8")
        return archive, checksum

    def test_pyproject_inventory_is_partial_and_unknown_for_vulnerabilities(self) -> None:
        pyproject = b'''[build-system]\nrequires = ["setuptools>=70"]\n\n[project]\nname = "demo"\ndependencies = ["requests>=2.32", "idna==3.10"]\n\n[project.optional-dependencies]\ntest = ["pytest>=8"]\n'''
        with tempfile.TemporaryDirectory() as td:
            archive, checksum = self.make_archive(Path(td), {"pyproject.toml": pyproject})
            report, sbom = scan_archive(archive, checksum)
        self.assertEqual(report["source_archive"]["integrity"], "PASS")
        self.assertEqual(report["scope"]["coverage"], "PARTIAL")
        self.assertEqual(report["inventory"]["status"], "PASS")
        self.assertEqual(report["inventory"]["dependency_declaration_count"], 4)
        self.assertEqual(report["security_posture"]["vulnerability_posture"], "UNKNOWN")
        self.assertEqual(report["sbom"]["status"], "DECLARATION_ONLY")
        self.assertEqual(sbom["bomFormat"], "CycloneDX")
        self.assertEqual({c["name"] for c in sbom["components"]}, {"setuptools", "requests", "idna", "pytest"})

    def test_package_json_dependencies_are_inventoried(self) -> None:
        package = json.dumps({"dependencies": {"react": "^19.0.0"}, "devDependencies": {"vite": "^7.0.0"}}).encode()
        with tempfile.TemporaryDirectory() as td:
            archive, checksum = self.make_archive(Path(td), {"web/package.json": package})
            report, _ = scan_archive(archive, checksum)
        deps = report["inventory"]["manifests"][0]["dependencies"]
        self.assertEqual([(d["group"], d["name"]) for d in deps], [("dependencies", "react"), ("devDependencies", "vite")])

    def test_malformed_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive, checksum = self.make_archive(Path(td), {"package.json": b"{"})
            with self.assertRaisesRegex(ValueError, "cannot parse dependency manifest"):
                scan_archive(archive, checksum)

    def test_unsafe_path_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive, checksum = self.make_archive(Path(td), {"../pyproject.toml": b"[project]\nname='x'\n"})
            with self.assertRaisesRegex(ValueError, "unsafe ZIP path"):
                scan_archive(archive, checksum)

    def test_symlink_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive, checksum = self.make_archive(Path(td), {"pyproject.toml": b"[project]\nname='x'\n"}, symlink="link")
            with self.assertRaisesRegex(ValueError, "symlink ZIP entry"):
                scan_archive(archive, checksum)

    def test_checksum_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive, checksum = self.make_archive(root, {"pyproject.toml": b"[project]\nname='x'\n"})
            checksum.write_text(f"{'0' * 64}  {archive.name}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                scan_archive(archive, checksum)


if __name__ == "__main__":
    unittest.main()
