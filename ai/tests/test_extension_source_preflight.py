"""Local-only source manifest verifier regression checks; no browser launch."""
import io
import json
import os
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extension_source_preflight as m


class PreflightTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.src = self.root / 'src'
        self.src.mkdir()

    def make_dir(self, base='.', manifest=None, files=None):
        p = self.src / base
        p.mkdir(parents=True, exist_ok=True)
        if manifest is None:
            manifest = {'manifest_version': 3, 'name': 'Synthetic test', 'version': '1.2.0',
                        'background': {'service_worker': 'worker.js'},
                        'action': {'default_popup': 'popup.html'},
                        'content_scripts': [{'matches': ['http://127.0.0.1/*'], 'js': ['content.js']}],
                        'icons': {'16': 'icon.png'}}
        (p/'manifest.json').write_text(json.dumps(manifest))
        for name in (files if files is not None else ['worker.js', 'popup.html', 'content.js', 'icon.png']):
            f=p/name
            f.parent.mkdir(parents=True,exist_ok=True)
            f.write_text('content')
        return p

    def report_zip(self, files, archive_status='PASS', expected=None):
        path=self.root/'input.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, value in files.items():
                z.writestr(name, value)
        def stub(_path, expected_sha256=None):
            return {'status': archive_status, 'sha256': expected_sha256,
                    'summary': {'archives_checked': 1}}
        with patch.dict(sys.modules, {'artifact_gate': types.SimpleNamespace(inspect=stub)}):
            return m.inspect(path, expected)

    def test_directory_valid(self):
        self.make_dir()
        r=m.inspect(self.src)
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['browser_e2e'], 'NOT_RUN')
        self.assertEqual(r['release_decision'], 'CANDIDATE_NO_GO')

    def test_multiple_manifest(self):
        self.make_dir('chrome')
        self.make_dir('firefox')
        r=m.inspect(self.src)
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(len(r['extensions']), 2)

    def test_missing_script(self):
        self.make_dir(files=['worker.js', 'popup.html','icon.png'])
        r=m.inspect(self.src)
        self.assertEqual(r['status'], 'FAIL')
        self.assertIn('referenced file missing', ' '.join(r['extensions'][0]['errors']))

    def test_bad_manifest(self):
        self.make_dir()
        (self.src/'manifest.json').write_text('{broken')
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_manifest_too_large(self):
        self.make_dir()
        (self.src/'manifest.json').write_text(' ' * (m.MANIFEST_LIMIT + 1))
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_unsafe_path_traversal(self):
        self.make_dir(manifest={'manifest_version': 3,'name':'x','version':'1', 'background':{'service_worker':'../other.js'}})
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_malformed_version_bool(self):
        self.make_dir(manifest={'manifest_version':True,'name':'x','version':'1'})
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_malformed_version_text(self):
        self.make_dir(manifest={'manifest_version': '3','name':'x','version':'1'})
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_wrong_content_script_structure(self):
        self.make_dir(manifest={'manifest_version': 3,'name':'x','version':'1','content_scripts':[{'js':['x.js']}]})
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_broad_hosts_warn_not_pass_e2e(self):
        self.make_dir(manifest={'manifest_version': 3,'name':'x','version':'1','host_permissions':['<all_urls>']})
        r=m.inspect(self.src)
        self.assertEqual(r['status'], 'PASS')
        self.assertIn('broad host permissions', r['extensions'][0]['warnings'][0])
        self.assertEqual(r['real_site_e2e'], 'NOT_RUN')

    def test_mv2_warning(self):
        self.make_dir(manifest={'manifest_version':2,'name':'x','version':'1'})
        r=m.inspect(self.src)
        self.assertEqual(r['status'],'PASS')
        self.assertIn('MV2',r['extensions'][0]['warnings'][0])

    def test_nested_zip_partial(self):
        self.make_dir()
        (self.src/'nested.zip').write_bytes(b'not an actual zip')
        self.assertEqual(m.inspect(self.src)['status'],'PARTIAL')

    def test_no_manifest_partial(self):
        (self.src/'README.md').write_text('x')
        self.assertEqual(m.inspect(self.src)['status'],'PARTIAL')

    def test_symlink_fails(self):
        self.make_dir()
        try: (self.src/'link').symlink_to(self.root)
        except (OSError,NotImplementedError): self.skipTest('cannot create symlink')
        self.assertEqual(m.inspect(self.src)['status'],'FAIL')

    def test_directory_sha_is_invalid(self):
        self.make_dir()
        self.assertEqual(m.inspect(self.src,'0'*64)['status'],'FAIL')

    def test_zip_valid(self):
        manifest={'manifest_version':3,'name':'x','version':'1','background':{'service_worker':'worker.js'}}
        r=self.report_zip({'foo/manifest.json':json.dumps(manifest),'foo/worker.js':'x'},expected='f'*64)
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(r['archive']['sha256'],'f'*64)

    def test_zip_nested_partial(self):
        manifest={'manifest_version':3,'name':'x','version':'1'}
        r=self.report_zip({'manifest.json':json.dumps(manifest),'other.zip':'x'})
        self.assertEqual(r['status'],'PARTIAL')

    def test_zip_archive_failure_blocks_manifest(self):
        r=self.report_zip({'manifest.json':'{}'},archive_status='FAIL')
        self.assertEqual(r['status'],'FAIL')
        self.assertEqual(r['extensions'],[])

    def test_zip_missing_file(self):
        manifest={'manifest_version':3,'name':'x','version':'1','action':{'default_popup':'missing.html'}}
        r=self.report_zip({'manifest.json':json.dumps(manifest)})
        self.assertEqual(r['status'],'FAIL')

    def test_option_page_icons(self):
        manifest={'manifest_version':3,'name':'x','version':'1', 'options_ui':{'page':'options.html'},
                  'icons':{'32':'icons/test.png'},'chrome_url_overrides':{'newtab':'newtab.html'}}
        self.make_dir(manifest=manifest,files=['options.html','icons/test.png','newtab.html'])
        self.assertEqual(m.inspect(self.src)['status'],'PASS')

    def test_casefold_directory_conflict(self):
        self.make_dir()
        if os.name == 'nt': self.skipTest('case-insensitive FS')
        (self.src/'CONTENT.JS').write_text('other')
        self.assertEqual(m.inspect(self.src)['status'],'FAIL')

    def test_no_closing_browser_or_identity_claims(self):
        self.make_dir()
        r=m.inspect(self.src)
        self.assertEqual(r['browser_install'],'NOT_RUN')
        self.assertEqual(r['windows_device'],'NOT_RUN')

    def test_duplicate_manifest_keys_fail_closed(self):
        self.make_dir()
        (self.src/'manifest.json').write_text('{"manifest_version":3,"name":"x","version":"1","version":"2"}')
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_windows_reserved_source_filename(self):
        self.make_dir()
        if os.name == 'nt': self.skipTest('Windows prevents reserved names')
        (self.src/'CON.txt').write_text('x')
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_bad_asset_windows_name(self):
        self.make_dir(manifest={'manifest_version':3,'name':'x','version':'1',
                                'background':{'service_worker':'CON.js'}})
        self.assertEqual(m.inspect(self.src)['status'], 'FAIL')

    def test_cli_exit_codes(self):
        self.make_dir()
        self.assertEqual(m.main([str(self.src)]),0)
        (self.src/'content.js').unlink()
        self.assertEqual(m.main([str(self.src)]),1)
        (self.src/'manifest.json').unlink()
        self.assertEqual(m.main([str(self.src)]),2)



class ManifestCoverageTests(unittest.TestCase):
    """Negative fixtures for MV2/MV3 package-reference omissions."""
    setUp = PreflightTests.setUp
    make_dir = PreflightTests.make_dir
    report_zip = PreflightTests.report_zip

    def _manifest(self, **fields):
        base = {"manifest_version": 3, "name": "Synthetic", "version": "1.0"}
        base.update(fields)
        return base

    def test_dnr_existing_ruleset_file(self):
        manifest = self._manifest(declarative_net_request={"rule_resources": [
            {"id": "base", "enabled": True, "path": "rules.json"}]})
        self.make_dir(manifest=manifest, files=["rules.json"])
        self.assertEqual(m.inspect(self.src)["status"], "PASS")

    def test_dnr_missing_ruleset_file_blocks_pass(self):
        manifest = self._manifest(declarative_net_request={"rule_resources": [
            {"id": "base", "enabled": False, "path": "missing-rules.json"}]})
        self.make_dir(manifest=manifest, files=[])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_dnr_requires_ruleset_path(self):
        manifest = self._manifest(declarative_net_request={"rule_resources": [
            {"id": "base", "enabled": True}]})
        self.make_dir(manifest=manifest, files=[])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_dnr_null_ruleset_path(self):
        manifest = self._manifest(declarative_net_request={"rule_resources": [
            {"id": "base", "enabled": True, "path": None}]})
        self.make_dir(manifest=manifest, files=[])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_dnr_invalid_and_duplicate_ids(self):
        manifest = self._manifest(declarative_net_request={"rule_resources": [
            {"id": "base", "enabled": True, "path": "rules.json"},
            {"id": "base", "enabled": False, "path": "rules.json"}]})
        self.make_dir(manifest=manifest, files=["rules.json"])
        self.assertIn("duplicate ruleset id", " ".join(m.inspect(self.src)["extensions"][0]["errors"]))

    def test_dnr_bad_enabled_bool(self):
        manifest = self._manifest(declarative_net_request={"rule_resources": [
            {"id": "base", "enabled": "true", "path": "rules.json"}]})
        self.make_dir(manifest=manifest, files=["rules.json"])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_dnr_not_a_dictionary(self):
        self.make_dir(manifest=self._manifest(declarative_net_request="bad"), files=[])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_sandbox_file_reference(self):
        manifest = self._manifest(sandbox={"pages": ["sandbox/page.html"]})
        self.make_dir(manifest=manifest, files=["sandbox/page.html"])
        self.assertEqual(m.inspect(self.src)["status"], "PASS")
        (self.src/"sandbox/page.html").unlink()
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_mv2_web_accessible_resources(self):
        manifest = self._manifest(manifest_version=2, web_accessible_resources=["assets/icon.png"])
        self.make_dir(manifest=manifest, files=["assets/icon.png"])
        self.assertEqual(m.inspect(self.src)["status"], "PASS")
        (self.src/"assets/icon.png").unlink()
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_mv3_web_accessible_resources(self):
        manifest = self._manifest(web_accessible_resources=[{
            "resources": ["assets/icon.png"], "matches": ["https://example.com/*"]}])
        self.make_dir(manifest=manifest, files=["assets/icon.png"])
        self.assertEqual(m.inspect(self.src)["status"], "PASS")
        (self.src/"assets/icon.png").unlink()
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_mv3_war_extension_ids_alternative(self):
        manifest = self._manifest(web_accessible_resources=[{
            "resources": ["/assets/icon.png"], "extension_ids": ["other-extension-id"]}])
        self.make_dir(manifest=manifest, files=["assets/icon.png"])
        self.assertEqual(m.inspect(self.src)["status"], "PASS")

    def test_mv3_missing_access_targets_is_failure(self):
        manifest = self._manifest(web_accessible_resources=[{"resources": ["assets/icon.png"]}])
        self.make_dir(manifest=manifest, files=["assets/icon.png"])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_wildcard_resources_exact_and_missing(self):
        manifest = self._manifest(web_accessible_resources=[{
            "resources": ["assets/*.png"], "matches": ["https://example.com/*"]}])
        self.make_dir(manifest=manifest, files=["assets/icon.png"])
        self.assertEqual(m.inspect(self.src)["status"], "PASS")
        (self.src/"assets/icon.png").unlink()
        result = m.inspect(self.src)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(any("no matching packaged file" in w for w in result["extensions"][0]["warnings"]))

    def test_web_resource_traversal_rejected(self):
        manifest = self._manifest(web_accessible_resources=[{
            "resources": ["../outside/*.js"], "matches": ["https://example.com/*"]}])
        self.make_dir(manifest=manifest, files=[])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_background_type_wrong_fails(self):
        self.make_dir(manifest=self._manifest(background="worker.js"), files=["worker.js"])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_content_script_malformed_js(self):
        manifest = self._manifest(content_scripts=[{"matches": ["https://example.com/*"],
                                                     "js": "content.js"}])
        self.make_dir(manifest=manifest, files=["content.js"])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_zip_dnr_rules_file(self):
        manifest = self._manifest(declarative_net_request={"rule_resources": [
            {"id": "base", "enabled": True, "path": "rules.json"}]})
        good = self.report_zip({"manifest.json": json.dumps(manifest), "rules.json": "[]"})
        self.assertEqual(good["status"], "PASS")
        bad = self.report_zip({"manifest.json": json.dumps(manifest)})
        self.assertEqual(bad["status"], "FAIL")

    def test_bad_war_type_fails(self):
        self.make_dir(manifest=self._manifest(web_accessible_resources="all"), files=[])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")

    def test_mv3_string_war_rejected(self):
        self.make_dir(manifest=self._manifest(web_accessible_resources=["icon.png"]), files=["icon.png"])
        self.assertEqual(m.inspect(self.src)["status"], "FAIL")


class RealArchiveGateIntegration(unittest.TestCase):
    """Actual artifact_gate interface, no monkeypatch; only when module is present."""

    def setUp(self):
        if not (Path(__file__).resolve().parents[1] / "artifact_gate.py").is_file():
            self.skipTest("artifact_gate.py not bundled into standalone test package")
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.archive = Path(t.name) / "fixture.zip"

    def test_real_zip_preflight_passes_integrity_and_manifest(self):
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("extension/manifest.json", json.dumps({
                "manifest_version": 3, "name": "Synthetic", "version": "1.0",
                "declarative_net_request": {"rule_resources": [
                    {"id": "base", "enabled": True, "path": "rules.json"}]}}))
            zf.writestr("extension/rules.json", "[]")
        result = m.inspect(self.archive)
        self.assertEqual(result["archive"]["status"], "PASS")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["real_site_e2e"], "NOT_RUN")

    def test_real_zip_traversal_rejected_before_manifest(self):
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("../danger.txt", "bad")
            zf.writestr("manifest.json", json.dumps({
                "manifest_version": 3, "name": "Synthetic", "version": "1.0"}))
        result = m.inspect(self.archive)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["reason"], "ARCHIVE_INTEGRITY_FAIL")
        self.assertEqual(result["extensions"], [])


if __name__=='__main__':
    unittest.main()