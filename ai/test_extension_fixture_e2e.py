import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.extension_fixture_e2e import MANIFEST, run, write_fixture

class ExtensionFixtureTest(unittest.TestCase):
    def test_restricted_host_permission(self):
        self.assertEqual(MANIFEST['host_permissions'], ['http://127.0.0.1/*'])
        self.assertEqual(MANIFEST['manifest_version'], 3)
        self.assertNotIn('externally_connectable', MANIFEST)

    def test_fixture_writes_consistent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_fixture(tmp)
            manifest = json.loads((folder / 'manifest.json').read_text())
            self.assertTrue((folder / 'content.js').is_file())
            self.assertEqual(manifest['background']['service_worker'], 'background.js')

    @patch('ai.extension_fixture_e2e.probe', return_value={'status': 'PASS'})
    def test_fixture_pass_does_not_claim_product(self, ignored):
        result = run()
        self.assertEqual(result['fixture_e2e']['status'], 'PASS')
        self.assertEqual(result['real_product_e2e'], 'NOT_RUN')
        self.assertEqual(result['firefox_extension_e2e'], 'NOT_RUN')
        self.assertEqual(result['release_readiness'], 'NO_GO')

    @patch('ai.extension_fixture_e2e.probe', side_effect=RuntimeError('private /tmp/test'))
    def test_failure_is_redacted(self, ignored):
        result = run()
        self.assertEqual(result['fixture_e2e']['status'], 'FAIL')
        self.assertNotIn('private /tmp/test', json.dumps(result))

if __name__ == '__main__':
    unittest.main()
