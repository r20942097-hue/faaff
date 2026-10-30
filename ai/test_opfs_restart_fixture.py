import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.opfs_restart_fixture import (
    SOURCE_A, SOURCE_B, HASH_A, HASH_B, INITIALIZE,
    STAGE_THEN_ABORT_MANIFEST, RECOVER_AND_COMMIT,
    report_template, require_generation, run, main,
)

class OpfsRestartContractTests(unittest.TestCase):
    def test_fixture_digests_match(self):
        self.assertEqual(hashlib.sha256(bytes(SOURCE_A)).hexdigest(), HASH_A)
        self.assertEqual(hashlib.sha256(bytes(SOURCE_B)).hexdigest(), HASH_B)
        self.assertNotEqual(HASH_A, HASH_B)

    def test_report_is_never_product_go(self):
        result=report_template('firefox')
        self.assertEqual(result['release_readiness'],'NO_GO')
        self.assertEqual(result['actual_process_crash'],'NOT_RUN')
        self.assertEqual(result['product_e2e'],'NOT_RUN')

    def test_manifest_commit_only_after_blob(self):
        self.assertLess(INITIALIZE.index("'blob-0001.bin'"), INITIALIZE.index("'state.json'"))
        self.assertLess(RECOVER_AND_COMMIT.index("'blob-0002.bin'"),
                        RECOVER_AND_COMMIT.index('const manifestWriter'))
        self.assertIn('await manifestWriter.close()', RECOVER_AND_COMMIT)

    def test_abort_happens_before_marking_generation_2(self):
        self.assertIn('await manifestWriter.abort()', STAGE_THEN_ABORT_MANIFEST)
        self.assertIn('await bw.close()', STAGE_THEN_ABORT_MANIFEST)

    def test_valid_generation(self):
        observed={'generation':1,'active':'blob-0001.bin','declared':HASH_A,
                  'calculated':HASH_A,'bytes':SOURCE_A}
        require_generation(observed,1,HASH_A,SOURCE_A)

    def test_corruption_blocks(self):
        observed={'generation':1,'active':'blob-0001.bin','declared':HASH_A,
                  'calculated':HASH_B,'bytes':SOURCE_A}
        with self.assertRaisesRegex(AssertionError,'GENERATION_'):
            require_generation(observed,1,HASH_A,SOURCE_A)

    @patch('ai.opfs_restart_fixture.probe',side_effect=RuntimeError('private /home/user'))
    def test_failure_redacts_browser_and_user_paths(self,unused):
        report=run('chromium')
        self.assertEqual(report['status'],'BLOCKED')
        self.assertNotIn('/home/user',json.dumps(report))
        self.assertEqual(report['restart_new_generation'],'NOT_RUN')

    @patch('ai.opfs_restart_fixture.probe',side_effect=RuntimeError('synthetic failure'))
    def test_cli_failure_is_nonzero_and_saves_json(self,unused):
        with tempfile.TemporaryDirectory() as root:
            file=Path(root)/'fail.json'
            with patch('builtins.print'):
                exit_code=main(['--browser','firefox','--output',str(file)])
            self.assertEqual(exit_code,2)
            self.assertEqual(json.loads(file.read_text())['release_readiness'],'NO_GO')

if __name__=='__main__':
    unittest.main()
