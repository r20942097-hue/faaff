"""Synthetic-only tests for read-only candidate archive checks."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from check_candidate_archive import inspect, IntakeError


def archive(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return buf.getvalue()


def addon_fixture():
    files = {"QA_REPORT.json": '{"status":"PASS"}',
             "README_JA.md": "Synthetic test only"}
    manifest = {}
    for product in ("StreamHarbor", "OmniStream", "TabWorkspace"):
        for browser in ("Chrome", "Firefox"):
            filename = f"{product}_{browser}_MV3.zip"
            inner_manifest = {"manifest_version": 3, "version": "1.0.0",
                              "permissions": []}
            if browser == "Firefox":
                inner_manifest["background"] = {"scripts": ["background.js"]}
                inner_manifest["browser_specific_settings"] = {
                    "gecko": {"id": f"{product}@test.invalid"}}
            else:
                inner_manifest["background"] = {"service_worker": "background.js"}
            raw = archive({"manifest.json": json.dumps(inner_manifest),
                           "background.js": "// artificial fixture\n"})
            files[f"Extensions/{browser}/{filename}"] = raw
            manifest[filename] = {"product": product, "browser": browser,
                                  "bytes": len(raw),
                                  "sha256": hashlib.sha256(raw).hexdigest(),
                                  "version": "1.0.0"}
    files["PACKAGE_MANIFEST.json"] = json.dumps(manifest)
    lines = [hashlib.sha256(v.encode() if isinstance(v, str) else v).hexdigest()
             + "  " + k for k, v in sorted(files.items())]
    files["SHA256SUMS.txt"] = "\n".join(lines) + "\n"
    return files


def replace_inner(entries, filename, updater):
    path = next(k for k in entries if k.endswith("/" + filename))
    with zipfile.ZipFile(io.BytesIO(entries[path])) as z:
        inner = {n: z.read(n) for n in z.namelist()}
    updater(inner)
    entries[path] = archive(inner)
    manifest = json.loads(entries["PACKAGE_MANIFEST.json"])
    manifest[filename]["bytes"] = len(entries[path])
    manifest[filename]["sha256"] = hashlib.sha256(entries[path]).hexdigest()
    entries["PACKAGE_MANIFEST.json"] = json.dumps(manifest)
    entries["SHA256SUMS.txt"] = "\n".join(
        hashlib.sha256(v.encode() if isinstance(v, str) else v).hexdigest()
        + "  " + k for k, v in sorted(entries.items())
        if k != "SHA256SUMS.txt") + "\n"


class CandidateArchiveChecks(unittest.TestCase):
    def check(self, entries, kind="auto"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.zip"
            path.write_bytes(archive(entries))
            return inspect(path, kind)

    def test_addons_verified(self):
        result = self.check(addon_fixture())
        self.assertEqual(result["type"], "three_addons")
        self.assertEqual(result["package_count"], 6)
        self.assertEqual(result["checksum_file_entries"], 9)
        self.assertTrue(all(x["crc_verified"] for x in result["packages"]))

    def test_addons_member_changed(self):
        entries = addon_fixture()
        name = "Extensions/Chrome/StreamHarbor_Chrome_MV3.zip"
        entries[name] = entries[name] + b"modified"
        with self.assertRaises(IntakeError):
            self.check(entries)

    def test_zip_traversal_rejected(self):
        entries = addon_fixture()
        entries["../credentials.txt"] = b"synthetic"
        with self.assertRaises(IntakeError):
            self.check(entries)

    def test_missing_firefox_id_rejected(self):
        entries = addon_fixture()
        path = "Extensions/Firefox/StreamHarbor_Firefox_MV3.zip"
        entries[path] = archive({"manifest.json":
                                 '{"manifest_version":3,"version":"1.0.0"}'})
        manifest = json.loads(entries["PACKAGE_MANIFEST.json"])
        manifest["StreamHarbor_Firefox_MV3.zip"]["bytes"] = len(entries[path])
        manifest["StreamHarbor_Firefox_MV3.zip"]["sha256"] = hashlib.sha256(entries[path]).hexdigest()
        entries["PACKAGE_MANIFEST.json"] = json.dumps(manifest)
        entries["SHA256SUMS.txt"] = "\n".join(
            hashlib.sha256(v.encode() if isinstance(v, str) else v).hexdigest()
            + "  " + k for k, v in sorted(entries.items())
            if k != "SHA256SUMS.txt") + "\n"
        with self.assertRaisesRegex(IntakeError, "FIREFOX_GECKO_ID_MISSING"):
            self.check(entries)

    def test_broad_host_is_a_review_flag_not_an_auto_rejection(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["host_permissions"] = ["https://*/*"]
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "StreamHarbor_Chrome_MV3.zip", edit)
        result = self.check(entries)
        entry = next(x for x in result["packages"] if
                     x["product"] == "StreamHarbor" and x["browser"] == "Chrome")
        self.assertIn("BROAD_HOST_PERMISSION", entry["review_flags"])

    def test_missing_background_reference_is_rejected(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["background"]["service_worker"] = "missing-worker.js"
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "StreamHarbor_Chrome_MV3.zip", edit)
        with self.assertRaisesRegex(IntakeError, "MANIFEST_REFERENCED_FILE_MISSING"):
            self.check(entries)

    def test_firefox_background_scripts_required(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["background"] = {}
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "OmniStream_Firefox_MV3.zip", edit)
        with self.assertRaisesRegex(IntakeError, "FIREFOX_BACKGROUND_SCRIPTS_MISSING"):
            self.check(entries)

    def test_declared_popup_must_exist(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["action"] = {"default_popup": "phantom-popup.html"}
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "TabWorkspace_Chrome_MV3.zip", edit)
        with self.assertRaisesRegex(IntakeError, "MANIFEST_REFERENCED_FILE_MISSING"):
            self.check(entries)

    def test_sensitive_api_permission_requires_review(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["permissions"] = ["cookies"]
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "StreamHarbor_Firefox_MV3.zip", edit)
        result = self.check(entries)
        entry = next(x for x in result["packages"] if
                     x["product"] == "StreamHarbor" and x["browser"] == "Firefox")
        self.assertIn("SENSITIVE_API_PERMISSION", entry["review_flags"])

    def test_malformed_icons_type_rejected_without_crash(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["icons"] = ["wrong-type"]
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "TabWorkspace_Chrome_MV3.zip", edit)
        with self.assertRaisesRegex(IntakeError, "MANIFEST_RESOURCE_FIELDS_INVALID"):
            self.check(entries)

    def test_malformed_content_script_type_rejected(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["content_scripts"] = {"js": "background.js"}
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "OmniStream_Chrome_MV3.zip", edit)
        with self.assertRaisesRegex(IntakeError, "CONTENT_SCRIPT_DECLARATION_INVALID"):
            self.check(entries)

    def test_stale_chrome_version_name_is_rejected(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["version_name"] = "0.79.0 CANDIDATE / NO_GO"
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "TabWorkspace_Chrome_MV3.zip", edit)
        with self.assertRaisesRegex(IntakeError, "CHROME_VERSION_NAME_MISMATCH"):
            self.check(entries)

    def test_matching_version_but_conflicting_no_go_is_rejected(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["version_name"] = "1.0.0 CANDIDATE / NO_GO"
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "TabWorkspace_Chrome_MV3.zip", edit)
        with self.assertRaisesRegex(IntakeError, "GO_CANDIDATE_CONFLICTING_NO_GO_LABEL"):
            self.check(entries)

    def test_matching_chrome_version_name_can_be_a_candidate(self):
        entries = addon_fixture()
        def edit(inner):
            m = json.loads(inner["manifest.json"])
            m["version_name"] = "1.0.0 CANDIDATE / NOT_RELEASED"
            inner["manifest.json"] = json.dumps(m).encode()
        replace_inner(entries, "TabWorkspace_Chrome_MV3.zip", edit)
        result = self.check(entries)
        self.assertEqual(result["package_count"], 6)

    def test_rplay_no_go(self):
        entries = {
            "DEVELOPMENT_HANDOFF_v2.68.0.md": "CANDIDATE / NO GO",
            "rplay-stable-player-extension/manifest.json":
                '{"manifest_version":3,"version":"2.68.0","background":{"service_worker":"background.js"}}',
            "rplay-stable-player-extension/background.js": "// synthetic",
            "rplay-stable-player-extension-firefox/manifest.json":
                '{"manifest_version":3,"version":"2.68.0","background":{"scripts":["background.js"]}}',
            "rplay-stable-player-extension-firefox/background.js": "// synthetic",
            "src/one.js": "// safe",
            "tests/test_fixture.py": "# safe"
        }
        result = self.check(entries)
        self.assertEqual(result["status"], "NO_GO")
        self.assertEqual(result["js_source_files"], 1)
        self.assertEqual(result["python_test_modules"], 1)


if __name__ == "__main__":
    unittest.main()
